# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrHnPayrollReport(models.TransientModel):
    _name = 'hr.hn.payroll.report'
    _description = 'Reporte de Nómina Honduras'

    lot_id = fields.Many2one(
        string="Lote",
        comodel_name="hr.payslip.run",
        required=True,
        help="Selecciona el lote de nómina para generar el reporte"
    )

    def action_generate_payroll_report(self):
        """Acción para generar el reporte de nómina"""
        if not self.lot_id:
            raise UserError(_("Debes seleccionar un lote de nómina."))

        return {
            'type': 'ir.actions.client',
            'tag': 'payroll_report',
            'params': {
                'lot_name': self.lot_id.name,
            }
        }

    def action_generate_deductions_report(self):
        """Acción para generar el reporte de deducciones"""
        if not self.lot_id:
            raise UserError(_("Debes seleccionar un lote de nómina."))

        return {
            'type': 'ir.actions.client',
            'tag': 'deductions_report',
            'params': {
                'lot_name': self.lot_id.name,
            }
        }