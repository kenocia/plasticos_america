# -*- coding: utf-8 -*-
from odoo import api, models


class ReportSalesInvoices(models.AbstractModel):
    _name = "report.kc_plasticasa.report_sales_invoices"
    _description = "Reporte Facturas de Venta (KC)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["kc.sales.invoices.report.wizard"].browse(docids).ensure_one()
        invoices = wizard._get_invoices()
        return {
            "doc_ids": invoices.ids,
            "doc_model": "account.move",
            "docs": invoices,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "company": wizard.company_id,
        }
