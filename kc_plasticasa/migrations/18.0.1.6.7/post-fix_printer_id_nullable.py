# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Quita NOT NULL heredado de cuando printer_id era required en el modelo.

    Odoo exige la firma ``migrate(cr, version)`` (el segundo argumento es la
    versión instalada previa al upgrade).
    """
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'kc_lot_label_print_wizard'
              AND column_name = 'printer_id'
              AND is_nullable = 'NO'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    _logger.info(
        'kc_plasticasa: ALTER TABLE kc_lot_label_print_wizard '
        'ALTER COLUMN printer_id DROP NOT NULL'
    )
    cr.execute(
        'ALTER TABLE kc_lot_label_print_wizard '
        'ALTER COLUMN printer_id DROP NOT NULL'
    )
