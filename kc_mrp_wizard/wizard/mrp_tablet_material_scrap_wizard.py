# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class MrpTabletMaterialScrapWizard(models.TransientModel):
    _name = 'mrp.tablet.material.scrap.wizard'
    _description = 'Asistente tablet: merma de material (MO)'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        readonly=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        related='workorder_id.production_id',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='production_id.company_id',
        readonly=True,
    )
    move_raw_id = fields.Many2one(
        'stock.move',
        string='Componente (lista de materiales)',
        required=True,
        domain="[('id', 'in', allowed_move_raw_ids)]",
    )
    allowed_move_raw_ids = fields.Many2many(
        'stock.move',
        compute='_compute_allowed_move_raw_ids',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        related='move_raw_id.product_id',
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad',
        related='move_raw_id.product_uom',
        readonly=True,
    )
    tracking = fields.Selection(
        related='product_id.tracking',
        readonly=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote / serie',
        domain="[('id', 'in', allowed_lot_ids)]",
    )
    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_allowed_lot_ids',
    )
    type_id = fields.Many2one(
        'kc.mrp.resin.scrap.type',
        string='Tipo de merma',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Obligatorio al confirmar; no en create del asistente (el usuario lo elige en el formulario).',
    )
    quantity = fields.Float(
        string='Cantidad',
        digits='Product Unit of Measure',
        default=0.0,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de consumo',
        related='move_raw_id.location_id',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        wo_id = res.get('workorder_id') or self.env.context.get('default_workorder_id')
        if wo_id:
            wo = self.env['mrp.workorder'].browse(wo_id)
            if wo.exists():
                company = wo.company_id or company
        if 'type_id' in fields_list and not res.get('type_id'):
            scrap_types = self.env['kc.mrp.resin.scrap.type'].search([
                ('active', '=', True),
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ], order='name', limit=2)
            if len(scrap_types) == 1:
                res['type_id'] = scrap_types.id
        return res

    @api.depends('production_id')
    def _compute_allowed_move_raw_ids(self):
        Move = self.env['stock.move']
        for wizard in self:
            if wizard.production_id:
                wizard.allowed_move_raw_ids = wizard.production_id._kc_tablet_material_scrap_raw_moves()
            else:
                wizard.allowed_move_raw_ids = Move

    @api.depends('move_raw_id', 'product_id', 'location_id')
    def _compute_allowed_lot_ids(self):
        Lot = self.env['stock.lot']
        Quant = self.env['stock.quant']
        for wizard in self:
            if (
                not wizard.product_id
                or wizard.product_id.tracking == 'none'
                or not wizard.location_id
            ):
                wizard.allowed_lot_ids = Lot
                continue
            quants = Quant.search([
                ('product_id', '=', wizard.product_id.id),
                ('location_id', '=', wizard.location_id.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ])
            wizard.allowed_lot_ids = quants.mapped('lot_id')

    @api.onchange('move_raw_id')
    def _onchange_move_raw_id(self):
        self.lot_id = False
        if self.move_raw_id and self.product_id and self.product_id.tracking != 'none':
            if len(self.allowed_lot_ids) == 1:
                self.lot_id = self.allowed_lot_ids[:1]

    def action_confirm(self):
        self.ensure_one()
        if float_is_zero(
            self.quantity,
            precision_rounding=self.product_uom_id.rounding if self.product_uom_id else 1e-6,
        ):
            raise UserError(_('Indique una cantidad mayor que cero.'))
        if not self.type_id:
            raise UserError(_('Seleccione el tipo de merma.'))
        wo = self.workorder_id
        if not wo.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        mo = self.production_id
        if mo.state in ('done', 'cancel'):
            raise UserError(_('No se puede registrar merma en una orden de fabricación terminada o cancelada.'))
        if self.move_raw_id.raw_material_production_id != mo:
            raise UserError(_('El componente seleccionado no pertenece a esta orden de fabricación.'))
        if self.product_id.tracking != 'none' and not self.lot_id:
            raise UserError(
                _('El producto «%s» requiere lote o número de serie para registrar la merma.')
                % self.product_id.display_name
            )
        return wo._tablet_finish_material_scrap_wizard(self)
