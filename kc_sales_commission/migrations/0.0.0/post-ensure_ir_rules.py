# -*- coding: utf-8 -*-
from odoo.addons.kc_sales_commission.hooks import ensure_commission_ir_rules


def migrate(cr, version):
    ensure_commission_ir_rules(cr)
