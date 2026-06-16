from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_fuel_order = fields.Boolean(string='Orden de combustible', default=False)
    fuel_voucher_id = fields.Many2one(
        'fuel.voucher',
        string='Vale de combustible',
    )
    vehicle_id = fields.Many2one(
        'fuel.vehicle',
        string='Vehículo',
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Motorista',
    )
    last_odometer = fields.Float(string='Último odómetro')
    projected_odometer = fields.Float(string='Odómetro proyectado')
    reason = fields.Text(string='Motivo / referencia')

