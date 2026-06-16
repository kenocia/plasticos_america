# -*- coding: utf-8 -*-

import datetime
import base64
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SecurePortalExpenseController(http.Controller):
    """Controlador seguro para gastos en el portal"""

    def _get_current_employee(self):
        """Obtiene el empleado actual del usuario portal con validaciones de seguridad"""
        user = request.env.user
        
        # Verificar que el usuario tenga permisos de portal
        if not user.has_group('base.group_portal'):
            raise AccessError("Solo los usuarios del portal pueden acceder a esta funcionalidad")
        
        # Obtener empleado asociado al usuario
        employee = user.partner_id.employee_ids.filtered(
            lambda e: e.company_id == user.company_id and e.active
        )
        
        if not employee:
            raise UserError("No se encontró un empleado activo asociado a su usuario")
        
        if len(employee) > 1:
            _logger.warning(f"Usuario {user.id} tiene múltiples empleados activos")
            employee = employee[0]  # Tomar el primero
        
        return employee

    def _validate_expense_data(self, expense_data):
        """Valida los datos del gasto antes de procesarlos"""
        required_fields = ['name', 'date', 'total_amount_currency', 'payment_mode', 'description']
        
        for field in required_fields:
            if not expense_data.get(field):
                raise ValidationError(f"El campo {field} es obligatorio")
        
        # Validar fecha
        try:
            expense_date = fields.Date.from_string(expense_data['date'])
            if expense_date > fields.Date.today():
                raise ValidationError("La fecha del gasto no puede ser futura")
        except ValueError:
            raise ValidationError("Formato de fecha inválido")
        
        # Validar monto
        try:
            amount = float(expense_data['total_amount_currency'])
            if amount <= 0:
                raise ValidationError("El monto debe ser mayor a 0")
            if amount > 1000000:  # Límite de seguridad
                raise ValidationError("El monto excede el límite permitido")
        except (ValueError, TypeError):
            raise ValidationError("Monto inválido")
        
        # Validar modo de pago
        valid_payment_modes = ['own_account', 'company_account', 'viatic']
        if expense_data['payment_mode'] not in valid_payment_modes:
            raise ValidationError("Modo de pago inválido")
        
        return True

    def _process_attachments(self, attachments_data):
        """Procesa archivos adjuntos de forma segura"""
        processed_attachments = []
        
        for attachment in attachments_data:
            if not attachment.get('data') or not attachment.get('name'):
                continue
                
            # Validar tipo de archivo
            allowed_types = ['image/jpeg', 'image/png', 'application/pdf', 'image/gif']
            if attachment.get('type') not in allowed_types:
                _logger.warning(f"Tipo de archivo no permitido: {attachment.get('type')}")
                continue
            
            # Validar tamaño (máximo 10MB)
            try:
                import base64
                file_data = base64.b64decode(attachment['data'].split(',')[1])
                if len(file_data) > 10 * 1024 * 1024:  # 10MB
                    _logger.warning(f"Archivo muy grande: {attachment.get('name')}")
                    continue
            except Exception as e:
                _logger.error(f"Error procesando archivo {attachment.get('name')}: {e}")
                continue
            
            processed_attachments.append({
                'name': attachment['name'],
                'datas': attachment['data'],
                'type': 'binary',
                'res_model': 'hr.expense',
            })
        
        return processed_attachments

    @http.route(['/my/expense/list'], type='http', auth="user", website=True)
    def portal_expense_list(self, page=0, **kwargs):
        """Lista de gastos del empleado con validaciones de seguridad"""
        try:
            employee = self._get_current_employee()
            
            # Parámetros de paginación
            items_per_page = 20  # Reducido para mejor rendimiento
            page = max(0, int(page))
            
            # Obtener gastos del empleado
            domain = [
                ('employee_id', '=', employee.id),
                ('company_id', '=', employee.company_id.id)
            ]
            
            total_items = request.env['hr.expense'].search_count(domain)
            total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 0
            
            # Obtener gastos con offset y limit
            expenses = request.env['hr.expense'].search(
                domain,
                offset=page * items_per_page,
                limit=items_per_page,
                order='date desc'
            )
            
            return request.render('hr_hn_portal_expense.template_list_of_expense', {
                'items': expenses,
                'page': page,
                'total_pages': total_pages,
                'employee': employee,
            })
            
        except (AccessError, UserError) as e:
            return request.render('http_routing.403', {'message': str(e)})
        except Exception as e:
            _logger.error(f"Error en portal_expense_list: {e}")
            return request.render('http_routing.500', {'message': 'Error interno del servidor'})

    @http.route('/safe_hr_expense', methods=["POST"], type="json", auth="user", website=True)
    def create_expenses(self, expense_list):
        """Crea gastos de forma segura"""
        try:
            employee = self._get_current_employee()
            
            if not isinstance(expense_list, list):
                raise ValidationError("Formato de datos inválido")
            
            if len(expense_list) > 50:  # Límite de seguridad
                raise ValidationError("Demasiados gastos en una sola solicitud")
            
            created_expenses = []
            
            for expense_data in expense_list:
                # Validar datos
                self._validate_expense_data(expense_data)
                
                # Preparar datos para crear el gasto
                expense_vals = {
                    'name': expense_data['name'],
                    'date': expense_data['date'],
                    'total_amount_currency': float(expense_data['total_amount_currency']),
                    'payment_mode': expense_data['payment_mode'],
                    'description': expense_data['description'],
                    'employee_id': employee.id,
                    'company_id': employee.company_id.id,
                    'state': 'draft',
                }
                
                # Agregar producto si existe
                if expense_data.get('product_id'):
                    try:
                        product_id = int(expense_data['product_id'])
                        product = request.env['product.product'].browse(product_id)
                        if product.exists() and product.company_id in (False, employee.company_id):
                            expense_vals['product_id'] = product_id
                    except (ValueError, TypeError):
                        pass  # Ignorar si el producto no es válido
                
                # Crear el gasto
                expense = request.env['hr.expense'].create(expense_vals)
                
                # Procesar archivos adjuntos
                if expense_data.get('archivo_adjunto'):
                    attachments = self._process_attachments(expense_data['archivo_adjunto'])
                    for attachment_data in attachments:
                        attachment_data['res_id'] = expense.id
                        request.env['ir.attachment'].create(attachment_data)
                
                created_expenses.append(expense.id)
            
            return {
                'success': True,
                'message': f'Se crearon {len(created_expenses)} gastos correctamente',
                'expense_ids': created_expenses
            }
            
        except (AccessError, UserError, ValidationError) as e:
            return {
                'success': False,
                'message': str(e)
            }
        except Exception as e:
            _logger.error(f"Error en create_expenses: {e}")
            return {
                'success': False,
                'message': 'Error interno del servidor'
            }

    @http.route('/get_value_of_product', type='json', auth="user", website=True)
    def get_product_info(self, product_id):
        """Obtiene información del producto de forma segura"""
        try:
            employee = self._get_current_employee()
            
            if not product_id:
                return {'quantity': False, 'unit_price': 0}
            
            product = request.env['product.product'].browse(int(product_id))
            
            if not product.exists():
                return {'quantity': False, 'unit_price': 0}
            
            # Verificar que el producto pertenezca a la misma empresa
            if product.company_id and product.company_id != employee.company_id:
                return {'quantity': False, 'unit_price': 0}
            
            return {
                'quantity': product.can_be_expensed,
                'unit_price': product.list_price
            }
            
        except Exception as e:
            _logger.error(f"Error en get_product_info: {e}")
            return {'quantity': False, 'unit_price': 0}
