# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.constrains('operation_ids', 'type')
    def _kc_check_single_tablet_pt_lot_workcenter(self):
        for bom in self:
            if bom.type not in ('normal', 'phantom'):
                continue
            wcs = bom.operation_ids.workcenter_id
            flagged = wcs.filtered('kc_tablet_creates_pt_lot')
            if len(flagged) > 1:
                raise ValidationError(_(
                    'Solo un centro de trabajo en la pestaña "Operaciones" de esta lista de materiales '
                    'puede tener "Genera lote de PT (tablet)" activo. Revise: %s'
                ) % (', '.join(flagged.mapped('name'))))
