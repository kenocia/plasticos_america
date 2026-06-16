from odoo import models, api, fields
import datetime

class RequestNewPositions(models.Model):
    _name = 'request.new.positions'
    _inherit = ['mail.thread']
    _rec_name = 'position_id'

    request_date = fields.Date(string='Fecha de solicitud')
    manager_id = fields.Many2one('hr.employee', string='Manager que solicita')
    department_id = fields.Many2one('hr.department', related="manager_id.department_id", readonly=True,
                                    string="Department", help="Employee")
    position_id = fields.Many2one('hr.position', string='Plaza')
    state = fields.Selection([
        ('new', 'Nuevo'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada')
    ], string='Estado', default='new')
    date_processed = fields.Date(string='Fecha procesada')
    qty = fields.Integer(string='Cantidad de plazas')

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'approved':
            self.date_processed = datetime.datetime.now()
            Model = self.env['hr.job']
            result = Model.search([('department_id', '=', self.department_id.id), ('position_id', '=', self.position_id.id)])
            if result:
                result.no_of_recruitment = result.no_of_recruitment + self.qty
            else:
                Model.create({
                    'position_id': self.position_id.id,
                    'department_id': self.department_id.id,
                    'no_of_recruitment': self.qty,
                    'name': self.position_id.name
                })


