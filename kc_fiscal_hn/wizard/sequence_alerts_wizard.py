# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SequenceAlertsWizard(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.sequence_alerts'
    _description = 'Wizard de Alertas de Secuencias Fiscales'

    # Campos para mostrar información
    expired_sequences = fields.Text(string='Secuencias Agotadas', readonly=True)
    expiring_cais = fields.Text(string='CAI Próximos a Vencer', readonly=True)
    validation_errors = fields.Text(string='Errores de Validación', readonly=True)
    
    def action_check_sequences(self):
        """Verificar todas las secuencias fiscales"""
        self.ensure_one()
        
        # Obtener secuencias fiscales
        sequences = self.env['ir.sequence'].search([('is_fiscal', '=', True)])
        
        # Verificar secuencias agotadas
        expired_info = []
        for sequence in sequences:
            expired_data = sequence.check_sequence_expiration()
            if expired_data:
                expired_info.extend(expired_data)
        
        # Verificar CAI próximos a vencer
        expiring_info = []
        for sequence in sequences:
            if sequence.date_range_ids:
                for date_range in sequence.date_range_ids:
                    expiring_data = date_range.check_cai_expiration()
                    if expiring_data:
                        expiring_info.extend(expiring_data)
        
        # Verificar errores de validación
        validation_errors = []
        for sequence in sequences:
            if sequence.fiscal_validation_error:
                validation_errors.append(f"Secuencia: {sequence.name} - Error: {sequence.fiscal_validation_error}")
        
        # Actualizar campos del wizard
        self.expired_sequences = self._format_expired_sequences(expired_info)
        self.expiring_cais = self._format_expiring_cais(expiring_info)
        self.validation_errors = self._format_validation_errors(validation_errors)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kc_fiscal_hn.wizard.sequence_alerts',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _format_expired_sequences(self, expired_data):
        """Formatear información de secuencias agotadas"""
        if not expired_data:
            return "No hay secuencias agotadas."
        
        result = "Secuencias próximas a agotarse:\n\n"
        for data in expired_data:
            result += f"• Secuencia: {data['sequence']}\n"
            result += f"  Rango: {data['date_range']}\n"
            result += f"  Números restantes: {data['remaining']}\n"
            result += f"  CAI: {data['cai']}\n\n"
        
        return result
    
    def _format_expiring_cais(self, expiring_data):
        """Formatear información de CAI próximos a vencer"""
        if not expiring_data:
            return "No hay CAI próximos a vencer."
        
        result = "CAI próximos a vencer:\n\n"
        for data in expiring_data:
            result += f"• Secuencia: {data['sequence']}\n"
            result += f"  Rango: {data['date_range']}\n"
            result += f"  CAI: {data['cai']}\n"
            result += f"  Vence: {data['expiration_date']}\n"
            result += f"  Días restantes: {data['days_to_expire']}\n\n"
        
        return result
    
    def _format_validation_errors(self, errors):
        """Formatear errores de validación"""
        if not errors:
            return "No hay errores de validación."
        
        result = "Errores de validación encontrados:\n\n"
        for error in errors:
            result += f"• {error}\n"
        
        return result
    
    def action_validate_all_sequences(self):
        """Validar todas las secuencias fiscales"""
        sequences = self.env['ir.sequence'].search([('is_fiscal', '=', True)])
        
        validated_count = 0
        error_count = 0
        
        for sequence in sequences:
            try:
                sequence.validate_fiscal_sequence_complete()
                validated_count += 1
            except Exception as e:
                error_count += 1
        
        # Mostrar resumen
        message = f"Validación completada:\n"
        message += f"• Secuencias validadas: {validated_count}\n"
        message += f"• Errores encontrados: {error_count}"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación Completada'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
            }
        } 