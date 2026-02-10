# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SequenceAudit(models.Model):
    _name = 'kc_fiscal_hn.sequence.audit'
    _description = 'Auditoría de Secuencias Fiscales'
    _order = 'create_date desc'

    sequence_id = fields.Many2one('ir.sequence', string='Secuencia', required=True, ondelete='cascade')
    action = fields.Selection([
        ('reset', 'Reinicio'),
        ('modify', 'Modificación'),
        ('create', 'Creación'),
        ('delete', 'Eliminación')
    ], string='Acción', required=True)
    
    old_number = fields.Integer(string='Número Anterior')
    new_number = fields.Integer(string='Número Nuevo')
    reason = fields.Text(string='Motivo')
    
    user_id = fields.Many2one('res.users', string='Usuario', required=True, default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Compañía', 
                                default=lambda self: self.env.company)
    
    # Campos adicionales para contexto
    ip_address = fields.Char(string='Dirección IP')
    session_id = fields.Char(string='ID de Sesión')
    
    def name_get(self):
        """Nombre personalizado para los registros de auditoría"""
        result = []
        for audit in self:
            name = f"{audit.sequence_id.name} - {audit.action.upper()} - {audit.create_date.strftime('%Y-%m-%d %H:%M')}"
            result.append((audit.id, name))
        return result
    
    @api.model_create_multi
    def create(self, vals_list):
        """Crear registro de auditoría con información adicional"""
        # Procesar cada conjunto de valores
        for vals in vals_list:
            # Capturar información adicional si está disponible
            if not vals.get('ip_address'):
                vals['ip_address'] = self.env.context.get('ip_address', 'N/A')
            
            if not vals.get('session_id'):
                vals['session_id'] = self.env.context.get('session_id', 'N/A')
        
        return super().create(vals_list)
    
    def action_view_sequence(self):
        """Ver secuencia relacionada"""
        self.ensure_one()
        return {
            'name': _('Secuencia Fiscal'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.sequence',
            'res_id': self.sequence_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    @api.model
    def get_audit_summary(self, days=30):
        """Obtener resumen de auditoría de los últimos días"""
        from datetime import datetime, timedelta
        
        start_date = fields.Datetime.now() - timedelta(days=days)
        
        audits = self.search([
            ('create_date', '>=', start_date)
        ])
        
        summary = {
            'total_actions': len(audits),
            'resets': len(audits.filtered(lambda a: a.action == 'reset')),
            'modifications': len(audits.filtered(lambda a: a.action == 'modify')),
            'creations': len(audits.filtered(lambda a: a.action == 'create')),
            'deletions': len(audits.filtered(lambda a: a.action == 'delete')),
            'by_user': {},
            'by_sequence': {}
        }
        
        # Agrupar por usuario
        for audit in audits:
            user_name = audit.user_id.name
            if user_name not in summary['by_user']:
                summary['by_user'][user_name] = 0
            summary['by_user'][user_name] += 1
        
        # Agrupar por secuencia
        for audit in audits:
            sequence_name = audit.sequence_id.name
            if sequence_name not in summary['by_sequence']:
                summary['by_sequence'][sequence_name] = 0
            summary['by_sequence'][sequence_name] += 1
        
        return summary 