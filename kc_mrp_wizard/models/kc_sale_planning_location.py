# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class KcSalePlanningLocation(models.Model):
    """Ubicaciones de stock usadas en planificación ventas / MRP (multi-ubicación)."""

    _name = 'kc.sale.planning.location'
    _description = 'Ubicación planificación MRP'
    _order = 'usage_type, sequence, id'

    USAGE_TYPES = [
        ('pt', 'Producto terminado (PT)'),
        ('mp', 'Materia prima (MP)'),
        ('wip', 'Producción en proceso (WIP)'),
        ('consumption', 'Consumo por centro'),
        ('production', 'Producción / salida intermedia'),
    ]

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    usage_type = fields.Selection(
        USAGE_TYPES,
        string='Tipo',
        required=True,
        default='pt',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        required=True,
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])]",
        check_company=True,
    )
    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        domain="[('company_id', 'in', [company_id, False])]",
        check_company=True,
        help='Opcional. Para tipo «Consumo por centro», indica la máquina que consume desde esta ubicación.',
    )
    include_child_locations = fields.Boolean(
        string='Incluir sububicaciones',
        default=True,
        help='Suma el stock de todas las ubicaciones hijas bajo la ubicación indicada.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    notes = fields.Char(string='Notas')

    _sql_constraints = [
        (
            'location_company_uniq',
            'unique(company_id, location_id, usage_type, workcenter_id)',
            'La misma ubicación y tipo ya está configurada para esta compañía.',
        ),
    ]

    @api.constrains('usage_type', 'workcenter_id')
    def _check_consumption_workcenter(self):
        for rec in self:
            if rec.usage_type == 'consumption' and not rec.workcenter_id:
                raise ValidationError(_(
                    'Las ubicaciones de tipo «Consumo por centro» deben tener un centro de trabajo.'
                ))

    @api.constrains('location_id', 'company_id')
    def _check_location_company(self):
        for rec in self:
            if rec.location_id.company_id and rec.location_id.company_id != rec.company_id:
                raise ValidationError(_(
                    'La ubicación %(loc)s pertenece a otra compañía.',
                    loc=rec.location_id.display_name,
                ))

    def _kc_planning_refresh_company_stock_metrics(self):
        """Invalida KPIs de stock tras cambiar ubicaciones de planificación."""
        Sol = self.env['sale.order.line']
        for company in self.mapped('company_id'):
            lines = Sol.search([
                ('company_id', '=', company.id),
                ('state', '=', 'sale'),
                ('display_type', '=', False),
                ('product_id', '!=', False),
            ])
            products = lines.mapped('product_id')
            if products:
                products._kc_planning_invalidate_from_sale_lines()
                lines._kc_planning_invalidate_from_mrp()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._kc_planning_refresh_company_stock_metrics()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'location_id', 'usage_type', 'workcenter_id', 'include_child_locations', 'active'} & set(vals):
            self._kc_planning_refresh_company_stock_metrics()
        return res

    def unlink(self):
        refresh_data = []
        Sol = self.env['sale.order.line']
        for company in self.mapped('company_id'):
            lines = Sol.search([
                ('company_id', '=', company.id),
                ('state', '=', 'sale'),
                ('display_type', '=', False),
                ('product_id', '!=', False),
            ])
            refresh_data.append((lines.mapped('product_id'), lines))
        res = super().unlink()
        for products, lines in refresh_data:
            if products:
                products._kc_planning_invalidate_from_sale_lines()
                lines._kc_planning_invalidate_from_mrp()
        return res
