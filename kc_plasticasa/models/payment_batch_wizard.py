# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class KcPaymentBatchWizard(models.TransientModel):
    _name = "kc.payment.batch.wizard"
    _description = "Crear Lote de Pagos (KC)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
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
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        domain="[('type','in',('bank','cash')), ('company_id','=',company_id)]",
        check_company=True,
    )
    payment_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    batch_reference = fields.Char(string="Referencia del lote")
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Método de pago",
        domain="[('id', 'in', available_payment_method_line_ids)]",
    )
    available_payment_method_line_ids = fields.Many2many(
        "account.payment.method.line",
        compute="_compute_available_payment_method_line_ids",
    )
    load_mode = fields.Selection(
        [("manual", "Manual"), ("invoices", "Desde Facturas")],
        required=True,
        default="manual",
    )
    auto_post = fields.Boolean(string="Publicar pagos automáticamente")
    line_ids = fields.One2many("kc.payment.batch.line", "wizard_id", string="Líneas")
    invoice_ids = fields.Many2many("account.move", string="Facturas")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_model == "account.move" and active_ids:
            moves = self.env["account.move"].browse(active_ids)
            res.setdefault("load_mode", "invoices")
            if "invoice_ids" in fields_list:
                res["invoice_ids"] = [(6, 0, active_ids)]
            if "line_ids" in fields_list:
                lines = []
                for invoice in moves:
                    if invoice.state != "posted" or invoice.amount_residual <= 0:
                        continue
                    payment_ref = invoice.name or invoice.ref or invoice.payment_reference or ""
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "partner_id": invoice.partner_id.id,
                                "invoice_id": invoice.id,
                                "amount_due": invoice.amount_residual,
                                "amount": invoice.amount_residual,
                                "payment_ref": payment_ref,
                            },
                        )
                    )
                res["line_ids"] = lines
        return res

    @api.onchange("partner_type")
    def _onchange_partner_type(self):
        for wizard in self:
            wizard.payment_type = "outbound" if wizard.partner_type == "supplier" else "inbound"

    @api.onchange("journal_id", "company_id")
    def _onchange_journal_id(self):
        for wizard in self:
            if wizard.journal_id:
                wizard.currency_id = wizard.journal_id.currency_id or wizard.journal_id.company_id.currency_id
            else:
                wizard.currency_id = wizard.company_id.currency_id

    @api.depends("journal_id")
    def _compute_available_payment_method_line_ids(self):
        for wizard in self:
            if not wizard.journal_id:
                wizard.available_payment_method_line_ids = False
                continue
            wizard.available_payment_method_line_ids = (
                wizard.journal_id.inbound_payment_method_line_ids |
                wizard.journal_id.outbound_payment_method_line_ids
            )

    @api.onchange("journal_id")
    def _onchange_payment_method_line(self):
        for wizard in self:
            if wizard.journal_id:
                wizard.payment_method_line_id = wizard.available_payment_method_line_ids[:1]
            else:
                wizard.payment_method_line_id = False

    def _get_invoice_domain(self):
        self.ensure_one()
        move_types = ["in_invoice", "in_refund"] if self.partner_type == "supplier" else ["out_invoice", "out_refund"]
        return [
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", move_types),
        ]

    def action_select_all_invoices(self):
        self.ensure_one()
        invoices = self.env["account.move"].search(self._get_invoice_domain())
        self.invoice_ids = [(6, 0, invoices.ids)]
        return None

    def action_load_invoices(self):
        self.ensure_one()
        lines = [(5, 0, 0)]
        for invoice in self.invoice_ids:
            if invoice.state != "posted" or invoice.amount_residual <= 0:
                continue
            payment_ref = invoice.name or invoice.ref or invoice.payment_reference or ""
            lines.append(
                (
                    0,
                    0,
                    {
                        "partner_id": invoice.partner_id.id,
                        "invoice_id": invoice.id,
                        "amount_due": invoice.amount_residual,
                        "amount": invoice.amount_residual,
                        "payment_ref": payment_ref,
                    },
                )
            )
        self.line_ids = lines
        return None

    def _get_payment_method_line(self):
        self.ensure_one()
        if self.payment_method_line_id:
            return self.payment_method_line_id
        journal = self.journal_id
        payment_type = self.payment_type
        if hasattr(journal, "_get_available_payment_method_lines"):
            method_lines = journal._get_available_payment_method_lines(payment_type)
        else:
            method_lines = journal.inbound_payment_method_line_ids if payment_type == "inbound" else journal.outbound_payment_method_line_ids
        if not method_lines:
            raise UserError(_("El diario seleccionado no tiene métodos de pago disponibles."))
        return method_lines[0]

    def _validate_before_create(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Debe agregar al menos una línea al lote."))
        if self.journal_id.type not in ("bank", "cash"):
            raise UserError(_("El diario debe ser de tipo Banco/Caja."))
        if self.partner_type == "supplier" and self.payment_type != "outbound":
            raise UserError(_("Para Proveedor, la dirección del pago debe ser Saliente."))
        if self.partner_type == "customer" and self.payment_type != "inbound":
            raise UserError(_("Para Cliente, la dirección del pago debe ser Entrante."))
        invalid_lines = self.line_ids.filtered(lambda l: l.amount <= 0)
        if invalid_lines:
            raise ValidationError(_("No se permiten montos menores o iguales a cero."))
        if self.load_mode == "invoices":
            invalid_lines = self.line_ids.filtered(lambda l: not l.invoice_id and not l.is_advance)
            if invalid_lines:
                raise UserError(_("En modo facturas, cada línea debe tener una factura o marcarse como Anticipo."))
            invoices = self.line_ids.mapped("invoice_id").filtered(lambda m: m)
            invalid_invoices = invoices.filtered(lambda m: m.state != "posted" or m.amount_residual <= 0)
            if invalid_invoices:
                raise UserError(_("Solo se permiten facturas publicadas con saldo pendiente."))
            overpaid_lines = self.line_ids.filtered(lambda l: l.invoice_id and l.amount > l.invoice_id.amount_residual)
            if overpaid_lines:
                raise ValidationError(_("El monto a pagar no puede ser mayor que el saldo pendiente."))
            currencies = invoices.mapped("currency_id")
            if len(currencies) == 1 and self.currency_id and currencies[0] != self.currency_id:
                raise UserError(_("La moneda del lote no coincide con la moneda de las facturas."))

    def action_generate_batch(self):
        self.ensure_one()
        if not self.batch_reference:
            self.batch_reference = self.env["ir.sequence"].next_by_code("kc.payment.batch.wizard") or _("Nuevo")
        self._validate_before_create()

        payments = self.env["account.payment"]
        for line in self.line_ids:
            if line.invoice_id:
                payment = self._create_payment_from_invoice(line)
            else:
                payment = self._create_manual_payment(line)
            payments |= payment

        payment_groups = {}
        for payment in payments:
            currency = payment.currency_id
            payment_groups.setdefault(currency.id, self.env["account.payment"])
            payment_groups[currency.id] |= payment

        if "account.batch.payment" in self.env:
            batches = self.env["account.batch.payment"]
            for currency_id, grouped_payments in payment_groups.items():
                batch_vals = {
                    "journal_id": self.journal_id.id,
                    "batch_type": self.payment_type,
                    "date": self.payment_date,
                    "payment_ids": [(6, 0, grouped_payments.ids)],
                }
                if self.batch_reference:
                    suffix = self.env["res.currency"].browse(currency_id).name
                    batch_vals["name"] = f"{self.batch_reference} - {suffix}"
                batches |= self.env["account.batch.payment"].create(batch_vals)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Pagos creados"),
                    "message": _("Se generaron %(count)s pagos en %(batches)s lote(s).", count=len(payments), batches=len(payment_groups)),
                    "type": "success",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        batches = self.env["pa.account.payment.batch"]
        for currency_id, grouped_payments in payment_groups.items():
            batch_vals = {
                "journal_id": self.journal_id.id,
                "date": self.payment_date,
            }
            if self.batch_reference:
                suffix = self.env["res.currency"].browse(currency_id).name
                batch_vals["name"] = f"{self.batch_reference} - {suffix}"
            batch = self.env["pa.account.payment.batch"].create(batch_vals)
            grouped_payments.write({"pa_batch_id": batch.id})
            batches |= batch
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pagos creados"),
                "message": _("Se generaron %(count)s pagos en %(batches)s lote(s).", count=len(payments), batches=len(payment_groups)),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _create_payment_from_invoice(self, line):
        self.ensure_one()
        invoice = line.invoice_id
        payment_lines = invoice.line_ids.filtered(lambda l: l.display_type == "payment_term")
        if not payment_lines:
            raise UserError(_("No se encontraron líneas de pago en la factura %s.") % (invoice.display_name,))
        register = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create(
            {
                "line_ids": [(6, 0, payment_lines.ids)],
                "amount": line.amount,
                "payment_date": self.payment_date,
                "journal_id": self.journal_id.id,
                "communication": line.payment_ref or invoice.name or "",
                "payment_method_line_id": self._get_payment_method_line().id,
            }
        )
        payments = register._create_payments()
        return payments

    def _create_manual_payment(self, line):
        self.ensure_one()
        payment_method_line = self._get_payment_method_line()
        vals = {
            "partner_id": line.partner_id.id,
            "amount": line.amount,
            "date": self.payment_date,
            "journal_id": self.journal_id.id,
            "payment_type": self.payment_type,
            "partner_type": self.partner_type,
            "payment_method_line_id": payment_method_line.id,
            "payment_reference": line.payment_ref,
        }
        if self.currency_id:
            vals["currency_id"] = self.currency_id.id
        payment = self.env["account.payment"].create(vals)
        if self.auto_post:
            payment.action_post()
        return payment


class KcPaymentBatchLine(models.TransientModel):
    _name = "kc.payment.batch.line"
    _description = "Línea de Lote de Pagos (KC)"

    wizard_id = fields.Many2one("kc.payment.batch.wizard", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Contacto", required=True)
    invoice_id = fields.Many2one("account.move", string="Factura")
    is_advance = fields.Boolean(string="Anticipo")
    amount_due = fields.Monetary(string="Saldo pendiente", compute="_compute_amount_due", readonly=True)
    amount = fields.Monetary(string="Monto a pagar", required=True)
    payment_ref = fields.Char(string="Referencia")
    currency_id = fields.Many2one(related="wizard_id.currency_id", readonly=True)

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        for line in self:
            if line.invoice_id:
                line.is_advance = False
                line.partner_id = line.invoice_id.partner_id
                line.amount = line.invoice_id.amount_residual
                line.payment_ref = line.invoice_id.name or line.invoice_id.ref or line.invoice_id.payment_reference or ""
            else:
                line.amount = 0.0

    @api.onchange("is_advance")
    def _onchange_is_advance(self):
        for line in self:
            if line.is_advance:
                line.invoice_id = False

    @api.depends("invoice_id")
    def _compute_amount_due(self):
        for line in self:
            line.amount_due = line.invoice_id.amount_residual if line.invoice_id else 0.0

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("El monto debe ser mayor que cero."))
