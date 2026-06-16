# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import threading

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

import logging
_logger = logging.getLogger(__name__)


class ContractType(models.Model):
    _inherit = 'hr.contract.type'

    def unlink(self):
        type_id = [self.env.ref('hr.contract_type_permanent'),
                   self.env.ref('hr.contract_type_temporary')]
        for contract_type in self:
            if contract_type in type_id:
                raise UserError(
                    'No puede borrar ese tipo del contrato')
        return super(ContractType, self).unlink()


