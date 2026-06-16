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
    kc_gs1_code = fields.Char(
        string='Código GS1 AI 240',
        index=True,
        help='Valor del producto tras el prefijo GS1 240 en el QR (ej: 8OZ-C-24-200P).',
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

    # Slack Saldos (reporte de saldos)
    slack_udm_id = fields.Many2one(
        'uom.uom',
        string='Unidad de medida',
        domain="[('category_id', '=', uom_category_id)]",
        help='Unidad de medida para saldos en Slack (misma categoría que la UdM de ventas / '
             '"por [unidad]" del producto).',
    )
    slack_location_ids = fields.Many2many(
        'stock.location',
        'product_tmpl_slack_location_rel',
        'product_tmpl_id',
        'location_id',
        string='Ubicaciones',
        domain="[('usage', '=', 'internal')]",
        help='Ubicaciones de inventario consideradas para el envío de saldos.',
    )
    slack_enviar_saldos = fields.Boolean(
        string='Enviar saldos',
        default=False,
        help='Si está activo, este producto participa en el envío de saldos a Slack.',
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

    def write(self, vals):
        """
        Fuerza el cambio de tracking / is_storable aunque el producto ya tenga
        movimientos de inventario, evitando el UserError del módulo stock.

        Estrategia:
        1) Sacamos tracking/is_storable de vals para que super().write() no entre
           en la validación estándar que bloquea el cambio.
        2) Guardamos el resto de campos normalmente.
        3) Aplicamos tracking/is_storable por SQL directo en product_template.
        4) Invalidamos caché y registramos mensaje en chatter.
        """
        vals = dict(vals or {})
        force_inventory_vals = {}

        if 'tracking' in vals:
            force_inventory_vals['tracking'] = vals.pop('tracking')

        if 'is_storable' in vals:
            force_inventory_vals['is_storable'] = vals.pop('is_storable')

        # 1) Guardar primero el resto de campos con lógica normal
        result = True
        if vals:
            result = super(ProductTemplate, self).write(vals)

        # 2) Si no hay cambios forzados de inventario, terminamos normal
        if not force_inventory_vals:
            return result

        # 3) Aplicar cambios forzados por SQL
        allowed_tracking = {'none', 'lot', 'serial'}

        for template in self:
            updates = []
            params = []

            if 'tracking' in force_inventory_vals:
                tracking_value = force_inventory_vals['tracking']
                if tracking_value not in allowed_tracking:
                    raise ValueError(_("Valor inválido para tracking: %s") % tracking_value)
                updates.append("tracking = %s")
                params.append(tracking_value)

            if 'is_storable' in force_inventory_vals:
                is_storable_value = force_inventory_vals['is_storable']
                updates.append("is_storable = %s")
                params.append(bool(is_storable_value))

            if not updates:
                continue

            updates.append("write_uid = %s")
            params.append(self.env.uid)

            updates.append("write_date = NOW()")
            params.append(template.id)

            sql = """
                UPDATE product_template
                   SET %s
                 WHERE id = %%s
            """ % ", ".join(updates)

            self.env.cr.execute(sql, params)

        # 4) Invalidar caché / marcar modificación
        modified_fields = list(force_inventory_vals.keys())
        self.invalidate_recordset(modified_fields)
        self.modified(modified_fields)

        # 5) Mensaje en chatter (si aplica)
        for template in self:
            msg_parts = []
            if 'tracking' in force_inventory_vals:
                msg_parts.append(_("Tracking forzado a: %s") % force_inventory_vals['tracking'])
            if 'is_storable' in force_inventory_vals:
                msg_parts.append(_("Track Inventory / is_storable forzado a: %s") % force_inventory_vals['is_storable'])

            body = "<br/>".join(msg_parts)
            if body and hasattr(template, 'message_post'):
                template.message_post(body=body)

        return result

    def action_force_inventory_tracking(self, tracking='none', is_storable=True):
        """
        Método utilitario por si luego quieres llamarlo desde shell,
        server action o botón.
        """
        self.ensure_one()
        values = {}
        if tracking is not None:
            values['tracking'] = tracking
        if is_storable is not None:
            values['is_storable'] = is_storable
        return self.write(values)

