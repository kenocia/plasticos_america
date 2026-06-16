# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .net_sales_report_aggregation import aggregate_detail_rows, aggregate_fiscal_monthly_rows
from .net_sales_report_excel import action_export_attachment, build_net_sales_xlsx
from .net_sales_report_invoice_list import build_invoice_sheet_rows
from .net_sales_report_query import NetSalesReportQuery


class KcNetSalesReportWizard(models.TransientModel):
    _name = "kc.net.sales.report.wizard"
    _description = "Reporte de ventas netas (Excel)"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="Fecha desde", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Fecha hasta", required=True, default=fields.Date.context_today)

    partner_ids = fields.Many2many(
        "res.partner",
        "kc_net_sales_report_wizard_partner_rel",
        "wizard_id",
        "partner_id",
        string="Clientes",
    )
    categ_ids = fields.Many2many(
        "product.category",
        "kc_net_sales_report_wizard_categ_rel",
        "wizard_id",
        "categ_id",
        string="Categorías de producto",
    )
    product_ids = fields.Many2many(
        "product.product",
        "kc_net_sales_report_wizard_product_rel",
        "wizard_id",
        "product_id",
        string="Productos",
    )
    invoice_user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        help="Filtra por vendedor asignado a la factura (campo Vendedor del documento).",
    )

    def _validate_dates(self):
        self.ensure_one()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(_("La fecha desde no puede ser posterior a la fecha hasta."))

    def action_export_excel(self):
        self.ensure_one()
        self._validate_dates()

        query = NetSalesReportQuery(self.env, self)

        moves_detail = query.fetch_moves(apply_date_range=True)
        if not moves_detail:
            raise ValidationError(_(
                "No hay facturas ni notas de crédito de cliente publicadas en el periodo y filtros seleccionados."
            ))

        lines = query.fetch_product_lines_for_moves(moves_detail)
        qty_digits = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        detail_rows = aggregate_detail_rows(lines, qty_digits) if lines else []

        moves_fiscal = query.fetch_moves_fiscal()

        company_currency = self.company_id.currency_id
        fiscal_monthly_rows = aggregate_fiscal_monthly_rows(self.env, moves_fiscal)
        invoice_sheet_rows = build_invoice_sheet_rows(self.env, moves_detail)

        content = build_net_sales_xlsx(
            self.env,
            detail_rows,
            invoice_sheet_rows,
            fiscal_monthly_rows,
            company_currency,
        )
        fname = "ventas_netas_%s_%s.xlsx" % (self.date_from, self.date_to)
        return action_export_attachment(self.env, self, fname, content)
