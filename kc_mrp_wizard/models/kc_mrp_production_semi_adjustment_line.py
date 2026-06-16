# -*- coding: utf-8 -*-

from odoo import fields, models


class KcMrpProductionSemiAdjustmentLine(models.Model):
    _name = 'kc.mrp.production.semi.adjustment.line'
    _description = 'Salida / ajuste de inventario semi vinculado a MO'
    _order = 'id desc'
    _check_company_auto = True

    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento de stock',
        required=True,
        ondelete='restrict',
        index=True,
    )
    picking_id = fields.Many2one(
        related='stock_move_id.picking_id',
        string='Albarán',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related='stock_move_id.product_id',
        string='Producto',
        store=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        required=True,
        readonly=True,
    )
    quantity = fields.Float(
        string='Cantidad ajustada',
        digits='Product Unit of Measure',
        required=True,
        readonly=True,
    )
    is_scrap_desecho = fields.Boolean(
        string='Merma por desecho',
        help='Semi que no pasó a producción (envío a ubicación de merma / desecho).',
        required=True,
        default=False,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='production_id.company_id',
        store=True,
    )
