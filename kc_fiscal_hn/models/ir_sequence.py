# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
from datetime import datetime, timedelta


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    # Campos para control fiscal
    is_fiscal = fields.Boolean(string='Es Secuencia Fiscal', default=False)
    fiscal_type = fields.Selection([
        ('invoice', 'Factura'),
        ('credit_note', 'Nota de Crédito'),
        ('debit_note', 'Nota de Débito'),
        ('receipt', 'Recibo'),
        ('retention', 'Retención'),
        ('other', 'Otro')
    ], string='Tipo Fiscal', default='invoice')
    
    # Campos de alerta
    dias_alerta = fields.Integer(string='Días de Alerta', default=30)
    numeros_alerta = fields.Integer(string='Números de Alerta', default=100)
    
    # Campos de validación fiscal
    fiscal_sequence_validated = fields.Boolean(string='Secuencia Fiscal Validada', default=False)
    fiscal_validation_date = fields.Datetime(string='Fecha de Validación Fiscal', readonly=True)
    fiscal_validation_error = fields.Text(string='Error de Validación Fiscal', readonly=True)
    
    # Control de rangos
    fiscal_range_start = fields.Integer(string='Inicio de Rango Fiscal')
    fiscal_range_end = fields.Integer(string='Fin de Rango Fiscal')
    current_fiscal_number = fields.Integer(string='Número Fiscal Actual', compute='_compute_current_fiscal_number', store=True)
    
    # Alertas y validaciones
    alert_threshold = fields.Integer(string='Umbral de Alerta (%)', default=80, 
                                   help='Porcentaje del rango usado para generar alertas')
    warning_threshold = fields.Integer(string='Umbral de Advertencia (%)', default=90,
                                     help='Porcentaje del rango usado para generar advertencias')
    auto_alert = fields.Boolean(string='Alertas Automáticas', default=True)
    
    # Control de uso
    fiscal_usage_count = fields.Integer(string='Cantidad Usada', compute='_compute_fiscal_usage', store=True)
    fiscal_usage_percentage = fields.Float(string='Porcentaje Usado (%)', compute='_compute_fiscal_usage', store=True)
    last_used_date = fields.Date(string='Última Fecha de Uso', compute='_compute_last_used_date', store=True)
    
    # Validaciones SAR
    requires_cai = fields.Boolean(string='Requiere CAI', default=True)
    cai_validation = fields.Boolean(string='Validar CAI', default=True)
    rtn_validation = fields.Boolean(string='Validar RTN', default=True)
    
    # Campos para reportes
    fiscal_status = fields.Selection([
        ('active', 'Activo'),
        ('warning', 'Advertencia'),
        ('critical', 'Crítico'),
        ('expired', 'Expirado')
    ], string='Estado Fiscal', compute='_compute_fiscal_status', store=True)
    
    @api.depends('fiscal_range_start', 'fiscal_range_end', 'number_next_actual')
    def _compute_current_fiscal_number(self):
        """Calcular el número fiscal actual"""
        for sequence in self:
            if sequence.fiscal_range_start and sequence.fiscal_range_end:
                sequence.current_fiscal_number = sequence.number_next_actual
            else:
                sequence.current_fiscal_number = 0
    
    @api.depends('fiscal_range_start', 'fiscal_range_end', 'number_next_actual')
    def _compute_fiscal_usage(self):
        """Calcular el uso de la secuencia fiscal"""
        for sequence in self:
            if sequence.fiscal_range_start and sequence.fiscal_range_end:
                total_range = sequence.fiscal_range_end - sequence.fiscal_range_start + 1
                used_range = sequence.number_next_actual - sequence.fiscal_range_start
                sequence.fiscal_usage_count = max(0, used_range)
                sequence.fiscal_usage_percentage = (used_range / total_range * 100) if total_range > 0 else 0
            else:
                sequence.fiscal_usage_count = 0
                sequence.fiscal_usage_percentage = 0
    
    @api.depends('number_next_actual')
    def _compute_last_used_date(self):
        """Calcular la última fecha de uso"""
        for sequence in self:
            # Buscar el último uso en las facturas
            last_invoice = self.env['account.move'].search([
                ('name', 'like', f'%{sequence.prefix}%'),
                ('state', 'in', ['posted', 'cancel'])
            ], order='date desc', limit=1)
            
            sequence.last_used_date = last_invoice.date if last_invoice else False
    
    @api.depends('fiscal_usage_percentage', 'fiscal_range_end', 'number_next_actual')
    def _compute_fiscal_status(self):
        """Calcular el estado fiscal de la secuencia"""
        for sequence in self:
            if not sequence.is_fiscal:
                sequence.fiscal_status = 'active'
                continue
                
            if sequence.fiscal_range_end and sequence.number_next_actual > sequence.fiscal_range_end:
                sequence.fiscal_status = 'expired'
            elif sequence.fiscal_usage_percentage >= sequence.warning_threshold:
                sequence.fiscal_status = 'critical'
            elif sequence.fiscal_usage_percentage >= sequence.alert_threshold:
                sequence.fiscal_status = 'warning'
            else:
                sequence.fiscal_status = 'active'
    
    @api.constrains('fiscal_range_start', 'fiscal_range_end')
    def _check_fiscal_range(self):
        """Validar que el rango fiscal sea válido"""
        for sequence in self:
            if sequence.fiscal_range_start and sequence.fiscal_range_end:
                if sequence.fiscal_range_start >= sequence.fiscal_range_end:
                    raise ValidationError(_('El inicio del rango fiscal debe ser menor al final'))
                
                if sequence.fiscal_range_start < 1:
                    raise ValidationError(_('El inicio del rango fiscal debe ser mayor a 0'))
    
    @api.constrains('alert_threshold', 'warning_threshold')
    def _check_thresholds(self):
        """Validar que los umbrales sean válidos"""
        for sequence in self:
            if sequence.alert_threshold and sequence.warning_threshold:
                if sequence.alert_threshold >= sequence.warning_threshold:
                    raise ValidationError(_('El umbral de alerta debe ser menor al umbral de advertencia'))
                
                if sequence.alert_threshold < 0 or sequence.alert_threshold > 100:
                    raise ValidationError(_('El umbral de alerta debe estar entre 0 y 100'))
                
                if sequence.warning_threshold < 0 or sequence.warning_threshold > 100:
                    raise ValidationError(_('El umbral de advertencia debe estar entre 0 y 100'))
    
    def action_check_fiscal_sequences(self):
        """Verificar el estado de todas las secuencias fiscales"""
        self.ensure_one()
        
        sequences = self.search([('is_fiscal', '=', True)])
        alerts = []
        
        for sequence in sequences:
            if sequence.fiscal_status == 'critical':
                alerts.append({
                    'sequence': sequence,
                    'type': 'critical',
                    'message': f'La secuencia {sequence.name} está en estado crítico ({sequence.fiscal_usage_percentage:.1f}% usado)'
                })
            elif sequence.fiscal_status == 'warning':
                alerts.append({
                    'sequence': sequence,
                    'type': 'warning',
                    'message': f'La secuencia {sequence.name} está en advertencia ({sequence.fiscal_usage_percentage:.1f}% usado)'
                })
            elif sequence.fiscal_status == 'expired':
                alerts.append({
                    'sequence': sequence,
                    'type': 'expired',
                    'message': f'La secuencia {sequence.name} ha expirado'
                })
        
        if alerts:
            return self._show_sequence_alerts(alerts)
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Verificación Completada'),
                    'message': _('Todas las secuencias fiscales están en buen estado'),
                    'type': 'success',
                }
            }
    
    def _show_sequence_alerts(self, alerts):
        """Mostrar alertas de secuencias"""
        return {
            'name': _('Alertas de Secuencias Fiscales'),
            'type': 'ir.actions.act_window',
            'res_model': 'kc_fiscal_hn.wizard.sequence_alerts',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_alerts': str(alerts),
                'default_alert_count': len(alerts)
            }
        }
    
    def action_reset_fiscal_sequence(self):
        """Reiniciar secuencia fiscal"""
        self.ensure_one()
        
        if not self.is_fiscal:
            raise ValidationError(_('Esta secuencia no es fiscal'))
        
        return {
            'name': _('Reiniciar Secuencia Fiscal'),
            'type': 'ir.actions.act_window',
            'res_model': 'kc_fiscal_hn.wizard.reset_sequence',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sequence_id': self.id,
                'default_current_number': self.number_next_actual,
                'default_fiscal_range_start': self.fiscal_range_start,
                'default_fiscal_range_end': self.fiscal_range_end
            }
        }
    
    def action_view_fiscal_usage(self):
        """Ver el uso de la secuencia fiscal"""
        self.ensure_one()
        
        if not self.is_fiscal:
            raise ValidationError(_('Esta secuencia no es fiscal'))
        
        # Buscar documentos que usan esta secuencia
        domain = [
            ('name', 'like', f'%{self.prefix}%'),
            ('state', 'in', ['posted', 'cancel'])
        ]
        
        return {
            'name': _('Uso de Secuencia Fiscal'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'default_name': self.prefix,
                'search_default_fiscal_sequence': True
            }
        }
    
    def get_next_fiscal_number(self):
        """Obtener el próximo número fiscal con validaciones"""
        self.ensure_one()
        
        if not self.is_fiscal:
            return self._next()
        
        # Validar que no haya expirado
        if self.fiscal_status == 'expired':
            raise ValidationError(_(f'La secuencia fiscal {self.name} ha expirado. Contacte al administrador.'))
        
        # Validar que esté dentro del rango
        if self.fiscal_range_end and self.number_next_actual > self.fiscal_range_end:
            raise ValidationError(_(f'La secuencia fiscal {self.name} ha excedido su rango máximo.'))
        
        # Generar alertas si es necesario
        if self.auto_alert and self.fiscal_status in ['warning', 'critical']:
            self._generate_sequence_alert()
        
        return self._next()
    
    def _generate_sequence_alert(self):
        """Generar alerta automática para la secuencia"""
        self.ensure_one()
        
        # Crear alerta en el sistema
        self.env['kc_fiscal_hn.sequence.alert'].create({
            'sequence_id': self.id,
            'alert_type': self.fiscal_status,
            'message': f'La secuencia {self.name} está en estado {self.fiscal_status} ({self.fiscal_usage_percentage:.1f}% usado)',
            'usage_percentage': self.fiscal_usage_percentage,
            'current_number': self.number_next_actual,
            'range_start': self.fiscal_range_start,
            'range_end': self.fiscal_range_end
        })
    
    @api.model_create_multi
    def create(self, vals_list):
        """Crear secuencias con validaciones fiscales"""
        sequences = super().create(vals_list)
        
        for sequence in sequences:
            if sequence.is_fiscal:
                sequence._validate_fiscal_sequence()
        
        return sequences
    
    def write(self, vals):
        """Escribir secuencia con validaciones fiscales"""
        result = super().write(vals)
        
        for sequence in self:
            if sequence.is_fiscal:
                sequence._validate_fiscal_sequence()
        
        return result
    
    def _validate_fiscal_sequence(self):
        """Validar configuración básica de secuencia fiscal"""
        self.ensure_one()
        
        # Validar prefijo (solo una vez)
        if not self.prefix or len(self.prefix.strip()) == 0:
            raise ValidationError(_('Las secuencias fiscales deben tener un prefijo válido'))
    
    def _validate_fiscal_ranges(self):
        """Validar rangos fiscales de la secuencia"""
        self.ensure_one()
        
        # Si usa rangos de fecha, validar que existan rangos de fecha con CAI
        if self.use_date_range:
            # Buscar rangos de fecha que tengan CAI y rangos definidos
            date_ranges = self.date_range_ids.filtered(lambda r: r.cai and r.rangoInicial and r.rangoFinal)
            
            if not date_ranges:
                raise ValidationError(_('Las secuencias fiscales con rangos de fecha deben tener al menos un rango con CAI y rangos definidos'))
            
            # Validar que los rangos de fecha sean válidos
            for date_range in date_ranges:
                if date_range.rangoInicial >= date_range.rangoFinal:
                    raise ValidationError(_('El rango inicial debe ser menor al rango final en el rango de fecha'))
                
                # # Validar que el CAI tenga formato válido
                # if date_range.cai and not re.match(r'^[A-Z0-9]{37}$', date_range.cai):
                #     raise ValidationError(_('El CAI debe tener 37 caracteres alfanuméricos'))
                
                # Validar que las fechas del rango sean válidas (usando date_from y date_to de Odoo)
                if date_range.date_from and date_range.date_to:
                    if date_range.date_from >= date_range.date_to:
                        raise ValidationError(_('La fecha de inicio debe ser menor a la fecha de fin en el rango de fecha'))
        else:
            # Si no usa rangos de fecha, validar los rangos de la secuencia principal
            if not self.fiscal_range_start or not self.fiscal_range_end:
                raise ValidationError(_('Las secuencias fiscales deben tener un rango definido'))
            
            if self.fiscal_range_start >= self.fiscal_range_end:
                raise ValidationError(_('El rango inicial debe ser menor al rango final'))
    
    def _validate_date_range_current(self):
        """Validar que exista un rango de fecha válido para el período actual"""
        self.ensure_one()
        
        if not self.use_date_range:
            return True
        
        # Buscar rango de fecha para hoy
        current_date_range = self.date_range_ids.filtered(lambda r: r.date_from <= fields.Date.today() <= r.date_to)
        if not current_date_range:
            # Si no hay rango para hoy, buscar el más reciente
            current_date_range = self.date_range_ids.filtered(lambda r: r.date_to >= fields.Date.today()).sorted('date_to', reverse=True)
        
        if not current_date_range:
            raise ValidationError(_('No hay rangos de fecha válidos para el período actual'))
        
        # Validar que el rango de fecha actual tenga CAI y rangos válidos
        current_range = current_date_range[0]
        if not current_range.cai:
            raise ValidationError(_('El rango de fecha actual no tiene CAI configurado'))
        
        if not current_range.rangoInicial or not current_range.rangoFinal:
            raise ValidationError(_('El rango de fecha actual no tiene rangos inicial y final configurados'))
        
        if current_range.rangoInicial >= current_range.rangoFinal:
            raise ValidationError(_('El rango inicial debe ser menor al rango final en el período actual'))
        
        return True
    
    def _validate_sequence_numbers(self):
        """Validar que el número actual esté dentro del rango fiscal"""
        self.ensure_one()
        
        if not self.use_date_range:
            # Para rangos de secuencia principal
            if self.number_next_actual < self.fiscal_range_start:
                raise ValidationError(_('El número actual está por debajo del rango fiscal'))
            
            if self.fiscal_range_end and self.number_next_actual > self.fiscal_range_end:
                raise ValidationError(_('El número actual está por encima del rango fiscal'))
        
        return True
    
    def _clear_validation_state(self):
        """Limpiar estado de validación"""
        self.write({
            'fiscal_sequence_validated': False,
            'fiscal_validation_date': fields.Datetime.now(),
            'fiscal_validation_error': False
        })
    
    def _set_validation_success(self):
        """Marcar validación como exitosa"""
        self.write({
            'fiscal_sequence_validated': True,
            'fiscal_validation_date': fields.Datetime.now(),
            'fiscal_validation_error': False
        })
    
    def _set_validation_error(self, error_message):
        """Marcar validación como fallida"""
        self.write({
            'fiscal_sequence_validated': False,
            'fiscal_validation_date': fields.Datetime.now(),
            'fiscal_validation_error': error_message
        })
    
    def _return_validation_result(self, success=True, title='', message='', error_message=''):
        """Retornar resultado de validación estandarizado"""
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': message,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': error_message,
                    'type': 'danger',
                }
            }
    
    def validate_fiscal_sequence_complete(self):
        """Validar secuencia fiscal completa"""
        self.ensure_one()
        
        # Limpiar estado anterior
        self._clear_validation_state()
        
        try:
            # Validar configuración básica
            self._validate_fiscal_sequence()
            
            # Validar rangos fiscales
            self._validate_fiscal_ranges()
            
            # Validar que el número actual esté dentro del rango
            self._validate_sequence_numbers()
            
            # Validar que exista un rango de fecha válido para el período actual
            self._validate_date_range_current()
            
            # Si llegamos aquí, la validación fue exitosa
            self._set_validation_success()
            
            return self._return_validation_result(title=_('Validación Exitosa'), message=_('La secuencia fiscal ha sido validada correctamente'))
            
        except Exception as e:
            # Si hay error, guardar el error y devolver mensaje de error
            self._set_validation_error(str(e))
            
            return self._return_validation_result(title=_('Error de Validación'), error_message=str(e))
    
    def validate_fiscal_sequence_simple(self):
        """Validación simple para diagnosticar problemas"""
        self.ensure_one()
        
        # Limpiar estado anterior
        self._clear_validation_state()
        
        try:
            # Verificar si usa rangos de fecha
            if self.use_date_range:
                # Contar rangos de fecha con CAI y rangos
                valid_ranges = self.date_range_ids.filtered(lambda r: r.cai and r.rangoInicial and r.rangoFinal)
                
                if len(valid_ranges) == 0:
                    raise ValidationError(_('No hay rangos de fecha con CAI y rangos definidos'))
                
                # Marcar como válida
                self._set_validation_success()
                
                return self._return_validation_result(title=_('Validación Simple Exitosa'), message=_('La secuencia fiscal ha sido validada correctamente'))
            else:
                raise ValidationError(_('Esta secuencia no usa rangos de fecha'))
                
        except Exception as e:
            self._set_validation_error(str(e))
            
            return self._return_validation_result(title=_('Error de Validación Simple'), error_message=str(e))
    
    def get_fiscal_dashboard_data(self):
        """Obtener datos para el dashboard fiscal"""
        sequences = self.search([('is_fiscal', '=', True)])
        
        total_sequences = len(sequences)
        active_sequences = len(sequences.filtered(lambda s: s.fiscal_status == 'active'))
        warning_sequences = len(sequences.filtered(lambda s: s.fiscal_status == 'warning'))
        critical_sequences = len(sequences.filtered(lambda s: s.fiscal_status == 'critical'))
        expired_sequences = len(sequences.filtered(lambda s: s.fiscal_status == 'expired'))
        
        # Calcular uso total
        total_usage = sum(sequences.mapped('fiscal_usage_count'))
        total_range = sum([(s.fiscal_range_end - s.fiscal_range_start + 1) for s in sequences if s.fiscal_range_start and s.fiscal_range_end])
        overall_usage_percentage = (total_usage / total_range * 100) if total_range > 0 else 0
        
        return {
            'total_sequences': total_sequences,
            'active_sequences': active_sequences,
            'warning_sequences': warning_sequences,
            'critical_sequences': critical_sequences,
            'expired_sequences': expired_sequences,
            'overall_usage_percentage': overall_usage_percentage,
            'sequences': sequences
        }
    
    def validate_fiscal_sequence_date_ranges(self):
        """Validar específicamente secuencias con rangos de fecha"""
        self.ensure_one()
        
        if not self.use_date_range:
            raise ValidationError(_('Esta secuencia no usa rangos de fecha'))
        
        # Limpiar estado anterior
        self._clear_validation_state()
        
        try:
            # Validar que existan rangos de fecha
            if not self.date_range_ids:
                raise ValidationError(_('No hay rangos de fecha configurados'))
            
            # Validar que al menos un rango tenga CAI y rangos válidos
            valid_ranges = self.date_range_ids.filtered(lambda r: r.cai and r.rangoInicial and r.rangoFinal)
            
            if not valid_ranges:
                raise ValidationError(_('No hay rangos de fecha con CAI y rangos definidos'))
            
            # Validar que exista un rango para el período actual o futuro
            today = fields.Date.today()
            current_or_future_ranges = self.date_range_ids.filtered(lambda r: r.date_to >= today)
            
            if not current_or_future_ranges:
                raise ValidationError(_('No hay rangos de fecha válidos para el período actual o futuro'))
            
            # Validar cada rango (usar la función centralizada)
            for date_range in valid_ranges:
                if date_range.rangoInicial >= date_range.rangoFinal:
                    raise ValidationError(_(f'El rango inicial debe ser menor al rango final en el rango de fecha {date_range.date_from} - {date_range.date_to}'))
                
                if date_range.cai and not re.match(r'^[A-Z0-9]{37}$', date_range.cai):
                    raise ValidationError(_(f'El CAI del rango {date_range.date_from} - {date_range.date_to} debe tener 37 caracteres alfanuméricos'))
                
                if date_range.date_from and date_range.date_to:
                    if date_range.date_from >= date_range.date_to:
                        raise ValidationError(_(f'El rango {date_range.date_from} - {date_range.date_to} tiene una fecha de inicio mayor o igual a la fecha de fin'))
            
            # Marcar como válida
            self._set_validation_success()
            
            return self._return_validation_result(title=_('Validación de Rangos de Fecha Exitosa'), message=_('Los rangos de fecha de la secuencia fiscal han sido validados correctamente'))
            
        except Exception as e:
            self._set_validation_error(str(e))
            
            return self._return_validation_result(title=_('Error de Validación de Rangos de Fecha'), error_message=str(e))

    def get_available_future_ranges(self, current_date=None):
        """
        Obtener rangos de fecha futuros disponibles que permitan continuar operaciones
        """
        self.ensure_one()
        
        if not self.use_date_range:
            return self.env['ir.sequence.date_range']
        
        if not current_date:
            current_date = fields.Date.today()
        
        # Buscar rangos futuros que tengan CAI y rangos válidos
        future_ranges = self.date_range_ids.filtered(lambda r: 
            r.cai and 
            r.rangoInicial and 
            r.rangoFinal and
            r.rangoInicial < r.rangoFinal and
            r.date_from and 
            r.date_to and
            r.date_from < r.date_to and
            (
                r.date_from > current_date or  # Fecha posterior
                (r.date_from <= current_date <= r.date_to)  # Incluye fecha actual
            )
        ).sorted('date_from')
        
        return future_ranges
    
    def has_valid_future_sequences(self, current_date=None):
        """
        Verificar si existen subsecuencias futuras válidas que permitan continuar operaciones
        """
        self.ensure_one()
        
        if not self.use_date_range:
            return True
        
        future_ranges = self.get_available_future_ranges(current_date)
        return len(future_ranges) > 0
    
    def get_next_available_range(self, current_date=None):
        """
        Obtener el siguiente rango de fecha disponible
        """
        self.ensure_one()
        
        if not self.use_date_range:
            return False
        
        if not current_date:
            current_date = fields.Date.today()
        
        # Buscar el siguiente rango válido
        next_range = self.date_range_ids.filtered(lambda r: 
            r.cai and 
            r.rangoInicial and 
            r.rangoFinal and
            r.rangoInicial < r.rangoFinal and
            r.date_from and 
            r.date_to and
            r.date_from < r.date_to and
            r.date_from > current_date
        ).sorted('date_from')
        
        return next_range[0] if next_range else False
    
    def validate_sequence_continuity(self, current_date=None):
        """
        Validar continuidad de la secuencia fiscal, permitiendo operaciones si hay subsecuencias futuras
        """
        self.ensure_one()
        
        if not self.use_date_range:
            return {'valid': True, 'message': '', 'can_continue': True}
        
        if not current_date:
            current_date = fields.Date.today()
        
        # Obtener rango actual
        current_range = self.date_range_ids.filtered(lambda r: 
            r.date_from <= current_date <= r.date_to
        )
        
        if not current_range:
            # Buscar rango futuro más cercano
            future_range = self.get_next_available_range(current_date)
            if future_range:
                return {
                    'valid': True, 
                    'message': f'No hay rango para la fecha actual, pero existe rango futuro desde {future_range.date_from}',
                    'can_continue': True,
                    'next_range': future_range
                }
            else:
                return {
                    'valid': False,
                    'message': 'No hay rangos de fecha válidos para la fecha actual ni futuros',
                    'can_continue': False
                }
        
        current_range = current_range[0]
        
        # Validar rango actual
        if not current_range.cai:
            return {
                'valid': False,
                'message': f'El rango de fecha {current_range.date_from} - {current_range.date_to} no tiene CAI configurado',
                'can_continue': False
            }
        
        if not current_range.rangoInicial or not current_range.rangoFinal:
            return {
                'valid': False,
                'message': f'El rango de fecha {current_range.date_from} - {current_range.date_to} no tiene rangos numéricos configurados',
                'can_continue': False
            }
        
        if current_range.rangoInicial >= current_range.rangoFinal:
            return {
                'valid': False,
                'message': f'El rango numérico {current_range.rangoInicial}-{current_range.rangoFinal} no es válido',
                'can_continue': False
            }
        
        # Verificar si el rango actual está próximo a vencer
        warnings = []
        can_continue = True
        
        # Alerta de fecha
        if self.dias_alerta and current_range.date_to:
            dias_restantes = (current_range.date_to - current_date).days
            if dias_restantes <= 0:
                warnings.append(f'Fecha límite vencida: {current_range.date_to}')
                can_continue = False
            elif dias_restantes <= self.dias_alerta:
                warnings.append(f'Fecha límite próxima: {current_range.date_to} (quedan {dias_restantes} días)')
        
        # Alerta de números
        if self.numeros_alerta and hasattr(current_range, 'rangoInicial') and hasattr(current_range, 'rangoFinal'):
            if current_range.rangoInicial and current_range.rangoFinal:
                numeros_restantes = current_range.rangoFinal - current_range.number_next_actual + 1
                if numeros_restantes <= 0:
                    warnings.append(f'Rango numérico agotado: {current_range.rangoInicial}-{current_range.rangoFinal}')
                    can_continue = False
                elif numeros_restantes <= self.numeros_alerta:
                    warnings.append(f'Rango numérico próximo a agotarse: quedan {numeros_restantes} números')
        
        # Verificar si hay subsecuencias futuras que permitan continuar
        if not can_continue:
            future_ranges = self.get_available_future_ranges(current_date)
            if future_ranges:
                can_continue = True
                warnings.append(f'Existen {len(future_ranges)} rangos futuros disponibles que permiten continuar operaciones')
        
        return {
            'valid': True,
            'message': '; '.join(warnings) if warnings else 'Rango válido',
            'can_continue': can_continue,
            'current_range': current_range,
            'warnings': warnings
        }
    
    def get_fiscal_sequence_status(self, current_date=None):
        """
        Obtener estado completo de la secuencia fiscal para mostrar en el dashboard
        """
        self.ensure_one()
        
        if not current_date:
            current_date = fields.Date.today()
        
        # Validar continuidad
        continuity = self.validate_sequence_continuity(current_date)
        
        # Obtener rangos futuros
        future_ranges = self.get_available_future_ranges(current_date)
        
        # Calcular estadísticas
        total_ranges = len(self.date_range_ids)
        valid_ranges = len(self.date_range_ids.filtered(lambda r: r.cai and hasattr(r, 'rangoInicial') and hasattr(r, 'rangoFinal') and r.rangoInicial and r.rangoFinal))
        expired_ranges = len(self.date_range_ids.filtered(lambda r: r.date_to and r.date_to < current_date))
        future_ranges_count = len(future_ranges)
        
        return {
            'sequence_name': self.name,
            'is_fiscal': self.is_fiscal,
            'use_date_range': self.use_date_range,
            'continuity': continuity,
            'total_ranges': total_ranges,
            'valid_ranges': valid_ranges,
            'expired_ranges': expired_ranges,
            'future_ranges': future_ranges_count,
            'can_continue_operations': continuity['can_continue'],
            'status': 'active' if continuity['can_continue'] else 'critical',
            'last_validation': self.fiscal_validation_date,
            'validation_error': self.fiscal_validation_error
        }


class IrSequenceDateRange(models.Model):
    _inherit = 'ir.sequence.date_range'

    cai = fields.Char(string='CAI', help='Clave de Autorización de Impresión')
    rangoInicial = fields.Integer(string='Rango inicial', help='Rango inicial')
    rangoFinal = fields.Integer(string='Rango final', help='Rango final')
    cai_validated = fields.Boolean(string='CAI Validado', default=False)
    cai_validation_date = fields.Datetime(string='Fecha de Validación CAI', readonly=True)
    cai_validation_error = fields.Text(string='Error de Validación CAI', readonly=True)
    
    @api.constrains('rangoInicial', 'rangoFinal')
    def _check_cai_ranges(self):
        """Validar que los rangos del CAI sean válidos"""
        for record in self:
            if record.rangoInicial and record.rangoFinal:
                if record.rangoInicial >= record.rangoFinal:
                    raise ValidationError(_('El rango inicial debe ser menor al rango final'))
                
                if record.rangoInicial < 1:
                    raise ValidationError(_('El rango inicial debe ser mayor a 0'))
    
    @api.constrains('date_from', 'date_to')
    def _check_date_ranges(self):
        """Validar que las fechas del rango sean válidas"""
        for record in self:
            if record.date_from and record.date_to:
                if record.date_from >= record.date_to:
                    raise ValidationError(_('La fecha de inicio debe ser menor a la fecha de fin'))
    
    # @api.constrains('cai')
    # def _check_cai_format(self):
    #     """Validar formato del CAI"""
    #     for record in self:
    #         if record.cai and not re.match(r'^[A-Z0-9]{37}$', record.cai):
    #             raise ValidationError(_('El CAI debe tener 37 caracteres alfanuméricos'))
    
    def validate_cai_manual(self):
        """Validar CAI manualmente (validaciones adicionales)"""
        self.ensure_one()
        
        try:
            # Validar que el CAI esté presente
            if not self.cai:
                raise ValidationError(_('El CAI no puede estar vacío'))
            
            # Las validaciones de formato, rangos y fechas se hacen automáticamente con constraints
            # Solo validar que todos los campos requeridos estén presentes
            if not self.rangoInicial or not self.rangoFinal:
                raise ValidationError(_('Los rangos inicial y final son obligatorios'))
            
            # Marcar como validado
            self.write({
                'cai_validated': True,
                'cai_validation_date': fields.Datetime.now(),
                'cai_validation_error': False
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Validación Exitosa'),
                    'message': _('El CAI ha sido validado correctamente'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            self.write({
                'cai_validated': False,
                'cai_validation_date': fields.Datetime.now(),
                'cai_validation_error': str(e)
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error de Validación'),
                    'message': str(e),
                    'type': 'danger',
                }
            }
