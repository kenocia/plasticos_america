# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def _enable_internal_picking_types(env):
    """Activa el wizard GS1 en todos los tipos de operación interna existentes."""
    PickingType = env['stock.picking.type'].sudo()
    internal_types = PickingType.search([
        ('code', '=', 'internal'),
        ('kc_enable_internal_lot_scanner', '=', False),
    ])
    if internal_types:
        internal_types.write({'kc_enable_internal_lot_scanner': True})


def _move_internal_lot_scanner_metadata(env):
    """Reasigna metadatos XML del módulo absorbido kc_internal_lot_scanner."""
    Module = env['ir.module.module'].sudo()
    old_module = Module.search([('name', '=', 'kc_internal_lot_scanner')], limit=1)
    if not old_module or old_module.state != 'installed':
        return
    env.cr.execute("""
        UPDATE ir_model_data
           SET module = 'kc_logistics_handheld'
         WHERE module = 'kc_internal_lot_scanner'
    """)
    old_module.write({'state': 'to remove'})
    _logger.info(
        'Metadatos de kc_internal_lot_scanner migrados a kc_logistics_handheld.'
    )


def post_init_hook(env):
    _enable_internal_picking_types(env)
    _move_internal_lot_scanner_metadata(env)
