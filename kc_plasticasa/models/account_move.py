# -*- coding: utf-8 -*-
from odoo import models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_open_kc_payment_batch_wizard(self):
        moves = self
        if not moves:
            return False
        move = moves[0]
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear Lote de Pagos"),
            "res_model": "kc.payment.batch.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": moves.ids,
                "default_load_mode": "invoices",
                "default_partner_type": "supplier" if move.move_type in ("in_invoice", "in_refund") else "customer",
                "default_payment_type": "outbound" if move.move_type in ("in_invoice", "in_refund") else "inbound",
                "default_company_id": move.company_id.id,
            },
        }
