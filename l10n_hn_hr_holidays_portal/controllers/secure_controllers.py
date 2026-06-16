# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, UserError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SecurePortalLeaveController(http.Controller):
    """Controlador seguro para ausencias en el portal"""

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

    def _validate_leave_data(self, leave_data):
        """Valida los datos de la ausencia antes de procesarlos"""
        required_fields = ['holiday_status_id', 'employee_id', 'date_from', 'date_to']
        
        for field in required_fields:
            if not leave_data.get(field):
                raise ValidationError(f"El campo {field} es obligatorio")
        
        # Validar fechas
        try:
            date_from = fields.Date.from_string(leave_data['date_from'])
            date_to = fields.Date.from_string(leave_data['date_to'])
            
            if date_from > date_to:
                raise ValidationError("La fecha de inicio debe ser anterior a la fecha de fin")
            
            if date_from < fields.Date.today():
                raise ValidationError("No se pueden solicitar ausencias para fechas pasadas")
            
            # Validar que no sea más de 1 año en el futuro
            max_future_date = fields.Date.today() + timedelta(days=365)
            if date_from > max_future_date:
                raise ValidationError("No se pueden solicitar ausencias con más de 1 año de anticipación")
            
        except ValueError:
            raise ValidationError("Formato de fecha inválido")
        
        # Validar tipo de ausencia
        try:
            leave_type_id = int(leave_data['holiday_status_id'])
            leave_type = request.env['hr.leave.type'].browse(leave_type_id)
            
            if not leave_type.exists():
                raise ValidationError("Tipo de ausencia inválido")
            
            if not leave_type.active:
                raise ValidationError("El tipo de ausencia seleccionado no está activo")
                
        except (ValueError, TypeError):
            raise ValidationError("Tipo de ausencia inválido")
        
        # Validar empleado
        try:
            employee_id = int(leave_data['employee_id'])
            employee = request.env['hr.employee'].browse(employee_id)
            
            if not employee.exists():
                raise ValidationError("Empleado inválido")
            
            if not employee.active:
                raise ValidationError("El empleado seleccionado no está activo")
                
        except (ValueError, TypeError):
            raise ValidationError("Empleado inválido")
        
        return True

    def _check_leave_availability(self, employee, leave_type, date_from, date_to):
        """Verifica la disponibilidad de días para el tipo de ausencia"""
        try:
            # Verificar días disponibles
            remaining_leaves = leave_type.get_employees_days(employee.ids)[employee.id]
            
            if remaining_leaves['remaining_leaves'] <= 0:
                raise ValidationError(f"No tiene días disponibles para {leave_type.name}")
            
            # Verificar que no haya conflictos con ausencias existentes
            existing_leaves = request.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['confirm', 'validate1', 'validate']),
                ('date_from', '<=', date_to),
                ('date_to', '>=', date_from)
            ])
            
            if existing_leaves:
                raise ValidationError("Ya tiene una ausencia aprobada en el período seleccionado")
                
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            _logger.error(f"Error verificando disponibilidad: {e}")
            raise ValidationError("Error verificando disponibilidad de días")

    @http.route('/my/leaves', type='http', auth='user', website=True)
    def portal_leave_list(self, page=0, **kwargs):
        """Lista de ausencias del empleado con validaciones de seguridad"""
        try:
            employee = self._get_current_employee()
            
            # Parámetros de paginación
            items_per_page = 20
            page = max(0, int(page))
            
            # Obtener ausencias del empleado
            domain = [
                ('employee_id', '=', employee.id),
                ('company_id', '=', employee.company_id.id)
            ]
            
            total_items = request.env['hr.leave'].search_count(domain)
            total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 0
            
            # Obtener ausencias con offset y limit
            leaves = request.env['hr.leave'].search(
                domain,
                offset=page * items_per_page,
                limit=items_per_page,
                order='date_from desc'
            )
            
            return request.render('l10n_hn_hr_holidays_portal.portal_my_leaves', {
                'leaves': leaves,
                'page': page,
                'total_pages': total_pages,
                'employee': employee,
            })
            
        except (AccessError, UserError) as e:
            return request.render('http_routing.403', {'message': str(e)})
        except Exception as e:
            _logger.error(f"Error en portal_leave_list: {e}")
            return request.render('http_routing.500', {'message': 'Error interno del servidor'})

    @http.route('/safe_hr_leave', methods=["POST"], type="json", auth="user", website=True)
    def create_leave_request(self, leave):
        """Crea solicitud de ausencia de forma segura"""
        try:
            employee = self._get_current_employee()
            
            if not isinstance(leave, dict):
                raise ValidationError("Formato de datos inválido")
            
            # Validar datos
            self._validate_leave_data(leave)
            
            # Obtener objetos necesarios
            leave_type = request.env['hr.leave.type'].browse(int(leave['holiday_status_id']))
            employee_obj = request.env['hr.employee'].browse(int(leave['employee_id']))
            date_from = fields.Date.from_string(leave['date_from'])
            date_to = fields.Date.from_string(leave['date_to'])
            
            # Verificar que el empleado sea el mismo que el usuario actual
            if employee_obj != employee:
                raise AccessError("No puede crear ausencias para otros empleados")
            
            # Verificar disponibilidad
            self._check_leave_availability(employee_obj, leave_type, date_from, date_to)
            
            # Crear la solicitud de ausencia
            leave_vals = {
                'name': leave.get('name', f'{leave_type.name} - {date_from}'),
                'holiday_status_id': leave_type.id,
                'employee_id': employee_obj.id,
                'date_from': date_from,
                'date_to': date_to,
                'state': 'draft',
                'company_id': employee.company_id.id,
            }
            
            leave_request = request.env['hr.leave'].create(leave_vals)
            
            return {
                'success': True,
                'message': 'Solicitud de ausencia creada correctamente',
                'leave_id': leave_request.id
            }
            
        except (AccessError, UserError, ValidationError) as e:
            return {
                'success': False,
                'message': str(e)
            }
        except Exception as e:
            _logger.error(f"Error en create_leave_request: {e}")
            return {
                'success': False,
                'message': 'Error interno del servidor'
            }

    @http.route('/get_leave_types', type='json', auth="user", website=True)
    def get_leave_types(self):
        """Obtiene tipos de ausencia disponibles de forma segura"""
        try:
            employee = self._get_current_employee()
            
            leave_types = request.env['hr.leave.type'].search([
                ('active', '=', True),
                '|', ('company_id', '=', False), ('company_id', '=', employee.company_id.id)
            ])
            
            return [{
                'id': lt.id,
                'name': lt.name,
                'allocation_type': lt.allocation_type,
                'requires_allocation': lt.requires_allocation
            } for lt in leave_types]
            
        except Exception as e:
            _logger.error(f"Error en get_leave_types: {e}")
            return []

    @http.route('/get_employees', type='json', auth="user", website=True)
    def get_employees(self):
        """Obtiene empleados disponibles de forma segura"""
        try:
            employee = self._get_current_employee()
            
            # Solo devolver el empleado actual para usuarios portal
            return [{
                'id': employee.id,
                'name': employee.name
            }]
            
        except Exception as e:
            _logger.error(f"Error en get_employees: {e}")
            return []

    @http.route('/get_user', type='json', auth="user", website=True)
    def get_current_user_employee(self):
        """Obtiene el ID del empleado del usuario actual"""
        try:
            employee = self._get_current_employee()
            return employee.id
        except Exception as e:
            _logger.error(f"Error en get_current_user_employee: {e}")
            return None
