from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class FuelVoucher(models.Model):
    _name = 'fuel.voucher'
    _description = 'Vale de combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número de vale',
        readonly=True,
        copy=False,
        default='New',
    )
    date = fields.Datetime(
        string='Fecha',
        default=fields.Datetime.now,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('requested', 'Solicitado'),
            ('approved', 'Aprobado'),
            ('po_created', 'OC Creada'),
            ('billed', 'Facturado'),
            ('closed', 'Cerrado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
    )

    vehicle_id = fields.Many2one(
        'fuel.vehicle',
        string='Vehículo',
        required=True,
        tracking=True,
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Motorista',
        tracking=True,
    )
    supplier_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
    )
    fuel_product_id = fields.Many2one(
        'product.product',
        string='Producto combustible',
        required=True,
        tracking=True,
    )
    fuel_type = fields.Selection(
        [
            ('regular', 'Regular'),
            ('super', 'Super'),
            ('diesel', 'Diésel'),
            ('other', 'Otro'),
        ],
        string='Tipo de combustible',
        tracking=True,
    )
    authorized_amount = fields.Monetary(
        string='Monto autorizado',
        currency_field='currency_id',
        tracking=True,
        help='Autorización por monto. Rellene monto o volumen (galones/litros según la U.M.), no es obligatorio ambos; '
        'si indica ambos, el monto rige al crear la orden de compra.',
    )
    authorized_qty = fields.Float(
        string='Galones / volumen autorizado',
        tracking=True,
        help='Autorización por volumen; el monto de la OC se estima con el costo estándar del producto.',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de medida',
        help="Unidad de medida del combustible (ej. galones, litros).",
    )
    distance_unit = fields.Selection(
        [
            ('km', 'Kilómetros'),
            ('mi', 'Millas'),
        ],
        string='Unidad de distancia',
        default='km',
        help='Unidad del odómetro y de la distancia (viene del vehículo, se puede cambiar por vale).',
    )
    last_odometer = fields.Float(
        string='Último odómetro',
        tracking=True,
    )
    projected_odometer = fields.Float(
        string='Odómetro proyectado',
        tracking=True,
    )
    actual_odometer = fields.Float(
        string='Odómetro real',
        tracking=True,
    )
    distance_traveled = fields.Float(
        string='Distancia proyectada',
        compute='_compute_distance_traveled',
        store=True,
    )
    expected_efficiency = fields.Float(
        string='Rendimiento esperado',
        help="Rendimiento esperado del vehículo (distancia por unidad de combustible).",
    )
    real_efficiency = fields.Float(
        string='Rendimiento real',
        compute='_compute_real_efficiency',
        store=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta analítica',
    )
    reason = fields.Text(string='Motivo / referencia')

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de compra',
        readonly=True,
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Factura proveedor',
        readonly=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )
    authorized_amount_estimated = fields.Monetary(
        string='Monto estimado autorizado',
        compute='_compute_authorized_amount_estimated',
        store=True,
        currency_field='currency_id',
    )
    real_amount = fields.Monetary(
        string='Monto real',
        currency_field='currency_id',
        readonly=True,
    )
    notes = fields.Text(string='Notas')

    consumption_log_count = fields.Integer(
        string='Historial de consumo',
        compute='_compute_consumption_log_count',
    )

    @api.depends('projected_odometer', 'last_odometer')
    def _compute_distance_traveled(self):
        for voucher in self:
            if voucher.projected_odometer and voucher.last_odometer is not None:
                dist = voucher.projected_odometer - voucher.last_odometer
                voucher.distance_traveled = dist if dist > 0 else 0.0
            else:
                voucher.distance_traveled = 0.0

    @api.depends('actual_odometer', 'last_odometer', 'vendor_bill_id.real_fuel_qty')
    def _compute_real_efficiency(self):
        for voucher in self:
            real_qty = voucher.vendor_bill_id.real_fuel_qty if voucher.vendor_bill_id else 0.0
            if (
                voucher.actual_odometer
                and voucher.last_odometer is not None
                and real_qty > 0
            ):
                dist = voucher.actual_odometer - voucher.last_odometer
                voucher.real_efficiency = dist / real_qty if dist > 0 else 0.0
            else:
                voucher.real_efficiency = 0.0

    @api.depends(
        'authorized_qty',
        'authorized_amount',
        'fuel_product_id',
        'fuel_product_id.standard_price',
        'company_id',
    )
    def _compute_authorized_amount_estimated(self):
        for voucher in self:
            amount = 0.0
            if voucher.authorized_amount:
                amount = voucher.authorized_amount
            elif voucher.authorized_qty > 0 and voucher.fuel_product_id:
                price = voucher.fuel_product_id.standard_price or 0.0
                amount = voucher.authorized_qty * price
            voucher.authorized_amount_estimated = amount

    @api.depends('vendor_bill_id')
    def _compute_consumption_log_count(self):
        log_model = self.env['fuel.consumption.log']
        for voucher in self:
            voucher.consumption_log_count = log_model.search_count([
                ('voucher_id', '=', voucher.id),
            ])

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        for voucher in self:
            if voucher.vehicle_id:
                vehicle = voucher.vehicle_id
                voucher.driver_id = vehicle.driver_id
                voucher.fuel_product_id = vehicle.fuel_product_id or voucher.fuel_product_id
                voucher.analytic_account_id = vehicle.analytic_account_id or voucher.analytic_account_id
                voucher.last_odometer = vehicle.current_odometer
                voucher.expected_efficiency = vehicle.expected_efficiency
                voucher.fuel_type = vehicle.fuel_type or voucher.fuel_type
                voucher.distance_unit = vehicle.distance_unit
                if vehicle.fuel_product_id and not voucher.uom_id:
                    voucher.uom_id = vehicle.fuel_product_id.uom_id

    @api.constrains('authorized_qty', 'authorized_amount')
    def _check_authorized_qty_or_amount(self):
        for voucher in self:
            has_amount = bool(voucher.authorized_amount and voucher.authorized_amount > 0)
            has_qty = bool(voucher.authorized_qty and voucher.authorized_qty > 0)
            if not has_amount and not has_qty:
                raise ValidationError(
                    _('Debe indicar un monto autorizado o un volumen (galones/litros) mayor que cero.')
                )

    @api.constrains('projected_odometer', 'last_odometer')
    def _check_projected_odometer(self):
        for voucher in self:
            if (
                voucher.projected_odometer
                and voucher.last_odometer is not None
                and voucher.projected_odometer < voucher.last_odometer
            ):
                raise ValidationError(
                    _('El odómetro proyectado no puede ser menor que el último odómetro.')
                )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            seq = self.env.ref('kc_fuel_purchase_control.seq_fuel_voucher', raise_if_not_found=False)
            if seq:
                vals['name'] = seq.next_by_id()
        return super().create(vals)

    def action_request(self):
        for voucher in self:
            if voucher.state != 'draft':
                raise UserError(_('Solo los vales en borrador pueden solicitarse.'))
            voucher.state = 'requested'
        return True

    def action_approve(self):
        for voucher in self:
            if voucher.state not in ('requested', 'draft'):
                raise UserError(_('Solo los vales en borrador o solicitados pueden aprobarse.'))
            voucher.state = 'approved'
        return True

    def action_cancel(self):
        for voucher in self:
            voucher.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        for voucher in self:
            if voucher.state not in ('cancelled', 'draft'):
                raise UserError(_('Solo se puede regresar a borrador desde cancelado o borrador.'))
            voucher.state = 'draft'
        return True

    def action_close(self):
        for voucher in self:
            if voucher.state != 'billed':
                raise UserError(_('Solo se pueden cerrar vales facturados.'))
            voucher.state = 'closed'
        return True

    def _get_purchase_line_price_unit(self):
        """Precio unitario de la línea de compra (cantidad fija 1): monto explícito o volumen × costo estándar."""
        self.ensure_one()
        if self.authorized_amount and self.authorized_amount > 0:
            return self.authorized_amount
        if self.authorized_qty and self.authorized_qty > 0 and self.fuel_product_id:
            price = self.fuel_product_id.standard_price or 0.0
            return self.authorized_qty * price
        return 0.0

    def action_create_purchase_order(self):
        PurchaseOrder = self.env['purchase.order']
        for voucher in self:
            if voucher.state != 'approved':
                raise UserError(_('Solo los vales aprobados pueden generar una orden de compra.'))
            if voucher.purchase_order_id:
                raise UserError(_('Este vale ya tiene una orden de compra asociada.'))
            if not voucher.fuel_product_id:
                raise UserError(_('Debe indicar un producto de combustible.'))

            uom = voucher.uom_id or voucher.fuel_product_id.uom_po_id or voucher.fuel_product_id.uom_id
            price_unit = voucher._get_purchase_line_price_unit()
            if price_unit <= 0:
                raise UserError(
                    _(
                        'El monto de la orden de compra debe ser mayor que cero. '
                        'Indique un monto autorizado o un volumen con costo estándar del producto.'
                    )
                )
            vol_note = ''
            if voucher.authorized_qty and voucher.authorized_qty > 0:
                vol_note = _(
                    ' Volumen referencia: %(qty)s %(uom)s.',
                    qty=voucher.authorized_qty,
                    uom=uom.name or '',
                )
            description = _(
                'Combustible para vehículo %(vehicle)s (Placa: %(plate)s) - Vale: %(voucher)s.%(vol)s',
                vehicle=voucher.vehicle_id.name or '',
                plate=voucher.vehicle_id.plate or '',
                voucher=voucher.name,
                vol=vol_note,
            )

            po_vals = {
                'partner_id': voucher.supplier_id.id,
                'company_id': voucher.company_id.id,
                'origin': voucher.name,
                'is_fuel_order': True,
                'fuel_voucher_id': voucher.id,
                'vehicle_id': voucher.vehicle_id.id,
                'driver_id': voucher.driver_id.id,
                'last_odometer': voucher.last_odometer,
                'projected_odometer': voucher.projected_odometer,
                'reason': voucher.reason,
                'order_line': [
                    (
                        0,
                        0,
                        {
                            'product_id': voucher.fuel_product_id.id,
                            'name': description,
                            'product_qty': 1.0,
                            'product_uom': uom.id,
                            'price_unit': price_unit,
                        },
                    )
                ],
            }
            po = PurchaseOrder.create(po_vals)
            voucher.purchase_order_id = po
            voucher.state = 'po_created'
        return True

    def action_view_purchase_order(self):
        self.ensure_one()
        if not self.purchase_order_id:
            return False
        action = self.env.ref('purchase.purchase_rfq').read()[0]
        action['views'] = [(False, 'form')]
        action['res_id'] = self.purchase_order_id.id
        return action

    def action_view_vendor_bill(self):
        self.ensure_one()
        if not self.vendor_bill_id:
            return False
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        action['views'] = [(False, 'form')]
        action['res_id'] = self.vendor_bill_id.id
        return action

    def action_view_consumption_logs(self):
        self.ensure_one()
        action = self.env.ref('kc_fuel_purchase_control.action_fuel_consumption_log').read()[0]
        action['domain'] = [('voucher_id', '=', self.id)]
        return action

