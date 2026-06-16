# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    kc_tablet_register_semi = fields.Boolean(
        string='Registra semiterminado (tablet)',
        help='Indica que en esta operación se declaran cantidades y tickets de semiterminado (sin lote de stock de PT).',
    )
    kc_skip_sequential_wo_dependency = fields.Boolean(
        string='Sin esperar a la operación anterior (secuencia)',
        help='Solo aplica cuando la LdM no usa «dependencias entre operaciones»: Odoo por defecto encadena cada '
             'orden de trabajo con la anterior en la secuencia. Si marca esta casilla, esta operación podrá pasar '
             'a lista/en progreso aunque la anterior siga abierta (p. ej. etiquetado PT mientras soplado/semi sigue en curso). '
             'Las órdenes posteriores siguen enlazándose a la inmediatamente anterior en la lista.',
    )
    kc_semi_product_id = fields.Many2one(
        'product.product',
        string='Semiterminado (identidad)',
        domain="[('type', 'in', ('consu', 'product'))]",
        help='Opcional. Si se define, puede usarse en etiqueta y, si aplica, movimientos a WIP.',
    )
    kc_semi_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM declaración semi',
        help='Si no hay producto, defina la unidad de la cantidad reportada. Si hay producto, se usa siempre la UdM del producto (no editable).',
    )
    kc_semi_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación semi',
        help='Contenedor de semi asociado a esta operación. Usado en flujos MRP / semiacabado.',
        check_company=True,
    )
    kc_semi_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo de operación (semi)',
        help='Tipo de operación de inventario a usar al crear el albarán/movimiento de semi para esta operación '
             '(origen y destino por defecto vienen del tipo). Solo tipos de transferencia interna.',
        domain="[('code', '=', 'internal')]",
        check_company=True,
    )
    kc_semi_print_ticket = fields.Boolean(
        string='Imprimir ticket',
        help='Si está activo y el centro de trabajo tiene impresora de red de etiquetas, al registrar semi '
             'desde el MRP se dispara la impresión de la etiqueta. Sin impresora en el WC no se imprime.',
    )

    @api.constrains('kc_tablet_register_semi', 'kc_semi_product_id', 'kc_semi_uom_id')
    def _kc_check_semi_declaration_uom(self):
        for op in self:
            if not op.kc_tablet_register_semi:
                continue
            if op.kc_semi_product_id:
                continue
            if not op.kc_semi_uom_id:
                raise ValidationError(_(
                    'En la operación "%s" está activo "Registra semiterminado" sin producto: '
                    'debe indicar "UdM declaración semi".'
                ) % (op.name or op.display_name,))

    @api.onchange('kc_semi_product_id')
    def _onchange_kc_semi_product_id(self):
        for op in self:
            if op.kc_semi_product_id and op.kc_semi_product_id.uom_id:
                op.kc_semi_uom_id = op.kc_semi_product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prod_id = vals.get('kc_semi_product_id')
            if prod_id:
                prod = self.env['product.product'].browse(prod_id)
                if prod.exists() and prod.uom_id:
                    vals['kc_semi_uom_id'] = prod.uom_id.id
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        prod_id = vals.get('kc_semi_product_id')
        if prod_id:
            prod = self.env['product.product'].browse(prod_id)
            if prod.exists() and prod.uom_id:
                vals['kc_semi_uom_id'] = prod.uom_id.id
        res = super().write(vals)
        # Si había producto y se intentó fijar otra UdM (RPC/import), forzar la del producto
        mismatch = self.filtered(
            lambda o: o.kc_semi_product_id
            and o.kc_semi_product_id.uom_id
            and o.kc_semi_uom_id != o.kc_semi_product_id.uom_id
        )
        for op in mismatch:
            super(MrpRoutingWorkcenter, op).write({'kc_semi_uom_id': op.kc_semi_product_id.uom_id.id})
        return res
