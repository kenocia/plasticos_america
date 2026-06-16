# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    commission_excluded = fields.Boolean(
        string='Excluir de comisión',
        default=False,
        help='Si está marcado, los productos de esta categoría no comisionan.',
    )
    commission_use_custom = fields.Boolean(
        string='Comisión específica (categoría)',
        default=False,
        help='Si está activo, se usan tipo y valor para productos de esta categoría (salvo que el producto tenga comisión propia).',
    )
    commission_type = fields.Selection(
        [
            ('unit', 'Por unidad'),
            ('percent', 'Por porcentaje'),
        ],
        string='Tipo comisión (categoría)',
    )
    commission_rate = fields.Float(
        string='Valor comisión (categoría)',
        digits=(16, 6),
    )
