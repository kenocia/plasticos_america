# -*- coding: utf-8 -*-

import datetime

from odoo import models, fields


class AgedPartnerBalanceCustomHandler(models.AbstractModel):
    """
    Extiende el engine del reporte de antigüedad (CxC/CxP) para exponer una subfórmula
    adicional: `aging_days`.

    Nota:
    - El handler de CxC (`account.aged.receivable.report.handler`) y el de CxP
      (`account.aged.payable.report.handler`) heredan del handler común
      `account.aged.partner.balance.report.handler`, por lo que este override aplica a ambos.
    """

    _inherit = 'account.aged.partner.balance.report.handler'

    def _aged_partner_report_custom_engine_common(self, options, internal_type, current_groupby, next_groupby, offset=0, limit=None):
        res = super()._aged_partner_report_custom_engine_common(
            options, internal_type, current_groupby, next_groupby, offset=offset, limit=limit,
        )

        # En account.report, `date_to` siempre viaja como string 'YYYY-MM-DD' en options,
        # pero en algunos flujos puede llegar ya como date/datetime; usamos una conversión tolerante.
        date_to = fields.Date.to_date(options.get('date', {}).get('date_to')) if options else None

        def _to_date(value):
            if not value:
                return None
            if isinstance(value, datetime.datetime):
                return value.date()
            if isinstance(value, datetime.date):
                return value
            if isinstance(value, str):
                s = value.strip()
                # Caso típico: 'YYYY-MM-DD' o 'YYYY-MM-DD ...'
                if len(s) >= 10 and s[4:5] == '-' and s[7:8] == '-':
                    try:
                        return fields.Date.from_string(s[:10])
                    except Exception:
                        pass
                # Intento 2: date estricta
                try:
                    return fields.Date.from_string(s)
                except Exception:
                    pass
                # Intento 3: datetime -> date
                try:
                    return fields.Datetime.from_string(s).date()
                except Exception:
                    return None
            return None

        def _inject_aging_days(values):
            # Para niveles agregados (partner/total) `due_date` viene como None en el engine estándar.
            # Solo calculamos cuando hay una fecha concreta.
            due_date = _to_date(values.get('due_date'))
            if date_to and due_date:
                # “Antigüedad” en días: 0 si aún no vence, positivo si ya venció.
                values['aging_days'] = max(0, (date_to - due_date).days)
            else:
                values['aging_days'] = None

        if isinstance(res, dict):
            _inject_aging_days(res)
            return res

        # Forma estándar cuando hay groupby: lista de tuplas (grouping_key, dict_values)
        if isinstance(res, list):
            for _group_key, values in res:
                if isinstance(values, dict):
                    _inject_aging_days(values)
            return res

        return res

