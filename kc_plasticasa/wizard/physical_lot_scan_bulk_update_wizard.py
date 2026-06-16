# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class KcPhysicalLotScanBulkUpdateWizard(models.TransientModel):
    _name = 'kc.physical.lot.scan.bulk.update.wizard'
    _description = 'Actualización masiva — levantamiento físico previo'
    _inherit = ['kc.gs1.barcode.mixin']

    line_ids = fields.Many2many(
        'kc.physical.lot.scan.line',
        'kc_phys_lot_scan_bulk_wiz_line_rel',
        'wizard_id',
        'line_id',
        string='Líneas',
        readonly=True,
    )
    location_reported_id = fields.Many2one(
        'stock.location',
        string='Ubicación reportada',
        domain="[('id', 'in', kc_physical_allowed_location_ids)]",
    )
    last_movement_id = fields.Many2one(
        'stock.picking',
        string='Último movimiento',
        domain="[('state', '=', 'done')]",
    )
    last_movement_date = fields.Datetime(
        string='Fecha último movimiento',
    )
    last_movement_user_id = fields.Many2one(
        'res.users',
        string='Usuario último movimiento',
        default=lambda self: self.env.user,
    )
    update_location = fields.Boolean(
        string='Actualizar ubicación reportada',
        default=True,
    )
    update_movement = fields.Boolean(
        string='Actualizar último movimiento',
        default=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        if active_ids and 'line_ids' in fields_list:
            res['line_ids'] = [(6, 0, active_ids)]
        return res

    def _kc_physical_scan_company(self):
        self.ensure_one()
        if self.line_ids:
            return self.line_ids[:1].company_id
        lines = self.env['kc.physical.lot.scan.line'].browse(
            self.env.context.get('active_ids') or []
        )
        return lines[:1].company_id if lines else self.env.company

    @api.depends('line_ids', 'line_ids.company_id')
    def _compute_kc_physical_allowed_location_ids(self):
        return super()._compute_kc_physical_allowed_location_ids()

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay líneas seleccionadas.'))
        if not self.update_location and not self.update_movement:
            raise UserError(_('Marque al menos un tipo de actualización.'))
        if self.update_location and not self.location_reported_id:
            raise UserError(_('Indique la ubicación reportada.'))
        if self.update_movement and not self.last_movement_id:
            raise UserError(_('Indique el albarán de último movimiento.'))

        vals = {}
        if self.update_location:
            vals['location_reported_id'] = self.location_reported_id.id
        if self.update_movement:
            picking = self.last_movement_id
            vals.update({
                'last_movement_id': picking.id,
                'last_movement_date': (
                    self.last_movement_date
                    or picking.date_done
                    or picking.scheduled_date
                ),
                'last_movement_user_id': (
                    self.last_movement_user_id.id
                    or (picking.user_id.id if picking.user_id else self.env.user.id)
                ),
            })
        self.line_ids.write(vals)
        return {'type': 'ir.actions.act_window_close'}
