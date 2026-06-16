# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env['kc.physical.lot.scan.line']
    Session = env['kc.physical.lot.scan.session']

    for session in Session.search([]):
        lines = Line.search([('session_id', '=', session.id)], order='scan_date, id')
        uid_order = []
        for line in lines:
            uid = line.scan_session_uid or '__legacy__'
            if uid not in uid_order:
                uid_order.append(uid)

        if not uid_order:
            continue

        ramp_map = {uid: idx + 1 for idx, uid in enumerate(uid_order)}
        for uid, ramp_index in ramp_map.items():
            if uid == '__legacy__':
                domain = [
                    ('session_id', '=', session.id),
                    '|',
                    ('scan_session_uid', '=', False),
                    ('scan_session_uid', '=', ''),
                ]
            else:
                domain = [
                    ('session_id', '=', session.id),
                    ('scan_session_uid', '=', uid),
                ]
            ramp_lines = Line.search(domain, order='scan_date, id')
            base = Line._ramp_line_base(ramp_index)
            for idx, line in enumerate(ramp_lines):
                line.write({
                    'ramp_index': ramp_index,
                    'session_line_no': base + idx,
                })

        max_ramp = max(ramp_map.values())
        last_uid = uid_order[-1]
        active_uid = last_uid if last_uid != '__legacy__' else False
        session.write({
            'active_ramp_index': max_ramp,
            'active_scan_session_uid': active_uid,
        })

    _logger.info('kc_plasticasa: renumbered physical lot scan lines by ramp')
