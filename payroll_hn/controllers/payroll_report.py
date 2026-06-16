from odoo import http
from odoo.http import request
import random
import json
import tempfile
import os
import base64


class PayrollReport(http.Controller):

    @http.route('/payroll_hn/test', auth='user', type='http', methods=['GET'])
    def test_route(self, **kw):
        """Ruta de prueba para verificar que el controlador funciona"""
        return "Controlador funcionando correctamente"

    @http.route('/payroll_hn/export_xlsx', auth='user', type='json', methods=['POST'])
    def export_xlsx(self, **kw):
        data = json.loads(kw['data'])
        lot_text = data.get('lot_text', '')

        payslip_run_id = request.env['hr.payslip.run'].search([], limit=1)
        file_content = payslip_run_id.generate_xlsx_file(lot_text)

        # Convertir el contenido del archivo a base64 y almacenarlo en la base de datos
        attachment = request.env['ir.attachment'].create({
            'name': 'payslip.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_content),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'hr.payslip.run',
            'res_id': payslip_run_id.id,
        })

        # Generar una URL para la descarga del archivo
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        download_url = f'{base_url}/web/content/{attachment.id}?download=true'

        return {'url': download_url}

    @http.route('/web/content/<int:id>', type='http', auth='public')
    def download_xlsx_file(self, id, **kwargs):
        attachment = request.env['ir.attachment'].sudo().browse(id)
        if not attachment.exists():
            return request.not_found()

        file_content = base64.b64decode(attachment.datas)
        return request.make_response(file_content, [
            ('Content-Type', attachment.mimetype),
            ('Content-Disposition', f'attachment; filename={attachment.name}')
        ])


    @http.route('/payroll_hn/lot_search', auth='user', type='json', methods=['POST'])
    def lot_search(self, **kw):
        try:
            data = kw.get('data', {})
            lot_text = data.get('lot_text', '')
            
            if not lot_text:
                return {'error': 'No lot text provided'}

            payslips = request.env['hr.payslip'].search([('payslip_run_id.name','=',lot_text)])
            
            if not payslips:
                return {
                    'deductions': [],
                    'benefits': [],
                    'employees': [],
                }

            # Obtener reglas de deducciones y beneficios
            deduction_rules = {}
            benefit_rules = {}
            
            print("DEBUG: Buscando reglas en payslips...")
            for payslip in payslips:
                print(f"DEBUG: Payslip {payslip.id} - {payslip.employee_id.name}")
                for line in payslip.line_ids:
                    if line.amount != 0 and line.salary_rule_id and line.category_id:
                        rule_name = line.salary_rule_id.name
                        rule_id = line.salary_rule_id.id
                        category = line.category_id.code
                        
                        print(f"DEBUG: Regla encontrada - {rule_name}: Amount={line.amount}, Category={category}")
                        
                        if category == 'DED':
                            if rule_id not in deduction_rules:
                                deduction_rules[rule_id] = rule_name
                                print(f"DEBUG: ✅ Agregada deducción: {rule_name}")
                        elif category == 'ALW':
                            if rule_id not in benefit_rules:
                                benefit_rules[rule_id] = rule_name
                                print(f"DEBUG: ✅ Agregado beneficio: {rule_name}")
                        else:
                            print(f"DEBUG: ⚠️ Categoría desconocida: {category}")
                    else:
                        if line.amount != 0:
                            print(f"DEBUG: Línea con amount={line.amount} pero sin salary_rule_id o category_id")
            
            print(f"DEBUG: Total deducciones encontradas: {len(deduction_rules)}")
            print(f"DEBUG: Total beneficios encontrados: {len(benefit_rules)}")

            # Preparar listas de nombres
            deductions_name = list(deduction_rules.values())
            benefits_name = list(benefit_rules.values())

            employees = []

            for payslip in payslips:
                # Salario base
                basic_line = payslip.line_ids.filtered(lambda x: x.category_id and x.category_id.code == 'BASIC')
                salary = basic_line[0].total if basic_line else 0
                
                if salary == 0:
                    salary = payslip.contract_id.wage if payslip.contract_id else 0

                # Procesar beneficios
                rules_benefits = []
                total_benefits = 0
                for rule_id, rule_name in benefit_rules.items():
                    line = payslip.line_ids.filtered(lambda x: x.salary_rule_id.id == rule_id)
                    amount = line[0].amount if line else 0
                    total_benefits += amount
                    rules_benefits.append({'rule': rule_name, 'amount': amount})

                # Procesar deducciones
                rules_deductions = []
                total_deductions = 0
                for rule_id, rule_name in deduction_rules.items():
                    line = payslip.line_ids.filtered(lambda x: x.salary_rule_id.id == rule_id)
                    amount = line[0].amount if line else 0
                    total_deductions += amount
                    rules_deductions.append({'rule': rule_name, 'amount': amount})
                
                # Calcular salario neto correcto: salario + beneficios + deducciones
                # (las deducciones ya vienen con signo negativo)
                net_salary = salary + total_benefits + total_deductions
                
                rules = [{'benefits': rules_benefits, 'deductions': rules_deductions}]
                employees.append({
                    'employee': payslip.employee_id.name, 
                    'salary': salary, 
                    'rules': rules, 
                    'total_deductions': total_deductions, 
                    'total_benefits': total_benefits,
                    'net_salary': net_salary
                })

            employees = sorted(employees, key=lambda x: x['employee'])

            return {
                'deductions': deductions_name,
                'benefits': benefits_name,
                'employees': employees,
            }
        except Exception as e:
            return {'error': f'Error: {str(e)}'}
    
    @http.route('/payroll_hn/lot_deduction_search', auth='user', type='json', methods=['POST'])
    def lot_deduction_search(self, **kw):
        try:
            data = kw.get('data', {})
            lot_text = data.get('lot_text', '')
            
            if not lot_text:
                return {'error': 'No lot text provided'}

            payslips = request.env['hr.payslip'].search([('payslip_run_id.name','=',lot_text)])
            
            if not payslips:
                return {
                    'deductions': [],
                    'employees': [],
                }

            # Obtener reglas de deducciones de forma simple
            deduction_rules = {}
            
            for payslip in payslips:
                for line in payslip.line_ids:
                    # Para Odoo 18, verificar que la línea sea válida
                    if (line.amount != 0 and line.salary_rule_id and line.category_id and 
                        line.category_id.code == 'DED'):
                        rule_name = line.salary_rule_id.name
                        rule_id = line.salary_rule_id.id
                        if rule_id not in deduction_rules:
                            deduction_rules[rule_id] = rule_name

            deductions_name = list(deduction_rules.values())
            employees = []

            for payslip in payslips:
                rules = []
                total_deductions = 0
                
                for rule_id, rule_name in deduction_rules.items():
                    line = payslip.line_ids.filtered(lambda x: x.salary_rule_id.id == rule_id)
                    amount = line.amount if line else 0
                    total_deductions += amount
                    rules.append({'rule': rule_name, 'amount': amount})

                employees.append({'employee': payslip.employee_id.name, 'rules': rules, 'total_deductions': total_deductions})

            employees = sorted(employees, key=lambda x: x['employee'])

            return {
                'deductions': deductions_name,
                'employees': employees,
            }
        except Exception as e:
            return {'error': str(e)}