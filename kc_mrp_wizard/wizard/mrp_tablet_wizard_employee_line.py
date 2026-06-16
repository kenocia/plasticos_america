# -*- coding: utf-8 -*-

from odoo import fields, models, _


class MrpTabletWizardEmployeeLine(models.TransientModel):
    _name = 'mrp.tablet.wizard.employee.line'
    _description = 'Línea de empleado para selección en wizard tablet'

    employee_wizard_id = fields.Many2one(
        'mrp.tablet.employee.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
    )
    employee_name = fields.Char(
        string='Nombre',
        related='employee_id.name',
        readonly=True,
    )

    def action_select_employee(self):
        """Selecciona el empleado y abre el paso de PIN."""
        self.ensure_one()
        wizard = self.employee_wizard_id
        wizard.write({
            'employee_id': self.employee_id.id,
            'pin_input': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asistente MRP — PIN'),
            'res_model': 'mrp.tablet.employee.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('kc_mrp_wizard.mrp_tablet_employee_pin_wizard_form').id,
            'res_id': wizard.id,
            'target': 'new',
        }
