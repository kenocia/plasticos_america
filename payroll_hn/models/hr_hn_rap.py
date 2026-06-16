from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from odoo.osv import expression

class HrHnRap(models.Model):
    _name = 'hr.hn.rap'
    _description = 'RAP HN'
    _inherit = ['mail.thread']

    name = fields.Char(string="Nombre", required=True, tracking=True, copy=False)
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency', default=lambda self:self.env.user.company_id.currency_id.id, required=True)
    state = fields.Selection(string="Estado", selection=[('draft', 'Inactivo'),('active','Activo'),], default='draft', tracking=True)
    percentage_rap = fields.Float("Porcentaje Aplicar", required=True)
    contract_count = fields.Integer(string="Contratos", compute="_compute_count")
    limit_amount = fields.Float(string="Monto")

    @api.depends("name")
    def _compute_count(self):
        for rap in self:
            contracts = self.env['hr.contract'].search_count([('rap_id','=',rap.id)])
            rap.contract_count = contracts

    _sql_constraints = [('name_unique', 'unique(name)', '¡El nombre debe ser único!'),]

    """ Verifica y valida que solo pueda existir un registro activo a la vez. """
    @api.constrains('state')
    def _check_unique_active_state(self):
        for record in self:
            active_records = self.search_count([('state', '=', 'active'), ('id', '!=', record.id)])
            if record.state == 'active' and active_records > 0:
                raise ValidationError("¡Ya existe un registro activo!")

    """ Establece el estado como borrador y elimina todas las lineas. """
    def action_draft(self):
        self.write({'state': 'draft'})
    
    """ Establece el estado como activo. """
    def action_active(self):
        self.write({'state': 'active'})


class HrHnRapAssign(models.TransientModel):
    _name = 'hr.hn.rap.assign'
    _description = 'Asignar RAP'

    def _get_available_contracts_domain(self):
        return [('company_id', '=', self.env.company.id)]

    def _get_employees(self):
        return self.env['hr.employee'].search(self._get_available_contracts_domain())

    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department")
    schedule_pay = fields.Selection(string="Pago programado", selection=[('annually', 'Anualmente'),('semi-annually', 'Semestralmente'),('quarterly', 'Trimestral'),('bi-monthly', 'Bimestral'),('monthly', 'Mensual'),('bi-weekly', 'Quincenal'),('weekly', 'Semanalmente')])
    apply_in = fields.Selection([('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')], string="Aplicar en", default="both")
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_rap_assign_rel', 'assign_id', 'employee_id', 'Employees', default=lambda self: self._get_employees(), required=True, compute='_compute_employee_ids', store=True, readonly=False)

    @api.depends('department_id','schedule_pay')
    def _compute_employee_ids(self):
        for wizard in self:
            domain = wizard._get_available_contracts_domain()
            if wizard.department_id:
                domain = expression.AND([
                    domain,
                    [('department_id', 'child_of', self.department_id.id)]
                ])
            if wizard.schedule_pay:
                domain = expression.AND([
                    domain,
                    [('contract_ids.schedule_pay', '=', self.schedule_pay)]
                ])
            wizard.employee_ids = self.env['hr.employee'].search(domain)

    def action_assign(self):
        if not self.employee_ids:
            raise ValidationError(_('No se puede asignar cuentas a reglas si no hay empleados seleccionados.'))
        
        for employee in self.employee_ids:
            contract_id = self.env['hr.contract'].search([('employee_id','=',employee.id),('state','=','open')], limit=1)
            rap_id = self.env['hr.hn.rap'].search([('state','=','active')])

            if not contract_id:
                raise ValidationError(f"El empleado {employee.name} no cuenta con un contrato vigente.")
            
            if self.schedule_pay != contract_id.schedule_pay:
                raise ValidationError(f"El empleado {employee.name} cuenta con un pago programado distinto al que se quiere aplicar.")
            
            if self.schedule_pay == 'semi-monthly':
                contract_id.write({'apply_rap':True, 'rap_id':rap_id.id, 'apply_in_rap':self.apply_in})

            else:
                contract_id.write({'apply_rap':True, 'rap_id':rap_id.id})

