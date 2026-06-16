# -*- coding: utf-8 -*-
"""
Reglas de registro (ir.rule) creadas por SQL para evitar _check_domain del core,
que en algunas bases (p. ej. ir.model alterado) falla con columnas inexistentes en ir_model.
"""
import logging

from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'kc_sales_commission'


def post_init_hook(env):
    ensure_commission_ir_rules(env.cr)


def ensure_commission_ir_rules(cr):
    """Idempotente: inserta reglas + xmlids si no existen."""
    _insert_rule_if_missing(
        cr,
        xmlid_name='kc_sales_commission_rule_own_employee',
        title='Comisión: solo empleado propio',
        domain_force="[('employee_id.user_id', '=', user.id)]",
        group_data_name='group_sales_commission_user',
    )
    _insert_rule_if_missing(
        cr,
        xmlid_name='kc_sales_commission_rule_manager_all',
        title='Comisión: responsable ve todas',
        domain_force="[(1, '=', 1)]",
        group_data_name='group_sales_commission_manager',
    )


def _rule_xmlid_res_id(cr, xmlid_name):
    cr.execute(
        """
        SELECT d.res_id FROM ir_model_data d
        WHERE d.module = %s AND d.name = %s AND d.model = 'ir.rule'
        """,
        (MODULE, xmlid_name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _group_res_id(cr, group_data_name):
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = %s AND name = %s AND model = 'res.groups'
        """,
        (MODULE, group_data_name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _insert_rule_if_missing(cr, xmlid_name, title, domain_force, group_data_name):
    existing = _rule_xmlid_res_id(cr, xmlid_name)
    if existing:
        cr.execute('SELECT 1 FROM ir_rule WHERE id = %s', (existing,))
        if cr.fetchone():
            return
        cr.execute(
            """
            DELETE FROM ir_model_data
            WHERE module = %s AND name = %s AND model = 'ir.rule'
            """,
            (MODULE, xmlid_name),
        )

    cr.execute('SELECT id FROM ir_model WHERE model = %s', ('kc.sales.commission',))
    row = cr.fetchone()
    if not row:
        _logger.warning(
            'kc_sales_commission: no hay ir.model para kc.sales.commission; omitiendo regla %s',
            xmlid_name,
        )
        return
    model_id = row[0]

    group_id = _group_res_id(cr, group_data_name)
    if not group_id:
        _logger.warning(
            'kc_sales_commission: no se encontró res.groups para %s; omitiendo regla %s',
            group_data_name,
            xmlid_name,
        )
        return

    cr.execute(
        """
        INSERT INTO ir_rule (
            name, model_id, domain_force, active,
            perm_read, perm_write, perm_create, perm_unlink,
            create_uid, create_date, write_uid, write_date, "global"
        )
        VALUES (
            %s, %s, %s, true,
            true, true, true, true,
            %s, (now() AT TIME ZONE 'UTC'), %s, (now() AT TIME ZONE 'UTC'), false
        )
        RETURNING id
        """,
        (title, model_id, domain_force, SUPERUSER_ID, SUPERUSER_ID),
    )
    rule_id = cr.fetchone()[0]

    cr.execute(
        """
        INSERT INTO rule_group_rel (rule_group_id, group_id)
        VALUES (%s, %s)
        """,
        (rule_id, group_id),
    )

    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        VALUES (%s, %s, 'ir.rule', %s, true)
        """,
        (MODULE, xmlid_name, rule_id),
    )
