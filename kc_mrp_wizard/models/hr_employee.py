# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    kc_tablet_allow_start = fields.Boolean(
        string='Iniciar orden',
        default=False,
    )
    kc_tablet_allow_prelabels = fields.Boolean(
        string='Pre-etiquetas',
        default=False,
    )
    kc_tablet_allow_scan_prelabel = fields.Boolean(
        string='Producir pre-etiqueta',
        default=False,
    )
    kc_tablet_allow_create_lot = fields.Boolean(
        string='Crear lote PT',
        default=False,
    )
    kc_tablet_allow_register_semi = fields.Boolean(
        string='Registrar semi',
        default=False,
    )
    kc_tablet_allow_quality_alert = fields.Boolean(
        string='Alerta de calidad',
        default=False,
    )
    kc_tablet_allow_create_bad_lot = fields.Boolean(
        string='Producción (cantidad)',
        default=False,
    )
    kc_tablet_allow_selective_manual = fields.Boolean(
        string='Producción (componentes)',
        default=False,
        help='Producción manual con lote PT existente y consumo selectivo de componentes de la LdM.',
    )
    kc_tablet_allow_pause = fields.Boolean(
        string='Pausar/parar',
        default=False,
    )
    kc_tablet_allow_finish = fields.Boolean(
        string='Finalizar',
        default=False,
    )
    kc_tablet_allow_material_scrap = fields.Boolean(
        string='Merma de material',
        default=False,
    )
    kc_tablet_allow_reprint_label = fields.Boolean(
        string='Re-imprimir etiqueta',
        default=False,
    )

    kc_tablet_type_operator = fields.Selection(
        [('operator', 'Operador'), ('supervisor', 'Supervisor')],
        string='Tipo de operador',
        default='operator',
    )
