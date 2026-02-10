import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Entry Sequence",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="This sequence will be used to generate the journal entry number.",
    )
    refund_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Credit Note Entry Sequence",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="This sequence will be used to generate the journal entry number for refunds.",
    )
    # Redefine the default to True as <=v13.0
    # refund_sequence = fields.Boolean(default=True)

    document_fiscal = fields.Selection(string='Documento Fiscal', selection=[('client', 'Factura Cliente'),
                                                                             ('vendors', 'Factura Proveedor'),
                                                                             ('boleta', 'Boleta de Compra'),
                                                                             ('retention', 'Comprobante de Retencion'),
                                                                             ('credit', 'Nota de Credito'),
                                                                             ('debit', 'Nota de Debito')],
                                       required=False, )

    @api.constrains("refund_sequence_id", "sequence_id", "document_fiscal")
    def _check_journal_sequence(self):
        for journal in self:
            # Solo validar secuencias si el diario tiene documento fiscal configurado
            if not journal.document_fiscal:
                continue
                
            # Verificar que no se use la misma secuencia para entrada y reembolso
            if (
                    journal.refund_sequence_id
                    and journal.sequence_id
                    and journal.refund_sequence_id == journal.sequence_id
            ):
                raise ValidationError(
                    _(
                        "On journal '%s', the same sequence is used as "
                        "Entry Sequence and Credit Note Entry Sequence.",
                        journal.display_name,
                    )
                )
            
            # Verificar que las secuencias tengan empresa configurada
            if journal.sequence_id and not journal.sequence_id.company_id:
                msg = _(
                    "The company is not set on sequence '%(sequence)s' configured on "
                    "journal '%(journal)s'.",
                    sequence=journal.sequence_id.display_name,
                    journal=journal.display_name,
                )
                raise ValidationError(msg)
            if journal.refund_sequence_id and not journal.refund_sequence_id.company_id:
                msg = _(
                    "The company is not set on sequence '%(sequence)s' configured as "
                    "credit note sequence of journal '%(journal)s'.",
                    sequence=journal.refund_sequence_id.display_name,
                    journal=journal.display_name,
                )
                raise ValidationError(msg)

    @api.model_create_multi
    def create(self, vals_list):
        # Solo crear secuencias si el diario tiene documento fiscal configurado
        for vals in vals_list:
            if vals.get("document_fiscal") and not vals.get("sequence_id"):
                vals["sequence_id"] = self._create_sequence(vals).id
                
            if (
                    vals.get("document_fiscal") and
                    vals.get("type") in ("sale", "purchase")
                    and vals.get("refund_sequence")
                    and not vals.get("refund_sequence_id")
            ):
                vals["refund_sequence_id"] = self._create_sequence(vals, refund=True).id
        return super().create(vals_list)

    @api.model
    def _prepare_sequence(self, vals, refund=False):
        code = vals.get("code") and vals["code"].upper() or ""
        prefix = "%s%s/%%(range_year)s/" % (refund and "R" or "", code)
        seq_vals = {
            "name": "%s%s"
                    % (
                        vals.get("name", _("Sequence")),
                        refund and _("Refund") + " " or ""),
            "company_id": vals.get("company_id") or self.env.company.id,
            "implementation": "no_gap",
            "prefix": prefix,
            "padding": 4,
            "use_date_range": True,
        }
        return seq_vals

    @api.model
    def _create_sequence(self, vals, refund=False):
        seq_vals = self._prepare_sequence(vals, refund=refund)
        return self.env["ir.sequence"].sudo().create(seq_vals)

    def _prepare_sequence_current_moves(self, refund=False):
        """Get sequence dict values the journal based on current moves"""
        self.ensure_one()
        move_domain = [
            ("journal_id", "=", self.id),
            ("name", "!=", "/"),
        ]
        if self.refund_sequence:
            #  Based on original Odoo behavior
            if refund:
                move_domain.append(("move_type", "in", ("out_refund", "in_refund")))
            else:
                move_domain.append(("move_type", "not in", ("out_refund", "in_refund")))
        last_move = self.env["account.move"].search(
            move_domain, limit=1, order="id DESC"
        )
        msg_err = (
                "Journal %s could not get sequence %s values based on current moves. "
                "Using default values." % (self.id, refund and "refund" or "")
        )
        if not last_move:
            _logger.warning("%s %s", msg_err, "No moves found")
            return {}
        try:
            with self.env.cr.savepoint():
                # get the current sequence values could be buggy to get
                # But even we can use the default values
                # or do manual changes instead of raising errors
                last_sequence = last_move._get_last_sequence()
                if not last_sequence:
                    last_sequence = (
                            last_move._get_last_sequence(relaxed=True)
                            or last_move._get_starting_sequence()
                    )

                __, seq_format_values = last_move._get_sequence_format_param(
                    last_sequence
                )
                prefix1 = seq_format_values["prefix1"]
                prefix = prefix1
                if seq_format_values["year_length"] == 4:
                    prefix += "%(range_year)s"
                elif seq_format_values["year_length"] == 2:
                    prefix += "%(range_y)s"
                else:
                    # If there is not year so current values are valid
                    seq_vals = {
                        "padding": seq_format_values["seq_length"],
                        "suffix": seq_format_values["suffix"],
                        "prefix": prefix,
                        "date_range_ids": [],
                        "use_date_range": False,
                        "number_next_actual": seq_format_values["seq"] + 1,
                    }
                    return seq_vals
                prefix2 = seq_format_values.get("prefix2") or ""
                prefix += prefix2
                month = seq_format_values.get("month")  # It is 0 if only have year
                if month:
                    prefix += "%(range_month)s"
                prefix3 = seq_format_values.get("prefix3") or ""
                where_name_value = "%s%s%s%s%s%%" % (
                    prefix1,
                    "_" * seq_format_values["year_length"],
                    prefix2,
                    "_" * bool(month) * 2,
                    prefix3,
                )
                prefixes = prefix1 + prefix2
                select_year = (
                    "split_part(name, '%s', %d)" % (prefix2, prefixes.count(prefix2))
                    if prefix2
                    else "''"
                )
                prefixes += prefix3
                select_month = (
                    "split_part(name, '%s', %d)" % (prefix3, prefixes.count(prefix3))
                    if prefix3
                    else "''"
                )
                select_max_number = (
                        "MAX(split_part(name, '%s', %d)::INTEGER) AS max_number"
                        % (
                            prefixes[-1],
                            prefixes.count(prefixes[-1]) + 1,
                        )
                )
                query = (
                            "SELECT %s, %s, %s FROM account_move "
                            "WHERE name LIKE %%s AND journal_id=%%s GROUP BY 1,2"
                        ) % (
                            select_year,
                            select_month,
                            select_max_number,
                        )
                # It is not using user input
                # pylint: disable=sql-injection
                self.env.cr.execute(query, (where_name_value, self.id))
                res = self.env.cr.fetchall()
                prefix += prefix3
                seq_vals = {
                    "padding": seq_format_values["seq_length"],
                    "suffix": seq_format_values["suffix"],
                    "prefix": prefix,
                    "date_range_ids": [],
                    "use_date_range": True,
                }
                for year, month, max_number in res:
                    if not year and not month:
                        seq_vals.update(
                            {
                                "use_date_range": False,
                                "number_next_actual": max_number + 1,
                            }
                        )
                        continue
                    if len(year) == 2:
                        # Year >=50 will be considered as last century 1950
                        # Year <=49 will be considered as current century 2049
                        if int(year) >= 50:
                            year = "19" + year
                        else:
                            year = "20" + year
                    if month:
                        date_from = fields.Date.to_date("%s-%s-1" % (year, month))
                        date_to = fields.Date.end_of(date_from, "month")
                    else:
                        date_from = fields.Date.to_date("%s-1-1" % year)
                        date_to = fields.Date.to_date("%s-12-31" % year)
                    seq_vals["date_range_ids"].append(
                        (
                            0,
                            0,
                            {
                                "date_from": date_from,
                                "date_to": date_to,
                                "number_next_actual": max_number + 1,
                            },
                        )
                    )
                return seq_vals
        except Exception as e:
            _logger.warning("%s %s", msg_err, e)
        return {}

    def needs_fiscal_sequence(self, move_type=None):
        """
        Determina si el diario necesita secuencia fiscal basado en:
        - Si tiene documento fiscal configurado
        - El tipo de movimiento (si se especifica)
        """
        self.ensure_one()
        
        # Si no tiene documento fiscal configurado, no necesita secuencia fiscal
        if not self.document_fiscal:
            if move_type == 'out_refund':
                _logger.info(
                    "NC needs_fiscal_sequence: diario %s sin documento fiscal",
                    self.display_name,
                )
            return False
            
        # Si se especifica el tipo de movimiento, verificar si aplica
        if move_type:
            # Solo facturas y notas de crédito/débito necesitan secuencias fiscales
            fiscal_move_types = ['out_invoice', 'in_invoice', 'out_refund', 'in_refund', 'in_receipt']
            if move_type not in fiscal_move_types:
                if move_type == 'out_refund':
                    _logger.info(
                        "NC needs_fiscal_sequence: tipo %s no fiscal en diario %s",
                        move_type, self.display_name,
                    )
                return False
                
        if move_type == 'out_refund':
            _logger.info(
                "NC needs_fiscal_sequence: diario %s OK (documento_fiscal=%s)",
                self.display_name, self.document_fiscal,
            )
        return True

    def get_fiscal_sequence(self, move_type=None):
        """
        Obtiene la secuencia fiscal apropiada según el tipo de movimiento
        """
        self.ensure_one()
        
        if not self.needs_fiscal_sequence(move_type):
            if move_type == 'out_refund':
                _logger.info(
                    "NC get_fiscal_sequence: diario %s no requiere secuencia",
                    self.display_name,
                )
            return False
            
        # Para notas de crédito/débito, usar refund_sequence_id si existe
        if move_type in ['out_refund', 'in_refund'] and self.refund_sequence_id:
            if not self.refund_sequence_id.is_fiscal and self.document_fiscal == 'credit':
                # Forzar marcado fiscal para secuencia de NC si está configurada en diario fiscal
                self.refund_sequence_id.sudo().write({
                    'is_fiscal': True,
                    'fiscal_type': 'credit_note',
                })
                _logger.warning(
                    "NC get_fiscal_sequence: refund_sequence_id marcado como fiscal (%s)",
                    self.refund_sequence_id.display_name,
                )
            if move_type == 'out_refund':
                _logger.info(
                    "NC get_fiscal_sequence: usando refund_sequence_id %s",
                    self.refund_sequence_id.display_name,
                )
            return self.refund_sequence_id
        elif self.sequence_id:
            if move_type == 'out_refund':
                _logger.info(
                    "NC get_fiscal_sequence: usando sequence_id %s",
                    self.sequence_id.display_name,
                )
            return self.sequence_id
            
        if move_type == 'out_refund':
            _logger.warning(
                "NC get_fiscal_sequence: no hay secuencia en diario %s",
                self.display_name,
            )
        return False
