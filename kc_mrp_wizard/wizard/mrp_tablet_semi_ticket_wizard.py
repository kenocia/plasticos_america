# -*- coding: utf-8 -*-

import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpTabletSemiTicketWizard(models.TransientModel):
    _name = 'mrp.tablet.semi.ticket.wizard'
    _description = 'Registrar semiterminado (tablet)'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        readonly=True,
    )
    operation_id = fields.Many2one(
        'mrp.routing.workcenter',
        string='Operación',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Semiterminado (código)',
        readonly=True,
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de medida',
        required=True,
        readonly=True,
    )
    quantity = fields.Float(
        string='Cantidad',
        digits='Product Unit of Measure',
        default=1.0,
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        if self.quantity <= 0:
            raise UserError(_('Indique una cantidad mayor que cero.'))
        if not self.workorder_id.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        return self.workorder_id._tablet_finish_semi_ticket_wizard(self)
