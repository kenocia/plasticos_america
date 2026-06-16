from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HolidaysRequest(models.Model):
    _name = "hr.leave"
    _inherit = 'hr.leave'

    only_to_pay = fields.Boolean('Solo a pagar', default=False)

    @api.constrains('holiday_status_id')
    def _check_holiday_status_id(self):
        for leave in self:
            holiday_vacation_anticipate_id = self.env.ref('l10n_hn_hr_holidays.holiday_status_vacation_anticipate').id
            holiday_vacation_id = self.env.ref('l10n_hn_hr_holidays.holiday_status_vacation').id
            if leave.holiday_status_id.id == holiday_vacation_anticipate_id:
                employee = leave.employee_id
                if employee:
                    if not employee.permit_vacation_without_acumulated:
                        raise ValidationError("Usted no tiene permiso a pedir vacaciones anticipadas")
                    if employee.remaining_leave_year > 0:
                        cnt = employee.remaining_leave_year
                        raise ValidationError(_("Usted todavia puede pedir %s días de vacaciones acumuladas.", cnt))
                    if leave.number_of_days > employee.total_vacation_day:
                        raise ValidationError(_("El empleado %s No puede pedir  %s de vacaciones anticipada, solo tiene %r.", employee.name, leave.number_of_days, int(employee.total_vacation_day)))

    def action_validate(self, check_state=True):
        result = super(HolidaysRequest, self).action_validate(check_state=check_state)
        for leave in self:
            if leave.employee_id:
                leave.employee_id._compute_accumulated_leave()
                leave.employee_id._compute_accumulated_leave_day_take()
                leave.employee_id._compute_total_vacation_day()
        return result

    def action_refuse(self):
        result = super(HolidaysRequest, self).action_refuse()
        for leave in self:
            if leave.employee_id:
                leave.employee_id._compute_accumulated_leave()
                leave.employee_id._compute_accumulated_leave_day_take()
                leave.employee_id._compute_total_vacation_day()
        return result
