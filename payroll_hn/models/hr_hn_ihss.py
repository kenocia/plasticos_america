from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from odoo.osv import expression

class HrHnIhss(models.Model):
    _name = 'hr.hn.ihss'
    _description = 'IHSS HN'
    _inherit = ['mail.thread']

    name = fields.Char(string="Nombre", required=True, tracking=True, copy=False)
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency', default=lambda self:self.env.user.company_id.currency_id.id, required=True)
    state = fields.Selection(string="Estado", selection=[('draft', 'Inactivo'),('active','Activo'),], default='draft', tracking=True)
    percentage_enf_mat = fields.Float(string="Porcentaje ENF-MAT", tracking=True)
    percentage_ivm = fields.Float(string="Porcentaje IVM", tracking=True)
    limit_enf_mat = fields.Float(string="Techo ENF-MAT", tracking=True)
    limit_ivm = fields.Float(string="Techo IVM", tracking=True)
    fee_enf_mat = fields.Float(string="Cuota ENF-MAT", compute="_compute_calculate_fees", store=True, tracking=True)
    fee_ivm = fields.Float(string="Cuota IVM", compute="_compute_calculate_fees", store=True, tracking=True)
    fee_ihss = fields.Float(string="Cuota IHSS", compute="_compute_calculate_fees", store=True, tracking=True)
    contract_count = fields.Integer(string="Contratos", compute="_compute_count")

    @api.depends("name")
    def _compute_count(self):
        for ihss in self:
            contracts = self.env['hr.contract'].search_count([('ihss_id','=',ihss.id)])
            ihss.contract_count = contracts

    _sql_constraints = [('name_unique', 'unique(name)', '¡El nombre debe ser único!'),]

    """ Calcula el valor de las cuotas. """
    @api.depends('limit_enf_mat','limit_ivm','percentage_enf_mat','percentage_ivm')
    def _compute_calculate_fees(self):
        for rec in self:
            rec.fee_enf_mat = rec.limit_enf_mat * rec.percentage_enf_mat
            rec.fee_ivm = rec.limit_ivm * rec.percentage_ivm
            rec.fee_ihss = rec.fee_enf_mat + rec.fee_ivm

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
    

class HrHnIhssAssign(models.TransientModel):
    _name = 'hr.hn.ihss.assign'
    _description = 'Asignar IHSS'

    def _get_available_contracts_domain(self):
        return [('company_id', '=', self.env.company.id)]

    def _get_employees(self):
        return self.env['hr.employee'].search(self._get_available_contracts_domain())

    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department")
    schedule_pay = fields.Selection(string="Pago programado", selection=[('annually', 'Anualmente'),('semi-annually', 'Semestralmente'),('quarterly', 'Trimestral'),('bi-monthly', 'Bimestral'),('monthly', 'Mensual'),('bi-weekly', 'Quincenal'),('weekly', 'Semanalmente')])
    apply_in = fields.Selection([('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')], string="Aplicar en", default="both")
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_ihss_assign_rel', 'assign_id', 'employee_id', 'Employees', default=lambda self: self._get_employees(), required=True, compute='_compute_employee_ids', store=True, readonly=False)

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
            ihss_id = self.env['hr.hn.ihss'].search([('state','=','active')])

            if not contract_id:
                raise ValidationError(f"El empleado {employee.name} no cuenta con un contrato vigente.")
            
            if self.schedule_pay != contract_id.schedule_pay:
                raise ValidationError(f"El empleado {employee.name} cuenta con un pago programado distinto al que se quiere aplicar.")
            
            if self.schedule_pay == 'semi-monthly':
                contract_id.write({'apply_ihss':True, 'ihss_id':ihss_id.id, 'apply_in_ihss':self.apply_in})

            else:
                contract_id.write({'apply_ihss':True, 'ihss_id':ihss_id.id})

