# -*- coding: utf-8 -*-
import base64
import io
from odoo import _, fields, models
from odoo.exceptions import ValidationError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class ProductMovementReportWizard(models.TransientModel):
    _name = "product.movement.report.wizard"
    _description = "Wizard Reporte Productos Vendidos (Excel)"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="Fecha inicio", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Fecha fin", required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        domain=[("is_company", "=", True)],
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Categoría de producto",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
    )

    def _get_domain(self):
        self.ensure_one()
        domain = [
            ("move_id.move_type", "in", ("out_invoice", "out_refund")),
            ("move_id.state", "=", "posted"),
            ("move_id.invoice_date", ">=", self.date_from),
            ("move_id.invoice_date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
            ("product_id", "!=", False),
            ("display_type", "not in", ("line_section", "line_note")),
        ]
        if self.partner_id:
            domain.append(("move_id.partner_id", "=", self.partner_id.id))
        if self.categ_id:
            domain.append(("product_id.categ_id", "=", self.categ_id.id))
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        return domain

    def _get_move_lines(self):
        """Obtiene líneas de factura/NC con producto. Busca por move_id para evitar problemas con dominios sobre move_id.invoice_date."""
        self.ensure_one()
        move_domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
        ]
        if self.partner_id:
            move_domain.append(("partner_id", "=", self.partner_id.id))
        moves = self.env["account.move"].search(move_domain)
        if not moves:
            return self.env["account.move.line"]
        line_domain = [
            ("move_id", "in", moves.ids),
            ("product_id", "!=", False),
            ("display_type", "not in", ("line_section", "line_note")),
        ]
        if self.categ_id:
            line_domain.append(("product_id.categ_id", "=", self.categ_id.id))
        if self.product_id:
            line_domain.append(("product_id", "=", self.product_id.id))
        lines = self.env["account.move.line"].search(
            line_domain,
            order="date asc, id asc",
        )
        # Excluir categoría "All" (insensible a mayúsculas); el dominio solo no basta si está guardada como "All"
        return lines.filtered(
            lambda l: not (l.product_id.categ_id and (l.product_id.categ_id.name or "").upper() == "ALL")
        )

    def _quantity_signed(self, line):
        """Cantidad con signo: positiva para facturas, negativa para notas de crédito."""
        if line.move_id.move_type == "out_refund":
            return -(line.quantity or 0)
        return line.quantity or 0

    def _build_detail_rows(self, lines):
        """Genera lista de diccionarios para la hoja Detalle. Conservada para uso futuro (hoja Detalle desactivada por ahora)."""
        rows = []
        for line in lines:
            rows.append({
                "product": line.product_id.display_name or "",
                "categ": line.product_id.categ_id.name if line.product_id.categ_id else "",
                "quantity": self._quantity_signed(line),
                "partner": line.move_id.partner_id.name if line.move_id.partner_id else "",
                "date": line.move_id.invoice_date,
                "document": line.move_id.name or "",
            })
        return rows

    def _build_summary_by_product(self, lines):
        """Agrupa por producto y suma cantidades con signo. Retorna lista de dict y el de mayor movimiento."""
        totals = {}
        for line in lines:
            qty = self._quantity_signed(line)
            key = (line.product_id.id, line.product_id.display_name, line.product_id.categ_id.name if line.product_id.categ_id else "")
            totals[key] = totals.get(key, 0) + qty
        rows = [
            {"product": name, "categ": categ, "quantity": qty}
            for (_, name, categ), qty in sorted(totals.items(), key=lambda x: -x[1])
        ]
        top = rows[0] if rows else {"product": "-", "categ": "-", "quantity": 0}
        return rows, top

    def action_export_excel(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("La fecha inicio no puede ser mayor que la fecha fin."))
        if not xlsxwriter:
            raise ValidationError(_("La librería xlsxwriter no está instalada. Instale con: pip install xlsxwriter"))

        lines = self._get_move_lines()
        # detail_rows = self._build_detail_rows(lines)  # función conservada; hoja Detalle desactivada por ahora
        summary_rows, top_moved = self._build_summary_by_product(lines)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        title_fmt = workbook.add_format({
            "bold": True, "font_size": 16, "align": "center", "valign": "vcenter",
        })
        subtitle_fmt = workbook.add_format({"font_size": 10, "align": "left"})
        header_fmt = workbook.add_format({
            "bold": True, "align": "center", "valign": "vcenter", "text_wrap": True,
        })
        number_fmt = workbook.add_format({"num_format": "#,##0.00"})
        date_fmt = workbook.add_format({"num_format": "dd/mm/yyyy"})
        cell_fmt = workbook.add_format({"valign": "vcenter"})
        highlight_fmt = workbook.add_format({
            "bold": True, "bg_color": "#D7E4BD", "valign": "vcenter",
        })
        highlight_least_fmt = workbook.add_format({
            "bold": True, "bg_color": "#F8CECC", "valign": "vcenter",
        })

        # ----- Hoja Detalle (desactivada por ahora; solo se genera Resumen) -----
        # sheet_detail = workbook.add_worksheet("Detalle")
        # sheet_detail.set_column("A:A", 35)
        # sheet_detail.set_column("B:B", 25)
        # sheet_detail.set_column("C:C", 14)
        # sheet_detail.set_column("D:D", 35)
        # sheet_detail.set_column("E:E", 14)
        # sheet_detail.set_column("F:F", 20)
        # row = 0
        # sheet_detail.merge_range(row, 0, row, 5, "Reporte de productos vendidos", title_fmt)
        # row += 1
        # sheet_detail.write(row, 0, "Filtros aplicados:", subtitle_fmt)
        # row += 1
        # sheet_detail.write(row, 0, "Compañía: %s" % self.company_id.name, subtitle_fmt)
        # row += 1
        # sheet_detail.write(row, 0, "Fecha: %s a %s" % (self.date_from, self.date_to), subtitle_fmt)
        # row += 1
        # if self.partner_id:
        #     sheet_detail.write(row, 0, "Cliente: %s" % self.partner_id.name, subtitle_fmt)
        #     row += 1
        # if self.categ_id:
        #     sheet_detail.write(row, 0, "Categoría: %s" % self.categ_id.name, subtitle_fmt)
        #     row += 1
        # if self.product_id:
        #     sheet_detail.write(row, 0, "Producto: %s" % self.product_id.display_name, subtitle_fmt)
        #     row += 1
        # row += 1
        # headers = ["Producto", "Categoría del producto", "Cantidad movida", "Cliente", "Fecha de factura", "Documento / factura"]
        # for col, h in enumerate(headers):
        #     sheet_detail.write(row, col, h, header_fmt)
        # row += 1
        # if not detail_rows:
        #     sheet_detail.merge_range(
        #         row, 0, row, 5,
        #         _("No se encontraron líneas con los filtros aplicados. Compruebe: fechas, compañía y que existan facturas de cliente publicadas con productos."),
        #         subtitle_fmt,
        #     )
        #     row += 1
        # else:
        #     for r in detail_rows:
        #         sheet_detail.write(row, 0, r["product"], cell_fmt)
        #         sheet_detail.write(row, 1, r["categ"], cell_fmt)
        #         sheet_detail.write(row, 2, r["quantity"], number_fmt)
        #         sheet_detail.write(row, 3, r["partner"], cell_fmt)
        #         sheet_detail.write(row, 4, r["date"], date_fmt)
        #         sheet_detail.write(row, 5, r["document"], cell_fmt)
        #         row += 1

        # ----- Hoja Resumen -----
        sheet_resume = workbook.add_worksheet("Resumen")
        sheet_resume.set_column("A:A", 35)
        sheet_resume.set_column("B:B", 25)
        sheet_resume.set_column("C:C", 14)

        row = 0
        sheet_resume.merge_range(row, 0, row, 2, "Resumen por producto", title_fmt)
        row += 2
        for col, h in enumerate(["Producto", "Categoría", "Cantidad total movida"]):
            sheet_resume.write(row, col, h, header_fmt)
        row += 1
        for r in summary_rows:
            sheet_resume.write(row, 0, r["product"], cell_fmt)
            sheet_resume.write(row, 1, r["categ"], cell_fmt)
            sheet_resume.write(row, 2, r["quantity"], number_fmt)
            row += 1

        row += 1
        sheet_resume.merge_range(row, 0, row, 2, "5 productos más vendidos", header_fmt)
        row += 1
        sheet_resume.write(row, 0, "Producto", header_fmt)
        sheet_resume.write(row, 1, "Categoría", header_fmt)
        sheet_resume.write(row, 2, "Cantidad total movida", header_fmt)
        row += 1
        top_5 = summary_rows[:5]
        for r in top_5:
            sheet_resume.write(row, 0, r["product"], highlight_fmt)
            sheet_resume.write(row, 1, r["categ"], highlight_fmt)
            sheet_resume.write(row, 2, r["quantity"], number_fmt)
            row += 1

        row += 1
        sheet_resume.merge_range(row, 0, row, 2, "5 productos menos vendidos", header_fmt)
        row += 1
        sheet_resume.write(row, 0, "Producto", header_fmt)
        sheet_resume.write(row, 1, "Categoría", header_fmt)
        sheet_resume.write(row, 2, "Cantidad total movida", header_fmt)
        row += 1
        bottom_5 = summary_rows[-5:]
        for r in bottom_5:
            sheet_resume.write(row, 0, r["product"], highlight_least_fmt)
            sheet_resume.write(row, 1, r["categ"], highlight_least_fmt)
            sheet_resume.write(row, 2, r["quantity"], number_fmt)
            row += 1

        workbook.close()
        output.seek(0)
        content = output.getvalue()

        filename = "productos_vendidos_%s_%s.xlsx" % (self.date_from, self.date_to)
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "datas": base64.b64encode(content).decode("ascii"),
            "res_model": self._name,
            "res_id": self.id,
            "type": "binary",
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
