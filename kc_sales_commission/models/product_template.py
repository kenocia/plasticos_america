# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    commission_excluded = fields.Boolean(
        string='Excluir de comisión',
        default=False,
        help='Si está marcado, este producto no genera líneas de comisión.',
    )
    commission_use_custom = fields.Boolean(
        string='Comisión específica',
        default=False,
        help='Si está activo, se usan tipo y valor de comisión de este producto en lugar de categoría o empleado.',
    )
    commission_type = fields.Selection(
        [
            ('unit', 'Por unidad'),
            ('percent', 'Por porcentaje'),
        ],
        string='Tipo comisión (producto)',
    )
    commission_rate = fields.Float(
        string='Valor comisión (producto)',
        digits=(16, 6),
    )
