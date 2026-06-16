# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from odoo.addons.portal.controllers.portal import CustomerPortal as CustomerPortal


class L10nHnHrCustomerPortal(CustomerPortal):
    # Controlador temporalmente desactivado para evitar conflictos con el login
    pass


class LeaveController(http.Controller):
    # Controlador temporalmente desactivado para evitar conflictos con el login
    pass
