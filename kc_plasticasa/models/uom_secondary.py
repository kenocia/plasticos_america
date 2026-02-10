from odoo import api, fields, models
from odoo.tools import float_round


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    uom_secondary_id = fields.Many2one(
        related="product_id.product_tmpl_id.uom_secondary_id",
        string="Unidad alterna",
        readonly=True,
    )
    qty_secondary = fields.Float(
        string="Cantidad alterna",
        compute="_compute_qty_secondary",
    )

    @api.depends("product_uom_qty", "product_uom", "uom_secondary_id")
    def _compute_qty_secondary(self):
        for line in self:
            if line.uom_secondary_id and line.product_uom:
                qty = line.product_uom._compute_quantity(
                    line.product_uom_qty, line.uom_secondary_id
                )
                line.qty_secondary = float_round(
                    qty, precision_rounding=line.uom_secondary_id.rounding
                )
            else:
                line.qty_secondary = 0.0


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    uom_secondary_id = fields.Many2one(
        related="product_id.product_tmpl_id.uom_secondary_id",
        string="Unidad alterna",
        readonly=True,
    )
    qty_secondary = fields.Float(
        string="Cantidad alterna",
        compute="_compute_qty_secondary",
    )

    @api.depends("product_qty", "product_uom", "uom_secondary_id")
    def _compute_qty_secondary(self):
        for line in self:
            if line.uom_secondary_id and line.product_uom:
                qty = line.product_uom._compute_quantity(
                    line.product_qty, line.uom_secondary_id
                )
                line.qty_secondary = float_round(
                    qty, precision_rounding=line.uom_secondary_id.rounding
                )
            else:
                line.qty_secondary = 0.0


class StockMove(models.Model):
    _inherit = "stock.move"

    uom_secondary_id = fields.Many2one(
        related="product_id.product_tmpl_id.uom_secondary_id",
        string="Unidad alterna",
        readonly=True,
    )
    qty_secondary = fields.Float(
        string="Cantidad alterna",
        compute="_compute_qty_secondary",
    )

    @api.depends("product_uom_qty", "product_uom", "uom_secondary_id")
    def _compute_qty_secondary(self):
        for move in self:
            if move.uom_secondary_id and move.product_uom:
                qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, move.uom_secondary_id
                )
                move.qty_secondary = float_round(
                    qty, precision_rounding=move.uom_secondary_id.rounding
                )
            else:
                move.qty_secondary = 0.0


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    uom_secondary_id = fields.Many2one(
        related="product_id.product_tmpl_id.uom_secondary_id",
        string="Unidad alterna",
        readonly=True,
    )
    qty_secondary_done = fields.Float(
        string="Cantidad alterna",
        compute="_compute_qty_secondary_done",
    )

    @api.depends("qty_done", "product_uom_id", "uom_secondary_id")
    def _compute_qty_secondary_done(self):
        for line in self:
            if line.uom_secondary_id and line.product_uom_id:
                qty = line.product_uom_id._compute_quantity(
                    line.qty_done, line.uom_secondary_id
                )
                line.qty_secondary_done = float_round(
                    qty, precision_rounding=line.uom_secondary_id.rounding
                )
            else:
                line.qty_secondary_done = 0.0


class StockQuant(models.Model):
    _inherit = "stock.quant"

    uom_secondary_id = fields.Many2one(
        related="product_id.product_tmpl_id.uom_secondary_id",
        string="Unidad alterna",
        readonly=True,
    )
    qty_secondary = fields.Float(
        string="Cantidad alterna",
        compute="_compute_qty_secondary",
    )

    @api.depends("quantity", "product_id", "uom_secondary_id")
    def _compute_qty_secondary(self):
        for quant in self:
            if quant.uom_secondary_id and quant.product_id and quant.product_id.uom_id:
                qty = quant.product_id.uom_id._compute_quantity(
                    quant.quantity, quant.uom_secondary_id
                )
                quant.qty_secondary = float_round(
                    qty, precision_rounding=quant.uom_secondary_id.rounding
                )
            else:
                quant.qty_secondary = 0.0


class ProductProduct(models.Model):
    _inherit = "product.product"

    uom_secondary_id = fields.Many2one(
        related="product_tmpl_id.uom_secondary_id",
        string="Unidad alterna",
        readonly=True,
    )
    qty_secondary_available = fields.Float(
        string="Cantidad alterna",
        compute="_compute_qty_secondary_available",
    )

    @api.depends("qty_available", "uom_secondary_id", "uom_id")
    def _compute_qty_secondary_available(self):
        for product in self:
            if product.uom_secondary_id and product.uom_id:
                qty = product.uom_id._compute_quantity(
                    product.qty_available, product.uom_secondary_id
                )
                product.qty_secondary_available = float_round(
                    qty, precision_rounding=product.uom_secondary_id.rounding
                )
            else:
                product.qty_secondary_available = 0.0
