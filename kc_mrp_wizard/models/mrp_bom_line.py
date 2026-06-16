# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    quantity_per_lot = fields.Float(
        string='Cantidad por lote (obsoleto)',
        help='Obsoleto: el asistente MRP ya no lo usa. El consumo por lote es '
             'product_qty × (cantidad del lote / cantidad base de la LdM). Deje en 0.',
    )
    kc_planning_critical_component = fields.Boolean(
        string='Crítico planificación (ventas)',
        help='Solo planificación de ventas / disponibilidad de resina: no afecta crear lote PT, '
             'pre-etiquetas ni producción manual en tablet. Una sola línea crítica por LdM.',
    )
    kc_tablet_manual_consumption_optional = fields.Boolean(
        string='Opcional en prod. manual (tablet)',
        help='Si está marcado, el operador puede omitir este componente al registrar '
             'producción manual con consumo selectivo. Si no, debe consumirse (p. ej. resina).',
    )
    kc_theoretical_resin_grams = fields.Float(
        string='G resina teóricos / UdM lista',
        digits=(16, 3),
        help='Gramos de resina (materia prima) teóricos por unidad de producto, según la cantidad base de la lista.',
    )

    @api.constrains('kc_planning_critical_component', 'bom_id')
    def _check_kc_single_planning_critical_component(self):
        for bom in self.mapped('bom_id'):
            critical = bom.bom_line_ids.filtered('kc_planning_critical_component')
            if len(critical) > 1:
                raise ValidationError(_(
                    'Solo puede haber un componente crítico (planificación) en la lista de materiales «%s».',
                ) % (bom.display_name,))