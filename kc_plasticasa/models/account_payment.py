# -*- coding: utf-8 -*-
from odoo import models, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_voucher_title(self):
        self.ensure_one()
        method_line = self.payment_method_line_id
        method_code = (method_line.payment_method_id.code or "").lower()
        method_name = (method_line.name or "").lower()
        if "check" in method_code or "cheque" in method_name or "check" in method_name:
            check_number = getattr(self, "check_number", False)
            if check_number:
                return _("VOUCHER DE CHEQUE %s") % check_number
            return _("VOUCHER DE CHEQUE")
        return _("VOUCHER DE TRANSFERENCIA")
