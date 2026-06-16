# -*- coding: utf-8 -*-
"""Estructura de filas para la hoja «Facturas» (vista lista agrupada por mes)."""

from collections import OrderedDict
from datetime import date as date_type

from odoo import _
from odoo.tools import format_date


def format_move_type_label(move):
    if move.move_type == "out_refund":
        return _("Nota de crédito")
    return _("Factura")


def state_label(move, env):
    pairs = move._fields["state"]._description_selection(env)
    labels = dict(pairs)
    return labels.get(move.state, move.state or "")


def build_invoice_sheet_rows(env, moves):
    """
    Construye filas para Excel: sección por mes (título), líneas de documento,
    subtotal del mes, fila de total general.
    Importes en moneda de la compañía (campos *signed de account.move).
    """
    moves = moves.sorted(key=lambda m: (m.invoice_date or m.date, m.id))

    by_month = OrderedDict()
    for m in moves:
        d = m.invoice_date
        if not d:
            key = None
        else:
            key = (d.year, d.month)
        by_month.setdefault(key, []).append(m)

    rows = []
    for key in by_month:
        ms = by_month[key]
        if key is None:
            title = _("Sin fecha de factura")
        else:
            y, mo = key
            fd = date_type(y, mo, 1)
            title = format_date(env, fd, date_format="MMMM yyyy")
        rows.append({"kind": "section", "title": title})

        sub_u = 0.0
        sub_t = 0.0
        for m in ms:
            u = m.amount_untaxed_signed or 0.0
            t = m.amount_total_signed or 0.0
            sub_u += u
            sub_t += t
            rows.append({"kind": "line", "move": m, "untaxed": u, "total": t})
        rows.append({"kind": "subtotal", "untaxed": sub_u, "total": sub_t})

    grand_u = sum(m.amount_untaxed_signed or 0.0 for m in moves)
    grand_t = sum(m.amount_total_signed or 0.0 for m in moves)
    rows.append({"kind": "grand", "untaxed": grand_u, "total": grand_t})
    return rows
