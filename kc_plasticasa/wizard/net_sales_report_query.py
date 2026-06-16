# -*- coding: utf-8 -*-
"""Consultas sobre account.move / account.move.line para el reporte de ventas netas."""

from datetime import date as date_type

from odoo.osv import expression


class NetSalesReportQuery(object):
    """Encapsula dominios y búsquedas; sin agregación ni exportación."""

    def __init__(self, env, wizard):
        self.env = env
        self.wizard = wizard

    def _expand_category_ids(self):
        categs = self.wizard.categ_ids
        if not categs:
            return []
        return self.env["product.category"].search([("id", "child_of", categs.ids)]).ids

    def _fiscal_invoice_date_domain(self):
        """
        Ventana de fechas del Resumen Fiscal (no es el rango exacto del wizard).

        - Un solo año en el rango: desde el 1 de enero de ese año hasta date_to.
        - Varios años: año inicial completo (ene–dic), años intermedios completos,
          y desde el 1 de enero del año final hasta date_to.
        """
        self.wizard.ensure_one()
        df = self.wizard.date_from
        dt = self.wizard.date_to
        yf, yt = df.year, dt.year
        if yf == yt:
            return [
                ("invoice_date", ">=", date_type(yf, 1, 1)),
                ("invoice_date", "<=", dt),
            ]
        doms = [
            [
                ("invoice_date", ">=", date_type(yf, 1, 1)),
                ("invoice_date", "<=", date_type(yf, 12, 31)),
            ],
        ]
        for y in range(yf + 1, yt):
            doms.append([
                ("invoice_date", ">=", date_type(y, 1, 1)),
                ("invoice_date", "<=", date_type(y, 12, 31)),
            ])
        doms.append([
            ("invoice_date", ">=", date_type(yt, 1, 1)),
            ("invoice_date", "<=", dt),
        ])
        return expression.OR(doms)

    def _move_domain(self, apply_date_range):
        self.wizard.ensure_one()
        w = self.wizard
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("company_id", "=", w.company_id.id),
        ]
        if apply_date_range:
            domain += [
                ("invoice_date", ">=", w.date_from),
                ("invoice_date", "<=", w.date_to),
            ]
        if w.partner_ids:
            domain.append(("partner_id", "in", w.partner_ids.ids))
        if w.invoice_user_id:
            domain.append(("invoice_user_id", "=", w.invoice_user_id.id))
        return domain

    def _move_domain_fiscal(self):
        """Mismo filtro de negocio que el detalle, pero con la ventana fiscal extendida."""
        self.wizard.ensure_one()
        w = self.wizard
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("company_id", "=", w.company_id.id),
        ]
        domain = expression.AND([domain, self._fiscal_invoice_date_domain()])
        if w.partner_ids:
            domain.append(("partner_id", "in", w.partner_ids.ids))
        if w.invoice_user_id:
            domain.append(("invoice_user_id", "=", w.invoice_user_id.id))
        return domain

    def _line_domain(self, move_ids):
        w = self.wizard
        domain = [
            ("move_id", "in", move_ids),
            ("display_type", "=", "product"),
            ("product_id", "!=", False),
        ]
        categ_ids = self._expand_category_ids()
        if categ_ids:
            domain.append(("product_id.categ_id", "in", categ_ids))
        if w.product_ids:
            domain.append(("product_id", "in", w.product_ids.ids))
        return domain

    def fetch_moves(self, apply_date_range):
        """Devuelve account.move recordset según filtros del wizard."""
        domain = self._move_domain(apply_date_range)
        return self.env["account.move"].search(domain, order="invoice_date asc, name asc")

    def fetch_moves_fiscal(self):
        """
        Movimientos para el Resumen Fiscal: ventana de fechas extendida y mismos filtros
        de compañía, clientes y vendedor. Si hay filtro de categoría o producto, solo
        se incluyen facturas/NC que tengan al menos una línea de producto que cumpla.
        """
        domain = self._move_domain_fiscal()
        moves = self.env["account.move"].search(domain, order="invoice_date asc, name asc")
        w = self.wizard
        if not w.product_ids and not self._expand_category_ids():
            return moves
        line_domain = [
            ("move_id", "in", moves.ids),
            ("display_type", "=", "product"),
            ("product_id", "!=", False),
        ]
        categ_ids = self._expand_category_ids()
        if categ_ids:
            line_domain.append(("product_id.categ_id", "in", categ_ids))
        if w.product_ids:
            line_domain.append(("product_id", "in", w.product_ids.ids))
        aml = self.env["account.move.line"].search(line_domain)
        return aml.move_id

    def fetch_product_lines_for_moves(self, moves):
        """Líneas de producto facturables para el conjunto de movimientos dado."""
        if not moves:
            return self.env["account.move.line"]
        return self.env["account.move.line"].search(
            self._line_domain(moves.ids),
            order="move_id, product_id, id",
        )
