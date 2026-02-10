# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class KcSalesInvoicesReportWizard(models.TransientModel):
    _name = "kc.sales.invoices.report.wizard"
    _description = "Reporte de Facturas de Venta (KC)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)

    def _get_invoices(self):
        self.ensure_one()
        domain = [
            ("move_type", "=", "out_invoice"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
        ]
        return self.env["account.move"].search(domain, order="invoice_date asc, name asc")

    def action_print_pdf(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("La fecha desde no puede ser mayor a la fecha hasta."))
        invoices = self._get_invoices()
        if not invoices:
            raise ValidationError(_("No se encontraron facturas en el rango de fechas especificado."))
        return self.env.ref("kc_plasticasa.action_report_sales_invoices").report_action(self)
