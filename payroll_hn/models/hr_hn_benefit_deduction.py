from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class HrHnBenefitDeduction(models.Model):
    _name = 'hr.hn.benefit.deduction'
    _description = 'Beneficios y deducciones HN'
    _rec_name = "rule_id"

    category = fields.Selection(string="Categoría", selection=[('DED','Deducción'),('ALW','Beneficio')], required=True)
    rule_id = fields.Many2one(string="Regla", comodel_name="hr.salary.rule", required=True)
    state = fields.Selection(string="Estado", selection=[('draft','Borrador'),('pause','Pausa'),('progress','Progreso'),('done','Finalizado')], default='draft')
    periodicity = fields.Selection(string="Periodicidad", selection=[('finite','Finito'),('infinite','Infinito')], required=True)
    fee_amount = fields.Float(string="Monto cuota")
    fee_amount_apply = fields.Float(string="Monto cuota aplicar", compute="_compute_fee_amount_apply", store=True)
    schedule_pay = fields.Selection(string="Pago programado", related="contract_id.schedule_pay")
    apply_in = fields.Selection([('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')], string="Aplicar en", default="both")
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency', default=lambda self:self.env.user.company_id.currency_id.id, required=True)
    contract_id = fields.Many2one(string="Contrato", comodel_name="hr.contract")
    description = fields.Char(string="Descripción")
    
    # Campos de la periodicidad finita
    start_date = fields.Date(string="Fecha de inicio")
    fee_numbers = fields.Integer(string="Número de cuotas", help="Cantidad de cuotas totales que se deducirán. (cuotas segun la periodicidad de pago)")
    fee_numbers_remaining = fields.Integer(string="Número de cuotas restantes", compute="_compute_fee_numbers_remaining")
    fee_numbers_apply = fields.Integer(string="Número de cuotas aplicadas", default=0, store=True)
    total_fee_residual = fields.Float(string="Total cuotas residual", compute="_compute_total_fee_residual")

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_pause(self):
        self.write({'state': 'pause'})
    
    def action_progress(self):
        self.write({'state': 'progress'})

    def action_done(self):
        self.write({'state': 'done'})
    
    @api.depends('fee_numbers','fee_numbers_apply')
    def _compute_fee_numbers_remaining(self):
        for record in self:
            record.fee_numbers_remaining = record.fee_numbers - record.fee_numbers_apply

    @api.depends('fee_amount_apply','fee_numbers','fee_numbers_apply')
    def _compute_total_fee_residual(self):
        for record in self:
            record.total_fee_residual = (record.fee_numbers * record.fee_amount_apply) - (record.fee_numbers_apply * record.fee_amount_apply)

    @api.depends('schedule_pay','fee_amount','apply_in')
    def _compute_fee_amount_apply(self):
        frequency_multiplier = {
            'annually': 12,
            'semi-annually': 6,
            'quarterly': 4,
            'bi-monthly': 2,
            'bi-weekly': 0.5,
            'weekly': 1 / 4.33,  # Aproximadamente 4.33 semanas en un mes
        }
        
        for rec in self:
            fee_amount_apply = rec.fee_amount * frequency_multiplier.get(rec.schedule_pay, 1)
            if rec.apply_in == 'both':
                rec.fee_amount_apply = fee_amount_apply
            else:
                rec.fee_amount_apply = fee_amount_apply * 2
    
    def get_fee_amount(self):
        return self.fee_amount_apply