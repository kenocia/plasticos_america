# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date


class KcSalesCommission(models.Model):
    _name = 'kc.sales.commission'
    _description = 'Cálculo de comisión de ventas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default='Nuevo',
        tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('calculated', 'Calculado'),
            ('confirmed', 'Confirmado'),
            ('payment_draft', 'Pago en borrador'),
            ('payment_posted', 'Pago confirmado'),
            ('locked', 'Bloqueado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
    )
    date_from = fields.Date(string='Fecha inicial', required=True, tracking=True)
    date_to = fields.Date(string='Fecha final', required=True, tracking=True)
    commission_calc_mode = fields.Selection(
        [
            ('parametrized', 'Por reglas (producto, categoría, empleado)'),
            ('employee_unit', 'Por unidades × tarifa del empleado'),
            ('employee_percent', 'Por % sobre ventas (tarifa del empleado)'),
        ],
        string='Base de cálculo',
        default='parametrized',
        required=True,
        tracking=True,
        help=(
            'Por reglas: se usa la jerarquía producto → categoría → empleado. '
            'Por unidades o por % sobre ventas: solo la tarifa del empleado (cantidad × tarifa o % sobre venta).'
        ),
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
        store=True,
    )
    payment_ids = fields.One2many(
        'account.payment',
        'commission_id',
        string='Pagos',
        copy=False,
    )
    payment_count = fields.Integer(string='Nº pagos', compute='_compute_payment_count')

    client_line_ids = fields.One2many(
        'kc.sales.commission.client.line',
        'commission_id',
        string='Clientes',
    )
    invoice_line_ids = fields.One2many(
        'kc.sales.commission.invoice.line',
        'commission_id',
        string='Facturas',
    )
    detail_line_ids = fields.One2many(
        'kc.sales.commission.detail.line',
        'commission_id',
        string='Detalle por producto',
    )

    total_clients = fields.Integer(string='Total clientes', compute='_compute_totals', store=True)
    total_invoices = fields.Integer(string='Total facturas', compute='_compute_totals', store=True)
    total_subtotal = fields.Monetary(
        string='Subtotal facturado',
        compute='_compute_totals',
        currency_field='currency_id',
        store=True,
    )
    total_tax = fields.Monetary(
        string='Total ISV',
        compute='_compute_totals',
        currency_field='currency_id',
        store=True,
    )
    total_amount = fields.Monetary(
        string='Total venta',
        compute='_compute_totals',
        currency_field='currency_id',
        store=True,
    )
    total_commission = fields.Monetary(
        string='Total comisión',
        compute='_compute_totals',
        currency_field='currency_id',
        store=True,
    )
    payment_paid_total = fields.Monetary(
        string='Pagado (confirmado)',
        compute='_compute_payment_balance',
        currency_field='currency_id',
        help='Suma de pagos en estado pagado.',
    )
    payment_registered_total = fields.Monetary(
        string='Importe en pagos',
        compute='_compute_payment_balance',
        currency_field='currency_id',
        help='Suma de importes en borrador, en proceso o pagados (excluye cancelados).',
    )
    commission_pending_balance = fields.Monetary(
        string='Saldo pendiente',
        compute='_compute_payment_balance',
        currency_field='currency_id',
        help='Total comisión menos importe ya cubierto por pagos registrados.',
    )
    commission_payment_partial = fields.Boolean(
        string='Pago parcial',
        compute='_compute_payment_balance',
        help='Queda saldo pendiente respecto al total de comisión.',
    )

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends(
        'total_commission',
        'currency_id',
        'payment_ids',
        'payment_ids.amount',
        'payment_ids.state',
    )
    def _compute_payment_balance(self):
        for rec in self:
            valid = rec.payment_ids.filtered(lambda p: p.state not in ('canceled', 'rejected'))
            registered = sum(valid.mapped('amount'))
            paid = rec.payment_ids.filtered(lambda p: p.state == 'paid')
            paid_sum = sum(paid.mapped('amount'))
            rec.payment_registered_total = registered
            rec.payment_paid_total = paid_sum
            pending = (rec.total_commission or 0.0) - registered
            if rec.currency_id:
                pending = rec.currency_id.round(pending)
            rec.commission_pending_balance = pending
            reg_ok = rec.currency_id.round(registered) if rec.currency_id else registered
            pend_ok = rec.currency_id.round(pending) if rec.currency_id else pending
            rec.commission_payment_partial = reg_ok > 0 and pend_ok > 0

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('La fecha inicial no puede ser posterior a la fecha final.'))

    @api.depends(
        'client_line_ids',
        'invoice_line_ids',
        'invoice_line_ids.amount_untaxed',
        'invoice_line_ids.amount_tax',
        'invoice_line_ids.amount_total',
        'detail_line_ids',
        'detail_line_ids.commission_amount',
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_clients = len(rec.client_line_ids)
            rec.total_invoices = len(rec.invoice_line_ids)
            rec.total_subtotal = sum(rec.invoice_line_ids.mapped('amount_untaxed'))
            rec.total_tax = sum(rec.invoice_line_ids.mapped('amount_tax'))
            rec.total_amount = sum(rec.invoice_line_ids.mapped('amount_total'))
            rec.total_commission = sum(rec.detail_line_ids.mapped('commission_amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') in (False, 'Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('kc.sales.commission') or 'Nuevo'
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('kc_commission_sync'):
            return super().write(vals)
        if self.env.context.get('kc_allow_commission_write'):
            return super().write(vals)
        protected = {
            'name',
            'state',
            'date_from',
            'date_to',
            'commission_calc_mode',
            'company_id',
            'employee_id',
            'client_line_ids',
            'invoice_line_ids',
            'detail_line_ids',
        }
        for rec in self:
            if rec.state not in ('draft', 'calculated') and set(vals) & protected:
                raise UserError(
                    _(
                        'No puede modificar datos del cálculo en este estado: solo es editable en '
                        'borrador o calculado. Use «Volver a calculado» si aplica.'
                    )
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise UserError(
                    _('Solo puede eliminar cálculos en borrador o cancelados.')
                )
        return super().unlink()

    def _sale_amount_company_currency(self, line):
        """Subtotal de línea en moneda de la compañía (tipo de cambio a fecha de factura)."""
        self.ensure_one()
        move = line.move_id
        company = move.company_id
        comp_currency = company.currency_id
        inv_date = move.invoice_date or move.date
        sub = line.price_subtotal or 0.0
        line_currency = line.currency_id
        if not line_currency or line_currency == comp_currency:
            return comp_currency.round(sub)
        return line_currency._convert(sub, comp_currency, company, inv_date)

    def _is_product_commission_excluded(self, product):
        self.ensure_one()
        tmpl = product.product_tmpl_id
        if tmpl.commission_excluded:
            return True
        categ = tmpl.categ_id
        while categ:
            if categ.commission_excluded:
                return True
            categ = categ.parent_id
        return False

    def _get_commission_params_for_product(self, product):
        """Prioridad: producto (tipo definido) > categoría (jerarquía) > empleado."""
        self.ensure_one()
        tmpl = product.product_tmpl_id
        if tmpl.commission_use_custom and tmpl.commission_type:
            return tmpl.commission_type, tmpl.commission_rate or 0.0
        categ = tmpl.categ_id
        while categ:
            if categ.commission_use_custom and categ.commission_type:
                return categ.commission_type, categ.commission_rate or 0.0
            categ = categ.parent_id
        emp = self.employee_id
        return emp.commission_type or 'unit', emp.commission_rate or 0.0

    def _get_effective_commission_params(self, product):
        """Tipo y tarifa según el modo elegido en el cálculo."""
        self.ensure_one()
        mode = self.commission_calc_mode
        if mode == 'parametrized':
            return self._get_commission_params_for_product(product)
        emp = self.employee_id
        rate = emp.commission_rate or 0.0
        if mode == 'employee_unit':
            return 'unit', rate
        if mode == 'employee_percent':
            return 'percent', rate
        return self._get_commission_params_for_product(product)

    def _compute_commission_amount(self, quantity, sale_amount, commission_type, commission_rate):
        """Calcula el monto de comisión según tipo (unidad o porcentaje)."""
        self.ensure_one()
        currency = self.currency_id
        rate = commission_rate or 0.0
        if commission_type == 'percent':
            amount = (sale_amount or 0.0) * (rate / 100.0)
        else:
            amount = (quantity or 0.0) * rate
        return currency.round(amount) if currency else round(amount, 2)

    def _get_assigned_clients(self):
        """Clientes con este empleado como comisionista, respetando compañía."""
        self.ensure_one()
        domain = [
            ('commission_employee_id', '=', self.employee_id.id),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ]
        return self.env['res.partner'].search(domain)

    def _get_valid_invoices(self, partner_ids):
        """Facturas y notas de crédito de cliente publicadas en rango (importes en moneda compañía)."""
        self.ensure_one()
        if not partner_ids:
            return self.env['account.move']
        domain = [
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('partner_id.commercial_partner_id', 'in', partner_ids.ids),
        ]
        return self.env['account.move'].search(
            domain,
            order='invoice_date asc, name asc, id asc',
        )

    def _prepare_client_lines(self, partners):
        """Valores para crear líneas de clientes."""
        self.ensure_one()
        return [
            {
                'commission_id': self.id,
                'partner_id': p.id,
            }
            for p in partners
        ]

    def _prepare_invoice_lines(self, moves):
        """Valores para líneas resumen por factura."""
        self.ensure_one()
        vals_list = []
        for move in moves:
            vals_list.append({
                'commission_id': self.id,
                'invoice_id': move.id,
                'move_type': move.move_type,
                'invoice_date': move.invoice_date,
                'invoice_name': move.name,
                'partner_id': move.partner_id.id,
                'amount_untaxed': move.amount_untaxed,
                'amount_tax': move.amount_tax,
                'amount_total': move.amount_total,
                'currency_id': move.currency_id.id,
            })
        return vals_list

    def _filter_invoice_product_lines(self, move):
        """Líneas de factura con producto e impacto comercial (Odoo 18: display_type product)."""
        self.ensure_one()
        return move.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id
        )

    def _prepare_detail_lines(self, moves):
        """Construye detalle agrupado por producto (suma de líneas de factura en moneda compañía)."""
        self.ensure_one()
        currency = self.currency_id
        agg = defaultdict(
            lambda: {
                'qty': 0.0,
                'sale_amount': 0.0,
                'invoice_dates': [],
                'move_types': [],
                'partner_ids': set(),
            }
        )

        for move in moves:
            for line in self._filter_invoice_product_lines(move):
                product = line.product_id
                if self._is_product_commission_excluded(product):
                    continue
                qty = line.quantity or 0.0
                sale_amount = self._sale_amount_company_currency(line)
                pid = product.id
                bucket = agg[pid]
                bucket['qty'] += qty
                bucket['sale_amount'] += sale_amount
                if move.invoice_date:
                    bucket['invoice_dates'].append(move.invoice_date)
                bucket['move_types'].append(move.move_type)
                if move.partner_id:
                    bucket['partner_ids'].add(move.partner_id.id)

        vals_list = []
        for product_id, data in agg.items():
            product = self.env['product.product'].browse(product_id)
            total_qty = data['qty']
            total_sale = data['sale_amount']
            if currency:
                total_sale = currency.round(total_sale)
            comm_type, comm_rate = self._get_effective_commission_params(product)
            total_comm = self._compute_commission_amount(total_qty, total_sale, comm_type, comm_rate)
            inv_dates = data['invoice_dates']
            inv_date = min(inv_dates) if inv_dates else False
            mtypes = set(data['move_types'])
            move_type = mtypes.pop() if len(mtypes) == 1 else False
            partner_id = False
            if len(data['partner_ids']) == 1:
                partner_id = next(iter(data['partner_ids']))
            price_unit = (total_sale / total_qty) if total_qty else 0.0

            vals_list.append({
                'commission_id': self.id,
                'invoice_id': False,
                'move_type': move_type,
                'invoice_date': inv_date,
                'partner_id': partner_id,
                'product_id': product_id,
                'product_code': product.default_code or '',
                'quantity': total_qty,
                'price_unit': price_unit,
                'sale_amount': total_sale,
                'commission_rate': comm_rate,
                'commission_type': comm_type,
                'commission_amount': total_comm,
                'currency_id': currency.id,
            })

        vals_list.sort(key=lambda v: (v['product_code'] or '', v['product_id']))
        return vals_list

    def _clear_lines(self):
        """Elimina todas las líneas hijas (sin duplicar al recalcular)."""
        for rec in self:
            rec.detail_line_ids.unlink()
            rec.invoice_line_ids.unlink()
            rec.client_line_ids.unlink()

    def _sync_state_from_payments(self):
        """Sincroniza estado según pagos vinculados (conciliación bloquea todo)."""
        for rec in self:
            if rec.state == 'cancel':
                continue
            payments = rec.payment_ids.filtered(lambda p: p.state != 'canceled')
            if not payments:
                if rec.state == 'locked':
                    continue
                if rec.state in ('payment_draft', 'payment_posted') and rec.detail_line_ids:
                    rec.with_context(kc_commission_sync=True).write({'state': 'confirmed'})
                continue

            if not all(p.state == 'paid' for p in payments):
                rec.with_context(kc_commission_sync=True).write({'state': 'payment_draft'})
                continue

            if all(p.is_reconciled for p in payments):
                rec.with_context(kc_commission_sync=True).write({'state': 'locked'})
            else:
                rec.with_context(kc_commission_sync=True).write({'state': 'payment_posted'})

    def generate_commission_lines(self):
        """
        Flujo principal: limpia, carga clientes, facturas, detalle y deja estado calculado.
        """
        for rec in self:
            if rec.state == 'locked':
                raise UserError(_('No puede recalcular un cálculo bloqueado.'))
            if rec.state not in ('draft', 'calculated'):
                raise UserError(
                    _('Solo puede generar o recalcular en borrador o calculado.')
                )
            if rec.date_from > rec.date_to:
                raise UserError(_('La fecha inicial no puede ser posterior a la fecha final.'))

            partners = rec._get_assigned_clients()
            if not partners:
                raise UserError(
                    _('El empleado %s no tiene clientes comerciales asignados como comisionista.')
                    % (rec.employee_id.name or '')
                )

            moves = rec._get_valid_invoices(partners)
            if not moves:
                raise UserError(
                    _(
                        'No hay facturas o notas de crédito de cliente publicadas en el rango indicado para los '
                        'clientes asignados a %s.'
                    )
                    % (rec.employee_id.name or '')
                )

            rec._clear_lines()

            client_vals = rec._prepare_client_lines(partners)
            if client_vals:
                self.env['kc.sales.commission.client.line'].create(client_vals)

            inv_vals = rec._prepare_invoice_lines(moves)
            if inv_vals:
                self.env['kc.sales.commission.invoice.line'].create(inv_vals)

            det_vals = rec._prepare_detail_lines(moves)
            if det_vals:
                self.env['kc.sales.commission.detail.line'].create(det_vals)
            else:
                raise UserError(
                    _(
                        'No hay líneas de comisión generadas (revisar productos excluidos o líneas sin producto).'
                    )
                )

            rec.write({'state': 'calculated'})
        return True

    def action_recalculate(self):
        for rec in self:
            if rec.state == 'locked':
                raise UserError(_('No puede recalcular un cálculo bloqueado.'))
            if rec.payment_ids.filtered(lambda p: p.state != 'canceled'):
                raise UserError(_('No puede recalcular mientras existan pagos asociados (no cancelados).'))
            rec.generate_commission_lines()
        return True

    def action_confirm(self):
        """Pasa a confirmado: deja de permitir cambios hasta desconfirmar (si aplica)."""
        for rec in self:
            if rec.state != 'calculated':
                raise UserError(_('Solo puede confirmar un cálculo en estado Calculado.'))
        self.with_context(kc_allow_commission_write=True).write({'state': 'confirmed'})
        return True

    def action_unconfirm(self):
        """Vuelve a calculado si aún no hay pagos."""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Solo puede desconfirmar en estado Confirmado.'))
            if rec.payment_ids:
                raise UserError(_('No puede desconfirmar: ya existen pagos asociados.'))
        self.with_context(kc_allow_commission_write=True).write({'state': 'calculated'})
        return True

    def action_view_payments(self):
        """Abre la lista de pagos vinculados a esta comisión."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagos de comisión'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('commission_id', '=', self.id)],
            'context': {'default_commission_id': self.id},
        }

    def action_open_payment_wizard(self):
        self.ensure_one()
        if self.state == 'locked':
            raise UserError(_('La comisión está bloqueada.'))
        if self.state in ('draft', 'calculated', 'cancel'):
            raise UserError(_('Confirme el cálculo antes de registrar pagos.'))
        if self.state not in ('confirmed', 'payment_posted', 'payment_draft'):
            raise UserError(_('No puede registrar un pago en este estado.'))
        pending_bal = self.commission_pending_balance
        if self.currency_id:
            pending_bal = self.currency_id.round(pending_bal or 0.0)
        else:
            pending_bal = pending_bal or 0.0
        if pending_bal <= 0:
            raise UserError(_('No hay saldo pendiente de comisión por pagar.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagar comisión'),
            'res_model': 'kc.sales.commission.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_commission_id': self.id,
            },
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == 'locked':
                raise UserError(_('No puede cancelar un cálculo bloqueado.'))
            if rec.payment_ids.filtered(lambda p: p.state == 'paid'):
                raise UserError(_('No puede cancelar: existen pagos confirmados.'))
            if rec.payment_ids.filtered(lambda p: p.state in ('draft', 'in_process')):
                raise UserError(_('Cancele o elimine primero los pagos en borrador o en proceso.'))
        self.with_context(kc_allow_commission_write=True).write({'state': 'cancel'})
        return True

    def action_reset_to_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('kc_sales_commission.action_report_sales_commission').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        from ..report.sales_commission_xlsx import generate_commission_excel_action

        return generate_commission_excel_action(self)

    def get_report_emission_str(self):
        self.ensure_one()
        return format_date(self.env, fields.Date.context_today(self))


class KcSalesCommissionClientLine(models.Model):
    _name = 'kc.sales.commission.client.line'
    _description = 'Línea de cliente en comisión'

    commission_id = fields.Many2one(
        'kc.sales.commission',
        string='Comisión',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        related='commission_id.employee_id',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='commission_id.company_id',
        store=True,
    )


class KcSalesCommissionInvoiceLine(models.Model):
    _name = 'kc.sales.commission.invoice.line'
    _description = 'Línea de factura en comisión'

    commission_id = fields.Many2one(
        'kc.sales.commission',
        string='Comisión',
        required=True,
        ondelete='cascade',
    )
    invoice_id = fields.Many2one('account.move', string='Factura', required=True)
    move_type = fields.Selection(
        selection=[
            ('out_invoice', 'Factura'),
            ('out_refund', 'Nota de crédito'),
        ],
        string='Tipo',
    )
    invoice_date = fields.Date(string='Fecha')
    invoice_name = fields.Char(string='Factura')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    amount_untaxed = fields.Monetary(string='Subtotal', currency_field='currency_id')
    amount_tax = fields.Monetary(string='ISV', currency_field='currency_id')
    amount_total = fields.Monetary(string='Total', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency')


class KcSalesCommissionDetailLine(models.Model):
    _name = 'kc.sales.commission.detail.line'
    _description = 'Detalle de comisión por producto (agrupado)'
    _order = 'product_code, product_id'

    commission_id = fields.Many2one(
        'kc.sales.commission',
        string='Comisión',
        required=True,
        ondelete='cascade',
    )
    invoice_id = fields.Many2one('account.move', string='Factura')
    move_type = fields.Selection(
        selection=[
            ('out_invoice', 'Factura'),
            ('out_refund', 'Nota de crédito'),
        ],
        string='Tipo',
    )
    invoice_date = fields.Date(string='Fecha')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    product_id = fields.Many2one('product.product', string='Producto')
    product_code = fields.Char(string='Código producto')
    quantity = fields.Float(string='Unidades')
    price_unit = fields.Float(string='Precio unitario')
    sale_amount = fields.Monetary(string='Venta', currency_field='currency_id')
    commission_rate = fields.Float(string='Comisión aplicada', digits=(16, 6))
    commission_type = fields.Selection(
        [
            ('unit', 'Por unidad'),
            ('percent', 'Por porcentaje'),
        ],
        string='Tipo comisión',
    )
    commission_amount = fields.Monetary(string='Comisión', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency')
