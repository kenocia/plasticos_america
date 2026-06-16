# -*- coding: utf-8 -*-
"""Agregación de cantidades e importes para ventas netas (detalle y resumen fiscal)."""

from collections import defaultdict
from datetime import date as date_type

from odoo import _
from odoo.tools import float_is_zero, format_date


def _line_sign(move):
    return -1.0 if move.move_type == "out_refund" else 1.0


def format_product_pivot_label(product):
    """Estilo vista pivote Odoo: [código interno] nombre del producto."""
    code = (product.default_code or "").strip()
    name = product.name or ""
    if code:
        return "[%s] %s" % (code, name)
    return product.display_name or name


def aggregate_detail_rows(lines, qty_digits):
    """
    Agrupa por (cliente, categoría, producto).
    Orden tipo pivote (producto primero), etiqueta [ref] nombre.
    """
    buckets = defaultdict(lambda: {"qty": 0.0, "untaxed": 0.0})
    meta = {}

    for line in lines:
        move = line.move_id
        sign = _line_sign(move)
        partner = move.partner_id
        product = line.product_id
        categ = product.categ_id
        key = (partner.id, categ.id, product.id)

        qty = sign * (line.quantity or 0.0)
        untaxed = sign * (line.price_subtotal or 0.0)

        buckets[key]["qty"] += qty
        buckets[key]["untaxed"] += untaxed

        if key not in meta:
            meta[key] = {
                "partner_name": partner.display_name or "",
                "categ_name": categ.complete_name if categ else "",
                "product_name": product.display_name or "",
                "product_label": format_product_pivot_label(product),
            }

    rows = []
    for key, vals in buckets.items():
        qty = vals["qty"]
        untaxed = vals["untaxed"]
        avg = (untaxed / qty) if not float_is_zero(qty, precision_digits=qty_digits) else 0.0
        m = meta[key]
        rows.append({
            "partner_name": m["partner_name"],
            "categ_name": m["categ_name"],
            "product_name": m["product_name"],
            "product_label": m["product_label"],
            "qty": qty,
            "avg_price": avg,
            "untaxed": untaxed,
        })

    # Misma lectura que el pivote: filas ordenadas por producto (referencia/nombre), luego cliente y categoría
    rows.sort(key=lambda r: (
        r["product_label"].lower(),
        r["partner_name"].lower(),
        r["categ_name"].lower(),
    ))
    return rows


def aggregate_fiscal_totals(moves, company_currency):
    """
    Subtotal sin impuestos, ISV y total en moneda de la compañía.
    Se usan los importes firmados estándar de account.move (base imponible e impuestos
    según los apuntes en moneda compañía); facturas y notas de crédito quedan neteadas.
    """
    return {
        "currency": company_currency,
        "subtotal": sum(m.amount_untaxed_signed or 0.0 for m in moves),
        "tax": sum(m.amount_tax_signed or 0.0 for m in moves),
        "total": sum(m.amount_total_signed or 0.0 for m in moves),
    }


def aggregate_fiscal_monthly_rows(env, moves):
    """
    Desglose por mes/año (como agrupación Odoo) + fila final de totales.
    Una fila por cada mes que tenga movimientos; importes en moneda compañía (*_signed).
    """
    by_month = defaultdict(lambda: {"subtotal": 0.0, "tax": 0.0, "total": 0.0})
    for m in moves:
        d = m.invoice_date
        key = None if not d else (d.year, d.month)
        by_month[key]["subtotal"] += m.amount_untaxed_signed or 0.0
        by_month[key]["tax"] += m.amount_tax_signed or 0.0
        by_month[key]["total"] += m.amount_total_signed or 0.0

    keys = sorted([k for k in by_month if k is not None], key=lambda x: (x[0], x[1]))
    if None in by_month:
        keys.append(None)

    rows = []
    for key in keys:
        if key is None:
            title = _("Sin fecha de factura")
        else:
            y, mo = key
            fd = date_type(y, mo, 1)
            title = format_date(env, fd, date_format="MMMM yyyy")
        v = by_month[key]
        rows.append({
            "kind": "month",
            "title": title,
            "subtotal": v["subtotal"],
            "tax": v["tax"],
            "total": v["total"],
        })

    g_sub = sum(m.amount_untaxed_signed or 0.0 for m in moves)
    g_tax = sum(m.amount_tax_signed or 0.0 for m in moves)
    g_tot = sum(m.amount_total_signed or 0.0 for m in moves)
    rows.append({
        "kind": "grand",
        "title": _("Total"),
        "subtotal": g_sub,
        "tax": g_tax,
        "total": g_tot,
    })
    return rows
