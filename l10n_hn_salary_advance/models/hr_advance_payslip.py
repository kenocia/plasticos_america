# -*- coding: utf-8 -*-
from datetime import datetime
import logging
from odoo import models, Command, fields, api, tools, _

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('employee_id', 'contract_id', 'struct_id', 'date_from', 'date_to', 'struct_id')
    def _compute_input_line_ids(self):
        print("=" * 80)
        print("=== INICIO _compute_input_line_ids ===")
        _logger.info("=== INICIO _compute_input_line_ids ===")
        print(f"Procesando {len(self)} nómina(s)")
        _logger.info("Procesando %d nómina(s)", len(self))
        super(HrPayslip, self)._compute_input_line_ids()
        input_line_vals = []
        attachment_types = self._get_attachment_types_advance()
        attachment_type_ids = [f.id for f in attachment_types.values()]
        lines_to_remove = self.input_line_ids.filtered(lambda x: x.input_type_id.id in attachment_type_ids)
        input_line_vals = [Command.unlink(line.id) for line in lines_to_remove]
        print(f"Líneas a eliminar: {len(lines_to_remove)}")
        _logger.info("Líneas a eliminar: %d", len(lines_to_remove))
        
        # Obtener la estructura structure_type_employee
        structure_type_employee = None
        try:
            structure_type_employee = self.env.ref('hr_contract.structure_type_employee')
            print(f"Estructura structure_type_employee encontrada: ID={structure_type_employee.id}")
            _logger.info("Estructura structure_type_employee encontrada: ID=%d", structure_type_employee.id)
        except ValueError as e:
            print(f"ADVERTENCIA: Estructura structure_type_employee no encontrada: {str(e)}")
            _logger.warning("Estructura structure_type_employee no encontrada: %s", str(e))
        
        for payslip in self:
            print("-" * 80)
            print(f"--- Procesando nómina ID: {payslip.id}, Empleado: {payslip.employee_id.name if payslip.employee_id else 'Sin empleado'} ---")
            _logger.info("--- Procesando nómina ID: %d, Empleado: %s ---", payslip.id, payslip.employee_id.name if payslip.employee_id else 'Sin empleado')
            if payslip.employee_id:
                # Información de la estructura de la nómina
                struct_info = "Sin estructura"
                is_structure_employee = False
                if payslip.struct_id:
                    struct_info = f"Estructura ID={payslip.struct_id.id}, Nombre={payslip.struct_id.name}"
                    if payslip.struct_id.type_id:
                        struct_info += f", Tipo ID={payslip.struct_id.type_id.id}, Tipo Nombre={payslip.struct_id.type_id.name}"
                        # Verificar si es structure_type_employee
                        if structure_type_employee and payslip.struct_id.type_id.id == structure_type_employee.id:
                            is_structure_employee = True
                            print(f">>> ESTRUCTURA DETECTADA: structure_type_employee (ID={structure_type_employee.id})")
                            _logger.info(">>> ESTRUCTURA DETECTADA: structure_type_employee (ID=%d)", structure_type_employee.id)
                print(f"Estructura de la nómina: {struct_info}")
                _logger.info("Estructura de la nómina: %s", struct_info)
                
                # Buscar todos los adelantos aprobados del empleado
                all_advances = payslip.env['salary.advance'].search(
                    [('employee_id', '=', payslip.employee_id.id),
                     ('state', '=', 'approve')],
                    order='date')
                print(f"Total de adelantos aprobados encontrados: {len(all_advances)}")
                _logger.info("Total de adelantos aprobados encontrados: %d", len(all_advances))
                
                # Si es structure_type_employee, buscar adelantos de 13avo y 14avo
                if is_structure_employee:
                    print(">>> RUTA: structure_type_employee - Buscando adelantos 13avo y 14avo")
                    _logger.info(">>> RUTA: structure_type_employee - Buscando adelantos 13avo y 14avo")
                    # Buscar adelantos de 13avo
                    adv_13avo = all_advances.filtered(lambda a: a.advance_thirteen_avo == True)
                    # Buscar adelantos de 14avo
                    adv_14avo = all_advances.filtered(lambda a: a.advance_fourteen_avo == True)
                    # Buscar adelantos regulares (ni 13avo ni 14avo)
                    adv_regular = all_advances.filtered(lambda a: a.advance_thirteen_avo == False and a.advance_fourteen_avo == False)
                    
                    print(f"Adelantos 13avo encontrados: {len(adv_13avo)}")
                    print(f"Adelantos 14avo encontrados: {len(adv_14avo)}")
                    print(f"Adelantos regulares encontrados: {len(adv_regular)}")
                    _logger.info("Adelantos 13avo encontrados: %d", len(adv_13avo))
                    _logger.info("Adelantos 14avo encontrados: %d", len(adv_14avo))
                    _logger.info("Adelantos regulares encontrados: %d", len(adv_regular))
                    
                    # Combinar todos los adelantos para procesarlos
                    adv_salary = adv_13avo + adv_14avo + adv_regular
                else:
                    print(">>> RUTA: Estructura regular (no structure_type_employee) - Buscando solo adelantos regulares")
                    _logger.info(">>> RUTA: Estructura regular (no structure_type_employee) - Buscando solo adelantos regulares")
                    # Solo buscar adelantos regulares
                    adv_salary = all_advances.filtered(
                        lambda a: a.advance_thirteen_avo == False and a.advance_fourteen_avo == False)
                    print(f"Adelantos regulares encontrados: {len(adv_salary)}")
                    _logger.info("Adelantos regulares encontrados: %d", len(adv_salary))
                for adv_obj in adv_salary:
                    print(f"  -> Procesando adelanto ID={adv_obj.id}, Monto={adv_obj.advance}, Razón={adv_obj.reason}, 13avo={adv_obj.advance_thirteen_avo}, 14avo={adv_obj.advance_fourteen_avo}")
                    _logger.info("Procesando adelanto ID=%d, Monto=%s, Razón=%s, 13avo=%s, 14avo=%s", 
                                adv_obj.id, adv_obj.advance, adv_obj.reason, 
                                adv_obj.advance_thirteen_avo, adv_obj.advance_fourteen_avo)
                    current_date = payslip.date_from.month if payslip.date_from else None
                    date = adv_obj.date
                    existing_date = date.month if date else None
                    print(f"  -> Fechas: current_date.month={current_date}, existing_date.month={existing_date}")
                    _logger.info("Fechas: current_date.month=%s, existing_date.month=%s", current_date, existing_date)
                    
                    if adv_obj.advance_thirteen_avo:
                        print("  >>> Agregando adelanto 13avo")
                        _logger.info(">>> Agregando adelanto 13avo")
                        try:
                            input_type = payslip.env.ref('l10n_hn_salary_advance.payslip_input_type_advance_13avo')
                            input_line_vals.append(Command.create({
                                'name': adv_obj.reason,
                                'amount': adv_obj.advance,
                                'input_type_id': input_type.id,
                            }))
                            print(f"  >>> Tipo de entrada 13avo agregado exitosamente: ID={input_type.id}")
                            _logger.info("Tipo de entrada 13avo agregado exitosamente: ID=%d", input_type.id)
                        except ValueError as e:
                            print(f"  >>> ERROR al obtener tipo de entrada 13avo: {str(e)}")
                            _logger.error("Error al obtener tipo de entrada 13avo: %s", str(e))
                    elif adv_obj.advance_fourteen_avo:
                        print("  >>> Agregando adelanto 14avo")
                        _logger.info(">>> Agregando adelanto 14avo")
                        try:
                            input_type = payslip.env.ref('l10n_hn_salary_advance.payslip_input_type_advance_14avo')
                            input_line_vals.append(Command.create({
                                'name': adv_obj.reason,
                                'amount': adv_obj.advance,
                                'input_type_id': input_type.id,
                            }))
                            print(f"  >>> Tipo de entrada 14avo agregado exitosamente: ID={input_type.id}")
                            _logger.info("Tipo de entrada 14avo agregado exitosamente: ID=%d", input_type.id)
                        except ValueError as e:
                            print(f"  >>> ERROR al obtener tipo de entrada 14avo: {str(e)}")
                            _logger.error("Error al obtener tipo de entrada 14avo: %s", str(e))
                    else:
                        print("  >>> Procesando adelanto regular")
                        _logger.info(">>> Procesando adelanto regular")
                        if current_date and existing_date and current_date == existing_date:
                            print(f"  >>> Fechas coinciden, agregando adelanto regular")
                            _logger.info("Fechas coinciden, agregando adelanto regular")
                            try:
                                input_type = payslip.env.ref('l10n_hn_salary_advance.payslip_input_type_advance')
                                input_line_vals.append(Command.create({
                                    'name': adv_obj.reason,
                                    'amount': adv_obj.advance,
                                    'input_type_id': input_type.id,
                                }))
                                print(f"  >>> Tipo de entrada regular agregado exitosamente: ID={input_type.id}")
                                _logger.info("Tipo de entrada regular agregado exitosamente: ID=%d", input_type.id)
                            except ValueError as e:
                                print(f"  >>> ERROR al obtener tipo de entrada regular: {str(e)}")
                                _logger.error("Error al obtener tipo de entrada regular: %s", str(e))
                        else:
                            print(f"  >>> Fechas NO coinciden (current={current_date}, existing={existing_date}), NO se agrega adelanto")
                            _logger.info("Fechas NO coinciden (current=%s, existing=%s), NO se agrega adelanto", current_date, existing_date)

                print(f"Actualizando input_line_ids con {len(input_line_vals)} comando(s)")
                _logger.info("Actualizando input_line_ids con %d comando(s)", len(input_line_vals))
                payslip.update({'input_line_ids': input_line_vals})
                print(f"Nómina ID={payslip.id} actualizada exitosamente")
                _logger.info("Nómina ID=%d actualizada exitosamente", payslip.id)
            else:
                print(f"Nómina ID={payslip.id} sin empleado asociado")
                _logger.warning("Nómina ID=%d sin empleado asociado", payslip.id)
                payslip.update({'input_line_ids': input_line_vals})
        print("=== FIN _compute_input_line_ids ===")
        print("=" * 80)
        _logger.info("=== FIN _compute_input_line_ids ===")

    @api.model
    def _get_attachment_types_advance(self):
        try:
            return {
                'load': self.env.ref('l10n_hn_salary_advance.payslip_input_type_advance'),
            }
        except ValueError:
            # Si el registro no existe, retornar un diccionario vacío
            return {}
