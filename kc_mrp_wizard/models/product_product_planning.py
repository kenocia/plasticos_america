# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'kc.sale.planning.mixin']

    kc_planning_sale_line_count = fields.Integer(
        string='Líneas pedido',
        compute='_compute_kc_planning_product',
        store=True,
    )
    kc_planning_order_count = fields.Integer(
        string='Pedidos',
        compute='_compute_kc_planning_product',
        store=True,
    )
    kc_planning_qty_ordered = fields.Float(
        string='Σ Pedido',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_qty_delivered = fields.Float(
        string='Σ Entregado',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_qty_to_deliver = fields.Float(
        string='Σ Saldo entregar',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_qty_to_invoice = fields.Float(
        string='Σ Por facturar',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_mo_produced_qty = fields.Float(
        string='Σ Producido OF',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_qty_to_manufacture = fields.Float(
        string='Σ Saldo fabricar',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_mo_count = fields.Integer(
        string='Nº OF',
        compute='_compute_kc_planning_product',
        store=True,
    )
    kc_planning_mo_open_count = fields.Integer(
        string='OF abiertas',
        compute='_compute_kc_planning_product',
        store=True,
    )
    kc_planning_mo_unlinked_qty = fields.Float(
        string='OF sin pedido',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
        help='Cantidad planificada en OF del mismo producto sin línea de pedido vinculada.',
    )
    kc_planning_pt_qty_available = fields.Float(
        string='Stock PT',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_wip_qty_available = fields.Float(
        string='Stock WIP',
        compute='_compute_kc_planning_product',
        digits='Product Unit of Measure',
        store=True,
    )
    kc_planning_mp_product_id = fields.Many2one(
        'product.product',
        string='Componente crítico',
        compute='_compute_kc_planning_product',
        store=True,
    )
    kc_planning_mp_qty_available = fields.Float(
        string='Stock MP',
        compute='_compute_kc_planning_product',
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
        compute='_compute_kc_planning_product',
        store=True,
    )

    @api.depends(
        'product_tmpl_id',
    )
    def _compute_kc_planning_product(self):
        """Agrega líneas de pedido confirmadas y OF vinculadas por producto."""
        Sol = self.env['sale.order.line']
        Production = self.env['mrp.production']
        if not self.ids:
            return

        sol_domain = self._kc_planning_sale_line_base_domain(company=None)
        sol_domain.append(('product_id', 'in', self.ids))

        sol_by_product = {}
        line_count_by_product = {}
        order_count_by_product = {}
        for product, qty_sum, del_sum, inv_sum, line_count, order_count in Sol._read_group(
            sol_domain,
            groupby=['product_id'],
            aggregates=[
                'product_uom_qty:sum',
                'qty_delivered:sum',
                'qty_to_invoice:sum',
                '__count',
                'order_id:count_distinct',
            ],
        ):
            if not product:
                continue
            sol_by_product[product.id] = {
                'product_uom_qty': qty_sum or 0.0,
                'qty_delivered': del_sum or 0.0,
                'qty_to_invoice': inv_sum or 0.0,
            }
            line_count_by_product[product.id] = line_count or 0
            order_count_by_product[product.id] = order_count or 0

        # qty_produced no es stored en mrp.production → no usable en _read_group
        mo_linked_by_product = {}
        linked_mos = Production.search([
            ('product_id', 'in', self.ids),
            ('sale_line_id', '!=', False),
            ('state', '!=', 'cancel'),
        ])
        for mo in linked_mos:
            mo_linked_by_product[mo.product_id.id] = (
                mo_linked_by_product.get(mo.product_id.id, 0.0) + mo.qty_produced
            )

        mo_open_by_product = {}
        for product, count in Production._read_group(
            [
                ('product_id', 'in', self.ids),
                ('sale_line_id', '!=', False),
                ('state', 'in', ('draft', 'confirmed', 'progress', 'to_close')),
            ],
            groupby=['product_id'],
            aggregates=['__count'],
        ):
            if product:
                mo_open_by_product[product.id] = count or 0

        mo_count_by_product = {}
        for product, count in Production._read_group(
            [
                ('product_id', 'in', self.ids),
                ('sale_line_id', '!=', False),
                ('state', '!=', 'cancel'),
            ],
            groupby=['product_id'],
            aggregates=['__count'],
        ):
            if product:
                mo_count_by_product[product.id] = count or 0

        mo_unlinked_by_product = {}
        for product, qty in Production._read_group(
            [
                ('product_id', 'in', self.ids),
                ('sale_line_id', '=', False),
                ('state', 'not in', ('done', 'cancel')),
            ],
            groupby=['product_id'],
            aggregates=['product_qty:sum'],
        ):
            if product:
                mo_unlinked_by_product[product.id] = qty or 0.0

        for product in self:
            company = product.company_id or self.env.company
            rounding = product.uom_id.rounding
            sg = sol_by_product.get(product.id, {})
            qty_ordered = sg.get('product_uom_qty', 0.0) or 0.0
            qty_delivered = sg.get('qty_delivered', 0.0) or 0.0
            qty_to_invoice = sg.get('qty_to_invoice', 0.0) or 0.0
            mo_produced = (mo_linked_by_product.get(product.id) or {}).get('qty_produced', 0.0) or 0.0

            product.kc_planning_sale_line_count = line_count_by_product.get(product.id, 0)
            product.kc_planning_order_count = order_count_by_product.get(product.id, 0)
            product.kc_planning_qty_ordered = float_round(qty_ordered, precision_rounding=rounding)
            product.kc_planning_qty_delivered = float_round(qty_delivered, precision_rounding=rounding)
            product.kc_planning_qty_to_deliver = float_round(
                qty_ordered - qty_delivered, precision_rounding=rounding,
            )
            product.kc_planning_qty_to_invoice = float_round(qty_to_invoice, precision_rounding=rounding)
            product.kc_planning_mo_produced_qty = float_round(mo_produced, precision_rounding=rounding)
            product.kc_planning_qty_to_manufacture = float_round(
                max(qty_ordered - mo_produced, 0.0),
                precision_rounding=rounding,
            )
            product.kc_planning_mo_count = mo_count_by_product.get(product.id, 0)
            product.kc_planning_mo_open_count = mo_open_by_product.get(product.id, 0)
            product.kc_planning_mo_unlinked_qty = float_round(
                mo_unlinked_by_product.get(product.id, 0.0) or 0.0,
                precision_rounding=rounding,
            )

            product.kc_planning_pt_qty_available = product._kc_planning_product_qty_by_usage(
                product, company, ['pt'],
            )
            product.kc_planning_wip_qty_available = product._kc_planning_product_qty_by_usage(
                product, company, ['wip', 'production'],
            )
            critical_line = product._kc_planning_critical_bom_line(product, company)
            if critical_line:
                product.kc_planning_mp_product_id = critical_line.product_id.id
                product.kc_planning_mp_qty_available = product._kc_planning_product_qty_by_usage(
                    critical_line.product_id, company, ['mp', 'consumption'],
                )
            else:
                product.kc_planning_mp_product_id = False
                product.kc_planning_mp_qty_available = 0.0

            product.kc_planning_alert_state = product._kc_planning_alert_state(
                product.kc_planning_qty_to_manufacture,
                product.kc_planning_pt_qty_available,
                product.kc_planning_mp_qty_available,
                bool(critical_line),
                product.kc_planning_mo_produced_qty,
                product.kc_planning_wip_qty_available,
            )

    def _kc_planning_invalidate_from_sale_lines(self):
        if self:
            self.invalidate_recordset([
                'kc_planning_sale_line_count',
                'kc_planning_order_count',
                'kc_planning_qty_ordered',
                'kc_planning_qty_delivered',
                'kc_planning_qty_to_deliver',
                'kc_planning_qty_to_invoice',
                'kc_planning_mo_produced_qty',
                'kc_planning_qty_to_manufacture',
                'kc_planning_mo_count',
                'kc_planning_mo_open_count',
                'kc_planning_mo_unlinked_qty',
                'kc_planning_pt_qty_available',
                'kc_planning_wip_qty_available',
                'kc_planning_mp_product_id',
                'kc_planning_mp_qty_available',
                'kc_planning_alert_state',
            ])

    def action_kc_open_sale_planning_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Líneas de pedido — %s') % self.display_name,
            'res_model': 'sale.order.line',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('kc_mrp_wizard.sale_order_line_planning_list').id, 'list'),
                (False, 'form'),
            ],
            'domain': [
                ('product_id', '=', self.id),
                ('state', '=', 'sale'),
                ('display_type', '=', False),
            ],
            'context': {'search_default_order_id': 1},
        }

    def action_kc_open_planning_mrp_production(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        action['domain'] = [
            ('product_id', '=', self.id),
            ('sale_line_id', '!=', False),
        ]
        action['name'] = _('OF vinculadas — %s') % self.display_name
        return action
