# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_model_data
           SET module = 'kc_logistics_handheld'
         WHERE module = 'kc_internal_lot_scanner'
    """)
    cr.execute("""
        UPDATE ir_module_module
           SET state = 'to remove'
         WHERE name = 'kc_internal_lot_scanner'
           AND state = 'installed'
    """)
    _logger.info(
        'kc_internal_lot_scanner: metadatos reasignados a kc_logistics_handheld.'
    )
