# -*- coding: utf-8 -*-

from odoo import api, fields, models


class KcMrpResinScrapType(models.Model):
    _name = 'kc.mrp.resin.scrap.type'
    _description = 'Tipo merma de material (KenoCia)'
    _order = 'name'

    name = fields.Char(string='Descripción', required=True, translate=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)


class KcMrpProductionResinScrap(models.Model):
    _name = 'kc.mrp.production.resin.scrap'
    _description = 'Línea merma material'
    _check_company_auto = True

    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Operación',
        ondelete='set null',
        index=True,
        help='Orden de trabajo desde la que se registró la merma en tablet.',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        ondelete='restrict',
    )
    type_id = fields.Many2one(
        'kc.mrp.resin.scrap.type',
        string='Tipo de merma',
        required=True,
        ondelete='restrict',
    )
    scrap_id = fields.Many2one(
        'stock.scrap',
        string='Desecho de inventario',
        required=True,
        ondelete='restrict',
        index=True,
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento de stock',
        compute='_compute_stock_move_id',
        store=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='restrict',
    )
    quantity = fields.Float(
        string='Cantidad',
        required=True,
        digits='Product Unit of Measure',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        related='product_id.uom_id',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='production_id.company_id',
        store=True,
    )

    @api.depends('scrap_id', 'scrap_id.move_ids')
    def _compute_stock_move_id(self):
        for line in self:
            line.stock_move_id = line.scrap_id.move_ids[:1]
