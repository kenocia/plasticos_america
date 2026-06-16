from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FuelVehicle(models.Model):
    _name = 'fuel.vehicle'
    _description = 'Vehículo para control de combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char(string='Nombre', required=True, tracking=True)
    display_name = fields.Char(
        string='Descripción',
        compute='_compute_display_name',
        store=True,
    )
    code = fields.Char(string='Código', tracking=True)
    plate = fields.Char(string='Placa', required=True, tracking=True)
    brand = fields.Char(string='Marca')
    model = fields.Char(string='Modelo')
    year = fields.Integer(string='Año')
    driver_id = fields.Many2one(
        'hr.employee',
        string='Motorista',
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
    fuel_product_id = fields.Many2one(
        'product.product',
        string='Producto combustible',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta analítica',
    )
    distance_unit = fields.Selection(
        [
            ('km', 'Kilómetros'),
            ('mi', 'Millas'),
        ],
        string='Unidad de distancia',
        default='km',
        tracking=True,
        help='Unidad en la que se registra el odómetro (y la distancia recorrida).',
    )
    current_odometer = fields.Float(
        string='Odómetro actual',
        tracking=True,
    )
    expected_efficiency = fields.Float(
        string='Rendimiento esperado (distancia/U.M.)',
        help="Rendimiento esperado del vehículo (distancia por unidad de combustible).",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notas')

    _sql_constraints = [
        (
            'plate_company_uniq',
            'unique(plate, company_id)',
            'La placa del vehículo debe ser única por compañía.',
        ),
    ]

    @api.depends('name', 'plate', 'code')
    def _compute_display_name(self):
        for vehicle in self:
            parts = [p for p in [vehicle.code, vehicle.name, vehicle.plate] if p]
            vehicle.display_name = ' / '.join(parts) if parts else _('Vehículo')

    @api.constrains('current_odometer')
    def _check_current_odometer(self):
        for vehicle in self:
            if vehicle.current_odometer < 0:
                raise ValidationError(_('El odómetro actual no puede ser negativo.'))

