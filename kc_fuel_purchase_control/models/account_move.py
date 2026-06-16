from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_fuel_bill = fields.Boolean(string='Factura de combustible')
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
    actual_odometer = fields.Float(
        string='Odómetro real',
        help='En la misma unidad que el odómetro del vehículo (normalmente kilómetros).',
    )
    real_fuel_qty = fields.Float(
        string='Cantidad real combustible',
        compute='_compute_real_fuel_qty',
        store=True,
        help='En la unidad de medida del producto combustible del vale (ej. galones o litros).',
    )
    fuel_product_uom_id = fields.Many2one(
        'uom.uom',
        string='Udm combustible',
        related='fuel_voucher_id.fuel_product_id.uom_id',
        readonly=True,
    )
    fuel_distance_unit = fields.Selection(
        related='fuel_voucher_id.distance_unit',
        string='Unidad distancia',
        readonly=True,
    )
    distance_traveled = fields.Float(
        string='Distancia recorrida',
        compute='_compute_fuel_metrics',
        store=True,
        help='Diferencia de odómetro. Unidad: la indicada en el vale (km o millas).',
    )
    real_efficiency = fields.Float(
        string='Rendimiento real',
        compute='_compute_fuel_metrics',
        store=True,
        help='Distancia por unidad de combustible (ej. km/gal o mi/gal). No es porcentaje.',
    )

    @api.depends('invoice_line_ids.quantity', 'invoice_line_ids.product_id', 'fuel_voucher_id.fuel_product_id')
    def _compute_real_fuel_qty(self):
        for move in self:
            qty = 0.0
            if move.fuel_voucher_id and move.fuel_voucher_id.fuel_product_id:
                fuel_product = move.fuel_voucher_id.fuel_product_id
                for line in move.invoice_line_ids:
                    if line.product_id == fuel_product:
                        qty += line.quantity
            move.real_fuel_qty = qty

    @api.depends('actual_odometer', 'fuel_voucher_id.last_odometer', 'real_fuel_qty')
    def _compute_fuel_metrics(self):
        for move in self:
            dist = 0.0
            eff = 0.0
            if move.actual_odometer and move.fuel_voucher_id:
                last_odo = move.fuel_voucher_id.last_odometer
                if last_odo is not None:
                    raw = move.actual_odometer - last_odo
                    dist = raw if raw > 0 else 0.0
                    if move.real_fuel_qty > 0 and dist > 0:
                        eff = dist / move.real_fuel_qty
            move.distance_traveled = dist
            move.real_efficiency = eff

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if (
                move.move_type == 'in_invoice'
                and move.invoice_origin
                and not move.fuel_voucher_id
            ):
                po = self.env['purchase.order'].search(
                    [
                        ('name', '=', move.invoice_origin),
                        ('is_fuel_order', '=', True),
                    ],
                    limit=1,
                )
                if po and po.fuel_voucher_id:
                    move.is_fuel_bill = True
                    move.fuel_voucher_id = po.fuel_voucher_id
                    move.vehicle_id = po.vehicle_id
                    move.driver_id = po.driver_id
        return moves

    def _validate_fuel_invoice_before_post(self):
        for move in self:
            if (
                move.move_type == 'in_invoice'
                and move.is_fuel_bill
            ):
                if not move.vehicle_id:
                    raise UserError(_('Debe indicar el vehículo para la factura de combustible.'))
                if not move.fuel_voucher_id:
                    raise UserError(_('Debe vincular un vale de combustible a la factura.'))
                if move.actual_odometer is None or move.actual_odometer <= 0:
                    raise UserError(_('Debe indicar el odómetro real para la factura de combustible.'))
                last_odo = move.fuel_voucher_id.last_odometer
                if last_odo is not None and move.actual_odometer < last_odo:
                    raise UserError(
                        _('El odómetro real no puede ser menor que el último odómetro del vale (%s).') % last_odo
                    )
                if move.real_fuel_qty <= 0:
                    raise UserError(_('No se ha detectado cantidad real de combustible en la factura.'))

                log_model = self.env['fuel.consumption.log']
                existing_log = log_model.search([
                    ('vendor_bill_id', '=', move.id),
                ], limit=1)
                if existing_log:
                    continue

    def _create_fuel_consumption_log(self):
        log_model = self.env['fuel.consumption.log']
        for move in self:
            if not (
                move.move_type == 'in_invoice'
                and move.is_fuel_bill
                and move.fuel_voucher_id
            ):
                continue

            existing_log = log_model.search([
                ('vendor_bill_id', '=', move.id),
            ], limit=1)
            if existing_log:
                continue

            voucher = move.fuel_voucher_id
            po = voucher.purchase_order_id
            fuel_product = voucher.fuel_product_id

            fuel_lines = move.invoice_line_ids.filtered(
                lambda l: l.product_id == fuel_product
            )
            fuel_qty = sum(fuel_lines.mapped('quantity'))
            unit_price = 0.0
            total_amount = 0.0
            uom = fuel_product.uom_id if fuel_product else False
            if fuel_lines:
                line0 = fuel_lines[0]
                unit_price = line0.price_unit
                total_amount = sum(fuel_lines.mapped('price_subtotal'))
                uom = line0.product_uom_id

            log_vals = {
                'name': 'New',
                'company_id': move.company_id.id,
                'date': move.invoice_date or fields.Datetime.now(),
                'voucher_id': voucher.id,
                'purchase_order_id': po.id if po else False,
                'vendor_bill_id': move.id,
                'vehicle_id': voucher.vehicle_id.id,
                'driver_id': voucher.driver_id.id,
                'supplier_id': voucher.supplier_id.id,
                'fuel_product_id': fuel_product.id if fuel_product else False,
                'odometer_before': voucher.last_odometer,
                'odometer_after': move.actual_odometer,
                'fuel_qty': fuel_qty,
                'uom_id': uom.id if uom else False,
                'unit_price': unit_price,
                'total_amount': total_amount or move.amount_total,
                'analytic_account_id': voucher.analytic_account_id.id,
                'notes': voucher.reason,
            }
            log_model.create(log_vals)

            if voucher.vehicle_id:
                voucher.vehicle_id.current_odometer = move.actual_odometer

            voucher.vendor_bill_id = move
            voucher.actual_odometer = move.actual_odometer
            voucher.real_amount = total_amount or move.amount_total
            voucher.state = 'billed'

    def action_post(self):
        self._validate_fuel_invoice_before_post()
        res = super().action_post()
        self._create_fuel_consumption_log()
        return res

