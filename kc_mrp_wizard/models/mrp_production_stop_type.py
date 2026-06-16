# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProductionStopType(models.Model):
    _name = 'mrp.production.stop.type'
    _description = 'Tipo de paro de producción'
    _parent_order = 'sequence, name'

    name = fields.Char('Nombre', required=True, translate=True)
    fa_icon = fields.Char(
        'Icono FA',
        default='fa-stop',
        help='Clase del icono Font Awesome (ej: fa-wrench, fa-exclamation-triangle).',
    )
    sequence = fields.Integer('Secuencia', default=10)
    active = fields.Boolean(default=True)

    # --- Paro padre / hijo ---
    is_parent = fields.Boolean(
        'Agrupador',
        default=False,
        help='Si está activo, este tipo solo agrupa paros agrupados; no se puede usar para registrar paros ni puede tener un paro agrupador.',
    )
    parent_id = fields.Many2one(
        'mrp.production.stop.type',
        'Agrupado por',
        ondelete='cascade',
        domain="[('is_parent', '=', True), '|', ('company_id', '=', company_id), ('company_id', '=', False)]",
    )
    child_ids = fields.One2many(
        'mrp.production.stop.type',
        'parent_id',
        'Paros agrupados',
    )
    child_count = fields.Integer('Paros agrupados', compute='_compute_child_count')

    @api.depends('child_ids')
    def _compute_child_count(self):
        for rec in self:
            rec.child_count = len(rec.child_ids)

    @api.constrains('is_parent', 'parent_id')
    def _check_parent_not_child(self):
        for rec in self:
            if rec.is_parent and rec.parent_id:
                raise UserError(_('Un paro padre no puede ser paro hijo. Desmarque "Agrupador" o quite el paro agrupador.'))
            if rec.parent_id and rec.parent_id.is_parent is False:
                raise UserError(_('El paro agrupador seleccionado debe tener activo "Agrupador".'))
            if rec.parent_id and rec.parent_id.id == rec.id:
                raise UserError(_('Un tipo de paro no puede ser agrupador de sí mismo.'))

    @api.onchange('is_parent')
    def _onchange_is_parent_clear_quality_maintenance(self):
        """Al activar "Agrupador", vaciar campos de calidad y mantenimiento (solo agrupan paros agrupados)."""
        if self.is_parent:
            self.create_quality_alert = False
            self.quality_team_id = False
            self.quality_responsible_id = False
            self.quality_tag_ids = [(5, 0, 0)]
            self.create_maintenance_request = False
            self.maintenance_team_id = False
            self.maintenance_responsible_id = False

    # --- Alerta de calidad ---
    create_quality_alert = fields.Boolean(
        'Generar alerta de calidad',
        default=False,
        help='Si está activo, al registrar este paro se crea una alerta de calidad.',
    )
    quality_team_id = fields.Many2one(
        'quality.alert.team',
        'Equipo de calidad',
        ondelete='set null',
        check_company=True,
    )
    quality_responsible_id = fields.Many2one(
        'res.users',
        'Responsable alerta de calidad',
        ondelete='set null',
        check_company=True,
    )
    quality_tag_ids = fields.Many2many(
        'quality.tag',
        'mrp_stop_type_quality_tag_rel',
        'stop_type_id',
        'tag_id',
        string='Etiquetas (alerta de calidad)',
        help='Etiquetas opcionales para la alerta de calidad creada.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        ondelete='cascade',
    )

    # --- Solicitud de mantenimiento ---
    create_maintenance_request = fields.Boolean(
        'Generar solicitud de mantenimiento',
        default=False,
        help='Si está activo, al registrar este paro se crea una solicitud de mantenimiento.',
    )
    maintenance_team_id = fields.Many2one(
        'maintenance.team',
        'Equipo de mantenimiento',
        ondelete='set null',
        check_company=True,
    )
    maintenance_responsible_id = fields.Many2one(
        'res.users',
        'Responsable mantenimiento',
        ondelete='set null',
        check_company=True,
        help='Técnico responsable de la solicitud de mantenimiento.',
    )

    def write(self, vals):
        """Al activar "Agrupador", vaciar campos de calidad y mantenimiento."""
        if vals.get('is_parent'):
            vals.update({
                'create_quality_alert': False,
                'quality_team_id': False,
                'quality_responsible_id': False,
                'quality_tag_ids': [(5, 0, 0)],
                'create_maintenance_request': False,
                'maintenance_team_id': False,
                'maintenance_responsible_id': False,
            })
        return super().write(vals)

    # --- Acción para crear alerta de calidad desde WO ---
    def action_create_quality_alert_from_workorder(self, workorder):
        """Crea una alerta de calidad desde este tipo de paro para la orden de trabajo dada."""
        self.ensure_one()
        if not self.create_quality_alert:
            return self.env['quality.alert']
        if not workorder or workorder._name != 'mrp.workorder':
            return self.env['quality.alert']
        company = workorder.company_id or self.env.company
        team = self.quality_team_id
        product = workorder.production_id.product_id.product_tmpl_id
        workcenter = workorder.workcenter_id
        title = _('Paro: %s en %s — O.T.: %s') % (self.name, workcenter.name, workorder.display_name)
        if not team:
            team = self.env['quality.alert.team'].search(
                ['|', ('company_id', '=', company.id), ('company_id', '=', False)],
                limit=1,
            )
        if not team:
            raise UserError(_(
                'No hay equipo de calidad configurado. Configure un equipo en Calidad o en el tipo de paro "%s".',
                self.name,
            ))
        vals = {
            'title': title,
            'description': _('Paro: %s — Orden de trabajo: %s') % (self.name, workorder.display_name),
            'product_tmpl_id': product.id,
            'workcenter_id': workcenter.id,
            'company_id': company.id,
            'team_id': team.id,
            'date_assign': fields.Datetime.now(),
            'priority': '3', # Critical
            'by_stop_production': True,
            'user_id': self.quality_responsible_id.id or self.env.user.id,
            'tag_ids': [(6, 0, self.quality_tag_ids.ids)],
            'workorder_id': workorder.id,
        }
        return self.env['quality.alert'].create(vals)

    def action_create_maintenance_request_from_workorder(self, workorder):
        """Crea una solicitud de mantenimiento desde este tipo de paro para la orden de trabajo dada."""
        self.ensure_one()
        if not self.create_maintenance_request:
            return self.env['maintenance.request']
        if not workorder or workorder._name != 'mrp.workorder':
            return self.env['maintenance.request']
        company = workorder.company_id or self.env.company
        team = self.maintenance_team_id
        production = workorder.production_id
        workcenter = workorder.workcenter_id
        if not team:
            team = self.env['maintenance.team'].search(
                [('company_id', '=', company.id)],
                limit=1,
            )
        if not team:
            team = self.env['maintenance.team'].search([], limit=1)
        if not team:
            raise UserError(_(
                'No hay equipo de mantenimiento configurado. Configure un equipo en Mantenimiento o en el tipo de paro "%s".',
                self.name,
            ))
        name = _('%s — %s') % (self.name, workorder.display_name)
        vals = {
            'name': name,
            'description': _('Paro registrado desde orden de trabajo: %s') % workorder.display_name,
            'company_id': company.id,
            'maintenance_team_id': team.id,
            'maintenance_for': 'workcenter',
            'workcenter_id': workcenter.id,
            'production_id': production.id,
            'maintenance_type': 'preventive',
            'schedule_date': fields.Datetime.now(),
            'priority': '3', # Critical
            'by_stop_production': True,
            'user_id': self.maintenance_responsible_id.id or False,
        }
        return self.env['maintenance.request'].create(vals)

    def action_trigger_from_workorder(self):
        """Ejecuta el paro para la orden de trabajo que viene en contexto (workorder_id).
        Solo paros ejecutables (no padre). Si no hay workorder_id (ej. desde configuración), abre el formulario del tipo."""
        self.ensure_one()
        if self.is_parent:
            raise UserError(_('No se puede registrar un paro padre. Elija un paro hijo o un tipo sin padre.'))
        workorder_id = self.env.context.get('workorder_id')
        if not workorder_id:
            return self.action_open_or_children()
        workorder = self.env['mrp.workorder'].browse(workorder_id)
        if not workorder.exists():
            raise UserError(_('Orden de trabajo no encontrada.'))
        return workorder.action_register_stop_type(stop_type_id=self.id)

    def action_open_or_children(self):
        """Abre el formulario del tipo o, si es paro padre, la vista kanban de sus hijos.
        Si viene workorder_id en contexto (asistente de producción), paro no padre ejecuta el paro en lugar de abrir formulario."""
        self.ensure_one()
        workorder_id = self.env.context.get('workorder_id')
        if self.is_parent:
            ctx = dict(self.env.context, default_parent_id=self.id)
            if workorder_id:
                ctx['workorder_id'] = workorder_id
            return {
                'type': 'ir.actions.act_window',
                'name': _('Paros: %s') % self.name,
                'res_model': 'mrp.production.stop.type',
                'view_mode': 'kanban',
                'view_id': self.env.ref('kc_mrp_wizard.mrp_production_stop_type_kanban_children').id,
                'domain': [('parent_id', '=', self.id)],
                'context': ctx,
                'target': 'new',
            }
        if workorder_id:
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            if workorder.exists():
                return workorder.action_register_stop_type(stop_type_id=self.id)
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'mrp.production.stop.type',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }
