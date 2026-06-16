# -*- coding: utf-8 -*-

from odoo import api, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._kc_planning_refresh_planning_cache()
        return records

    def write(self, vals):
        tracked = {'sale_line_id', 'product_id', 'product_qty', 'qty_produced', 'state', 'company_id'}
        res = super().write(vals)
        if tracked.intersection(vals):
            self._kc_planning_refresh_planning_cache()
        return res

    def unlink(self):
        sale_lines = self.mapped('sale_line_id')
        products = self.mapped('product_id')
        res = super().unlink()
        sale_lines._kc_planning_invalidate_from_mrp()
        products._kc_planning_invalidate_from_sale_lines()
        return res

    def _kc_planning_refresh_planning_cache(self):
        lines = self.mapped('sale_line_id').filtered(
            lambda l: l.state == 'sale' and not l.display_type
        )
        products = self.mapped('product_id') | lines.mapped('product_id')
        if lines:
            lines._kc_planning_invalidate_from_mrp()
        if products:
            products._kc_planning_invalidate_from_sale_lines()
