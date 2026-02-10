# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaAccountPaymentBatch(models.Model):
    _name = "pa.account.payment.batch"
    _description = "Lote de Pagos (Personalizado)"
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, string="Referencia")
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        domain=[("type", "in", ("bank", "cash"))],
        check_company=True,
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Método de pago",
        domain="[('id', 'in', available_payment_method_line_ids)]",
        required=False,
    )
    available_payment_method_line_ids = fields.Many2many(
        "account.payment.method.line",
        compute="_compute_available_payment_method_line_ids",
    )
    company_id = fields.Many2one(related="journal_id.company_id", readonly=True)
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("applied", "Aplicado"),
        ],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many(
        "pa.account.payment.batch.line",
        "batch_id",
        string="Líneas",
    )
    payment_ids = fields.One2many("account.payment", "pa_batch_id", string="Pagos")
    auto_post = fields.Boolean(string="Publicar pagos automáticamente")
    amount_total = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_amount_total",
        store=True,
        readonly=True,
    )

    @api.depends("journal_id")
    def _compute_currency_id(self):
        for batch in self:
            batch.currency_id = batch.journal_id.currency_id or batch.journal_id.company_id.currency_id

    @api.depends("journal_id")
    def _compute_available_payment_method_line_ids(self):
        for batch in self:
            if not batch.journal_id:
                batch.available_payment_method_line_ids = False
                continue
            batch.available_payment_method_line_ids = (
                batch.journal_id.inbound_payment_method_line_ids |
                batch.journal_id.outbound_payment_method_line_ids
            )

    @api.onchange("journal_id")
    def _onchange_journal_id_payment_method(self):
        for batch in self:
            if batch.journal_id:
                batch.payment_method_line_id = batch.available_payment_method_line_ids[:1]
            else:
                batch.payment_method_line_id = False

    @api.depends("payment_ids.amount", "payment_ids.currency_id", "payment_ids.date")
    def _compute_amount_total(self):
        for batch in self:
            total = 0.0
            for payment in batch.payment_ids:
                total += payment.currency_id._convert(
                    payment.amount,
                    batch.currency_id,
                    payment.company_id,
                    payment.date or fields.Date.context_today(self),
                )
            batch.amount_total = total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("pa.account.payment.batch") or _("Nuevo")
        return super().create(vals_list)

    def action_create_payments(self):
        for batch in self:
            if not batch.line_ids:
                raise ValidationError(_("Debe agregar al menos una línea."))
            if batch.journal_id.type not in ("bank", "cash"):
                raise ValidationError(_("El diario debe ser de tipo Banco/Caja."))
            payments = self.env["account.payment"]
            for line in batch.line_ids:
                if line.amount <= 0:
                    raise ValidationError(_("No se permiten montos menores o iguales a cero."))
                payment_method_line = batch._get_payment_method_line(line.payment_type)
                vals = {
                    "partner_id": line.partner_id.id,
                    "amount": line.amount,
                    "date": batch.date,
                    "journal_id": batch.journal_id.id,
                    "payment_type": line.payment_type,
                    "partner_type": line.partner_type,
                    "payment_method_line_id": payment_method_line.id,
                    "payment_reference": line.payment_ref,
                    "pa_batch_id": batch.id,
                }
                if batch.currency_id:
                    vals["currency_id"] = batch.currency_id.id
                payment = self.env["account.payment"].create(vals)
                if batch.auto_post:
                    payment.action_post()
                payments |= payment
            batch.line_ids.write({"is_processed": True})
            batch.state = "applied"
        return True

    def _get_payment_method_line(self, payment_type):
        self.ensure_one()
        if self.payment_method_line_id:
            return self.payment_method_line_id
        journal = self.journal_id
        if hasattr(journal, "_get_available_payment_method_lines"):
            method_lines = journal._get_available_payment_method_lines(payment_type)
        else:
            method_lines = journal.inbound_payment_method_line_ids if payment_type == "inbound" else journal.outbound_payment_method_line_ids
        if not method_lines:
            raise ValidationError(_("El diario seleccionado no tiene métodos de pago disponibles."))
        return method_lines[0]


class AccountPayment(models.Model):
    _inherit = "account.payment"

    pa_batch_id = fields.Many2one(
        "pa.account.payment.batch",
        string="Lote de pagos (KC)",
        ondelete="set null",
        copy=False,
        check_company=True,
    )


class PaAccountPaymentBatchLine(models.Model):
    _name = "pa.account.payment.batch.line"
    _description = "Línea de Lote de Pagos (KC)"

    batch_id = fields.Many2one("pa.account.payment.batch", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Contacto", required=True)
    amount = fields.Monetary(string="Importe", required=True)
    payment_ref = fields.Char(string="Referencia de pago")
    partner_type = fields.Selection(
        [("supplier", "Proveedor"), ("customer", "Cliente")],
        required=True,
        default="supplier",
    )
    payment_type = fields.Selection(
        [("outbound", "Saliente"), ("inbound", "Entrante")],
        required=True,
        default="outbound",
    )
    is_processed = fields.Boolean(default=False)
    currency_id = fields.Many2one(related="batch_id.currency_id", readonly=True)
