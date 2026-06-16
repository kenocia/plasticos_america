# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    kc_physical_scan_location_ids = fields.Many2many(
        'stock.location',
        'kc_company_physical_scan_location_rel',
        'company_id',
        'location_id',
        string='Ubicaciones físico previo (despacho/rampa)',
        domain="[('usage', 'in', ('internal', 'transit', 'customer')), "
               "'|', ('company_id', '=', False), ('company_id', '=', id)]",
        help='Ubicaciones adicionales (rampa, despacho, salida) permitidas al '
             'reportar ubicación en el levantamiento físico previo por lote.',
    )
    kc_physical_scan_adjustment_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo op. ajuste físico previo',
        domain="[('code', 'in', ('incoming', 'internal')), "
               "'|', ('company_id', '=', False), ('company_id', '=', id)]",
        help='Tipo de operación de inventario usado para el albarán único de '
             'entrada generado al aplicar el ajuste de una sesión de levantamiento físico previo.',
    )
    kc_physical_scan_return_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo op. devolución físico previo',
        domain="[('code', 'in', ('outgoing', 'internal')), "
               "'|', ('company_id', '=', False), ('company_id', '=', id)]",
        help='Tipo de operación usado para el albarán único de devolución que '
             'revierte el ajuste de entrada de una sesión de levantamiento físico previo.',
    )
