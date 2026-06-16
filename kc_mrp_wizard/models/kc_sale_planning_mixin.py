# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.tools.float_utils import float_round


class KcSalePlanningMixin(models.AbstractModel):
    """Utilidades compartidas para planificación ventas / MRP."""

    _name = 'kc.sale.planning.mixin'
    _description = 'Utilidades planificación (ventas / MRP)'

    @api.model
    def _kc_planning_sale_line_base_domain(self, product=None, company=None):
        domain = [
            ('state', '=', 'sale'),
            ('display_type', '=', False),
            ('product_id', '!=', False),
        ]
        if product:
            domain.append(('product_id', '=', product.id))
        if company:
            domain.append(('company_id', '=', company.id))
        return domain

    @api.model
    def _kc_planning_get_location_lines(self, company, usage_types):
        """Líneas de configuración activas para los tipos indicados."""
        company = company or self.env.company
        usage_types = list(usage_types) if usage_types else []
        return company.kc_planning_location_ids.filtered(
            lambda line: line.active and line.usage_type in usage_types
        )

    @api.model
    def _kc_planning_resolve_stock_locations(self, company, usage_types):
        """Ubicaciones internas (con hijas opcionales) para sumar existencias."""
        Location = self.env['stock.location']
        lines = self._kc_planning_get_location_lines(company, usage_types)
        if not lines:
            return Location
        loc_ids = set()
        for line in lines:
            root = line.location_id
            if not root:
                continue
            if line.include_child_locations:
                loc_ids.update(
                    Location.search([('id', 'child_of', root.id)]).ids
                )
            else:
                loc_ids.add(root.id)
        return Location.browse(list(loc_ids))

    @api.model
    def _kc_planning_product_qty_in_locations(self, product, locations, company):
        """Cantidad disponible (no reservada) en las ubicaciones indicadas."""
        if not product or not locations:
            return 0.0
        company = company or self.env.company
        groups = self.env['stock.quant']._read_group(
            [
                ('product_id', '=', product.id),
                ('location_id', 'in', locations.ids),
                ('company_id', '=', company.id),
            ],
            groupby=[],
            aggregates=['available_quantity:sum'],
        )
        qty = groups[0][0] if groups else 0.0
        return float_round(qty or 0.0, precision_rounding=product.uom_id.rounding)

    @api.model
    def _kc_planning_product_qty_by_usage(self, product, company, usage_types):
        locations = self._kc_planning_resolve_stock_locations(company, usage_types)
        return self._kc_planning_product_qty_in_locations(product, locations, company)

    @api.model
    def _kc_planning_get_warehouses(self, company):
        """Compatibilidad: devuelve almacenes derivados de ubicaciones PT/MP o legacy."""
        company = company or self.env.company
        Warehouse = self.env['stock.warehouse']
        pt_lines = self._kc_planning_get_location_lines(company, ['pt'])
        mp_lines = self._kc_planning_get_location_lines(company, ['mp'])
        pt_wh = pt_lines[:1].location_id.warehouse_id if pt_lines else False
        mp_wh = mp_lines[:1].location_id.warehouse_id if mp_lines else False
        if not pt_wh:
            pt_wh = company.kc_planning_pt_warehouse_id
        if not mp_wh:
            mp_wh = company.kc_planning_mp_warehouse_id or pt_wh
        if not pt_wh:
            pt_wh = Warehouse.search([('company_id', '=', company.id)], limit=1)
        if not mp_wh:
            mp_wh = pt_wh
        return pt_wh, mp_wh

    @api.model
    def _kc_planning_critical_bom_line(self, product, company):
        """Línea de LdM marcada como componente crítico (resina, bote sin etiquetar, etc.)."""
        if not product:
            return self.env['mrp.bom.line']
        Bom = self.env['mrp.bom']
        bom = Bom._bom_find(
            product,
            company_id=company.id if company else False,
            bom_type='normal',
        ).get(product)
        if not bom:
            return self.env['mrp.bom.line']
        critical = bom.bom_line_ids.filtered('kc_planning_critical_component')
        if len(critical) == 1:
            return critical
        return self.env['mrp.bom.line']

    @api.model
    def _kc_planning_mo_linked_domain(self, sale_line=None, product=None):
        domain = [('state', '!=', 'cancel')]
        if sale_line:
            domain.append(('sale_line_id', '=', sale_line.id))
        elif product:
            domain.append(('product_id', '=', product.id))
            domain.append(('sale_line_id', '!=', False))
        return domain

    @api.model
    def _kc_planning_mo_unlinked_domain(self, product, company=None):
        domain = [
            ('product_id', '=', product.id),
            ('sale_line_id', '=', False),
            ('state', 'not in', ('done', 'cancel')),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        return domain

    @api.model
    def _kc_planning_aggregate_mos(self, domain):
        """Devuelve dict con qty_planned, qty_produced, count, open_count."""
        Production = self.env['mrp.production']
        mos = Production.search(domain)
        open_states = ('draft', 'confirmed', 'progress', 'to_close')
        return {
            'mo_count': len(mos),
            'mo_open_count': len(mos.filtered(lambda m: m.state in open_states)),
            'mo_planned_qty': sum(mos.mapped('product_qty')),
            'mo_produced_qty': sum(mos.mapped('qty_produced')),
        }

    @api.model
    def _kc_planning_alert_state(
        self, qty_to_manufacture, pt_qty, mp_qty, has_critical, mo_produced_qty,
        wip_qty=0.0,
    ):
        if not has_critical:
            return 'warning'
        if qty_to_manufacture <= 0:
            return 'ok'
        covered = mo_produced_qty + pt_qty + (wip_qty or 0.0)
        if covered < qty_to_manufacture:
            return 'danger'
        if has_critical and mp_qty <= 0 and qty_to_manufacture > 0:
            return 'warning'
        return 'ok'
