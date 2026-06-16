# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'kc.sale.planning.mixin']

    kc_planning_qty_to_deliver = fields.Float(
        string='Saldo por entregar',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_qty_to_manufacture = fields.Float(
        string='Saldo por fabricar',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
        help='Cantidad pedida menos lo ya producido en órdenes de fabricación vinculadas a esta línea.',
    )
    kc_planning_mo_count = fields.Integer(
        string='Nº OF',
        compute='_compute_kc_planning_metrics',
        store=True,
    )
    kc_planning_mo_open_count = fields.Integer(
        string='OF abiertas',
        compute='_compute_kc_planning_metrics',
        store=True,
    )
    kc_planning_mo_planned_qty = fields.Float(
        string='Planificado OF',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_mo_produced_qty = fields.Float(
        string='Producido OF',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_pt_qty_available = fields.Float(
        string='Stock PT',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_wip_qty_available = fields.Float(
        string='Stock WIP',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
        help='Existencias en ubicaciones de producción en proceso y salidas intermedias.',
    )
    kc_planning_mp_product_id = fields.Many2one(
        'product.product',
        string='Componente crítico',
        compute='_compute_kc_planning_metrics',
        store=True,
    )
    kc_planning_mp_qty_available = fields.Float(
        string='Stock MP crítica',
        compute='_compute_kc_planning_metrics',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_alert_state = fields.Selection(
        [
            ('ok', 'OK'),
            ('warning', 'Revisar'),
            ('danger', 'Faltante'),
        ],
        string='Alerta',
        compute='_compute_kc_planning_metrics',
        store=True,
    )

    @api.depends(
        'product_uom_qty',
        'qty_delivered',
        'qty_to_invoice',
        'product_id',
        'product_uom',
        'company_id',
        'state',
        'display_type',
    )
    def _compute_kc_planning_metrics(self):
        for line in self:
            if line.display_type or line.state != 'sale' or not line.product_id:
                line.kc_planning_qty_to_deliver = 0.0
                line.kc_planning_qty_to_manufacture = 0.0
                line.kc_planning_mo_count = 0
                line.kc_planning_mo_open_count = 0
                line.kc_planning_mo_planned_qty = 0.0
                line.kc_planning_mo_produced_qty = 0.0
                line.kc_planning_pt_qty_available = 0.0
                line.kc_planning_wip_qty_available = 0.0
                line.kc_planning_mp_product_id = False
                line.kc_planning_mp_qty_available = 0.0
                line.kc_planning_alert_state = 'ok'
                continue

            uom = line.product_uom or line.product_id.uom_id
            rounding = uom.rounding
            line.kc_planning_qty_to_deliver = float_round(
                line.product_uom_qty - line.qty_delivered,
                precision_rounding=rounding,
            )
            mo_stats = line._kc_planning_aggregate_mos([
                ('sale_line_id', '=', line.id),
                ('state', '!=', 'cancel'),
            ])
            line.kc_planning_mo_count = mo_stats['mo_count']
            line.kc_planning_mo_open_count = mo_stats['mo_open_count']
            line.kc_planning_mo_planned_qty = mo_stats['mo_planned_qty']
            line.kc_planning_mo_produced_qty = mo_stats['mo_produced_qty']
            line.kc_planning_qty_to_manufacture = float_round(
                max(line.product_uom_qty - line.kc_planning_mo_produced_qty, 0.0),
                precision_rounding=rounding,
            )

            company = line.company_id
            line.kc_planning_pt_qty_available = line._kc_planning_product_qty_by_usage(
                line.product_id, company, ['pt'],
            )
            line.kc_planning_wip_qty_available = line._kc_planning_product_qty_by_usage(
                line.product_id, company, ['wip', 'production'],
            )
            critical_line = line._kc_planning_critical_bom_line(line.product_id, company)
            if critical_line:
                line.kc_planning_mp_product_id = critical_line.product_id
                line.kc_planning_mp_qty_available = line._kc_planning_product_qty_by_usage(
                    critical_line.product_id, company, ['mp', 'consumption'],
                )
            else:
                line.kc_planning_mp_product_id = False
                line.kc_planning_mp_qty_available = 0.0

            line.kc_planning_alert_state = line._kc_planning_alert_state(
                line.kc_planning_qty_to_manufacture,
                line.kc_planning_pt_qty_available,
                line.kc_planning_mp_qty_available,
                bool(critical_line),
                line.kc_planning_mo_produced_qty,
                line.kc_planning_wip_qty_available,
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped('product_id')._kc_planning_invalidate_from_sale_lines()
        return lines

    def write(self, vals):
        products_before = self.mapped('product_id')
        res = super().write(vals)
        tracked = {
            'product_uom_qty', 'qty_delivered', 'qty_invoiced', 'qty_to_invoice',
            'product_id', 'product_uom', 'state', 'company_id',
        }
        if tracked.intersection(vals):
            (products_before | self.mapped('product_id'))._kc_planning_invalidate_from_sale_lines()
            self.filtered(
                lambda l: l.state == 'sale' and not l.display_type
            )._kc_planning_invalidate_from_mrp()
        return res

    def _kc_planning_invalidate_from_mrp(self):
        lines = self.filtered(lambda l: l.state == 'sale' and not l.display_type)
        if lines:
            lines.invalidate_recordset([
                'kc_planning_qty_to_deliver',
                'kc_planning_qty_to_manufacture',
                'kc_planning_mo_count',
                'kc_planning_mo_open_count',
                'kc_planning_mo_planned_qty',
                'kc_planning_mo_produced_qty',
                'kc_planning_pt_qty_available',
                'kc_planning_wip_qty_available',
                'kc_planning_mp_product_id',
                'kc_planning_mp_qty_available',
                'kc_planning_alert_state',
            ])

    def action_kc_open_linked_mrp_production(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        action['domain'] = [('sale_line_id', '=', self.id)]
        action['name'] = _('OF vinculadas a %s') % self.display_name
        return action
