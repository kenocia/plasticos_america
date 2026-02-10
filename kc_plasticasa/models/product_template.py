# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    uom_secondary_id = fields.Many2one(
        'uom.uom',
        string='Unidad alterna',
        help='Unidad alterna para equivalencias del producto'
    )

    # Campo para identificar si el producto es una bolsa
    is_bag = fields.Boolean(
        string='Es Bolsa',
        default=False,
        help='Marcar si este producto es una bolsa'
    )
    
    # Campos manuales para productos de Plasticasa
    thread_number = fields.Char(
        string='Número de Rosca',
        help='Número de rosca del producto'
    )
    machine = fields.Char(
        string='Máquina',
        help='Máquina utilizada para el producto'
    )
    grammage = fields.Float(
        string='Gramaje',
        digits=(16, 2),
        help='Gramaje del producto (en decimales)'
    )
    units_per_bale = fields.Integer(
        string='Unidades x Fardo',
        help='Cantidad de unidades por fardo'
    )
    
    # Campos de dimensiones de bolsa (solo si is_bag = True)
    bag_width = fields.Float(
        string='Ancho',
        digits=(16, 2),
        help='Ancho de la bolsa'
    )
    bag_height = fields.Float(
        string='Alto',
        digits=(16, 2),
        help='Alto de la bolsa'
    )
    bag_gusset = fields.Float(
        string='Fuelle / Fondo',
        digits=(16, 2),
        help='Fuelle o fondo de la bolsa'
    )
    bag_name = fields.Char(
        string='Nombre de Bolsa',
        compute='_compute_bag_name',
        store=True,
        readonly=True,
        help='Nombre generado automáticamente para la bolsa (ej: 27X60X1.8)'
    )
    
    # Campos de bolsas asignadas al producto (solo si is_bag = False)
    bag_1_id = fields.Many2one(
        'product.template',
        string='Bolsa 1',
        domain="[('is_bag', '=', True)]",
        help='Primera bolsa asignada al producto'
    )
    bag_2_id = fields.Many2one(
        'product.template',
        string='Bolsa 2',
        domain="[('is_bag', '=', True)]",
        help='Segunda bolsa asignada al producto'
    )

    @api.constrains('uom_secondary_id', 'uom_id')
    def _check_uom_secondary_category(self):
        for product in self:
            if product.uom_secondary_id and product.uom_id:
                if product.uom_secondary_id.category_id != product.uom_id.category_id:
                    raise ValidationError(
                        _('La unidad alterna debe pertenecer a la misma categoría que la unidad base.')
                    )

    @api.depends('bag_width', 'bag_height', 'bag_gusset', 'is_bag')
    def _compute_bag_name(self):
        """
        Generar nombre automáticamente con formato: AnchoXAltoXFuelle
        - Si solo hay un campo, NO se agrega X
        - Si hay múltiples campos, se agrega X entre ellos (máximo 2 X)
        - Fuelle/Fondo nunca agrega X al final
        Ejemplos: "27", "60", "27X60", "27X1.8", "60X1.8", "27X60X1.8"
        """
        for product in self:
            if not product.is_bag:
                product.bag_name = ''
                continue
                
            parts = []
            # Contar cuántos campos hay
            fields_count = sum([bool(product.bag_width), bool(product.bag_height), bool(product.bag_gusset)])
            
            # Si solo hay un campo, no agregar X
            if fields_count <= 1:
                if product.bag_width:
                    parts.append(str(product.bag_width))
                elif product.bag_height:
                    parts.append(str(product.bag_height))
                elif product.bag_gusset:
                    parts.append(str(product.bag_gusset))
            else:
                # Si hay múltiples campos, agregar X entre ellos
                # Si hay ancho, agregar con X si hay más campos después
                if product.bag_width:
                    parts.append(str(product.bag_width))
                    if product.bag_height or product.bag_gusset:
                        parts.append('X')
                
                # Si hay alto, agregar con X solo si hay fuelle después
                if product.bag_height:
                    parts.append(str(product.bag_height))
                    if product.bag_gusset:
                        parts.append('X')
                
                # Si hay fuelle/fondo, agregar SIN X (máximo 2 X permitidos)
                if product.bag_gusset:
                    parts.append(str(product.bag_gusset))
            
            # Unir todas las partes
            product.bag_name = ''.join(parts) if parts else ''

