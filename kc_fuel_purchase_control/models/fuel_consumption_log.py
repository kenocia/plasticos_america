from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FuelConsumptionLog(models.Model):
    _name = 'fuel.consumption.log'
    _description = 'Historial de consumo de combustible'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Referencia',
        readonly=True,
        copy=False,
        default='New',
    )
    date = fields.Datetime(
        string='Fecha',
        default=fields.Datetime.now,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    voucher_id = fields.Many2one(
        'fuel.voucher',
        string='Vale de combustible',
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de compra',
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Factura proveedor',
    )
    vehicle_id = fields.Many2one(
        'fuel.vehicle',
        string='Vehículo',
        required=True,
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Motorista',
    )
    supplier_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
    )
    fuel_product_id = fields.Many2one(
        'product.product',
        string='Producto combustible',
    )
    distance_unit = fields.Selection(
        related='vehicle_id.distance_unit',
        string='Unidad distancia',
        readonly=True,
    )
    odometer_before = fields.Float(string='Odómetro antes')
    odometer_after = fields.Float(string='Odómetro después')
    distance_traveled = fields.Float(
        string='Distancia recorrida',
        compute='_compute_metrics',
        store=True,
    )
    fuel_qty = fields.Float(string='Cantidad de combustible')
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de medida',
    )
    unit_price = fields.Monetary(string='Precio unitario')
    total_amount = fields.Monetary(string='Monto total')
    efficiency = fields.Float(
        string='Rendimiento',
        compute='_compute_metrics',
        store=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta analítica',
    )
    notes = fields.Text(string='Notas')
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            'unique_vendor_bill',
            'unique(vendor_bill_id)',
            'Ya existe un historial de consumo para esta factura de proveedor.',
        )
    ]

    @api.depends('odometer_before', 'odometer_after', 'fuel_qty')
    def _compute_metrics(self):
        for log in self:
            dist = 0.0
            eff = 0.0
            if log.odometer_after and log.odometer_before is not None:
                raw = log.odometer_after - log.odometer_before
                dist = raw if raw > 0 else 0.0
                if log.fuel_qty > 0 and dist > 0:
                    eff = dist / log.fuel_qty
            log.distance_traveled = dist
            log.efficiency = eff

    @api.constrains('odometer_before', 'odometer_after')
    def _check_odometer(self):
        for log in self:
            if (
                log.odometer_after
                and log.odometer_before is not None
                and log.odometer_after < log.odometer_before
            ):
                raise ValidationError(
                    _('El odómetro después no puede ser menor que el odómetro antes.')
                )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            seq = self.env.ref('kc_fuel_purchase_control.seq_fuel_consumption_log', raise_if_not_found=False)
            if seq:
                vals['name'] = seq.next_by_id()
        return super().create(vals)

