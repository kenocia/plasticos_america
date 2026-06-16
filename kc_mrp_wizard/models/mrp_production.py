# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.tools.float_utils import float_is_zero


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.depends(
        'move_raw_ids.state', 'move_raw_ids.quantity', 'move_finished_ids.state',
        'workorder_ids.state', 'product_qty', 'qty_producing', 'move_raw_ids.picked')
    def _compute_state(self):
        """Como el estándar, pero «Hecho» exige también que todas las OT estén cerradas.

        El cálculo original puede dejar la MO en Hecho solo porque los movimientos de stock
        están terminados, mientras las órdenes de trabajo siguen «En progreso» (p. ej. lote tablet).
        """
        for production in self:
            if not production.state or not production.product_uom_id or not (production.id or production._origin.id):
                production.state = 'draft'
            elif production.state == 'cancel' or (production.move_finished_ids and all(move.state == 'cancel' for move in production.move_finished_ids)):
                production.state = 'cancel'
            elif (
                production.state == 'done'
                or (
                    (production.move_raw_ids and all(move.state in ('cancel', 'done') for move in production.move_raw_ids))
                    and all(move.state in ('cancel', 'done') for move in production.move_finished_ids)
                    and (
                        not production.workorder_ids
                        or all(wo_state in ('done', 'cancel') for wo_state in production.workorder_ids.mapped('state'))
                    )
                )
            ):
                production.state = 'done'
            elif production.workorder_ids and all(wo_state in ('done', 'cancel') for wo_state in production.workorder_ids.mapped('state')):
                production.state = 'to_close'
            elif not production.workorder_ids and float_compare(production.qty_producing, production.product_qty, precision_rounding=production.product_uom_id.rounding) >= 0:
                production.state = 'to_close'
            elif any(wo_state in ('progress', 'done') for wo_state in production.workorder_ids.mapped('state')):
                production.state = 'progress'
            elif production.product_uom_id and not float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
                production.state = 'progress'
            elif any(production.move_raw_ids.mapped('picked')):
                production.state = 'progress'

    def action_kc_relink_workorders_tablet(self):
        """Recalcula dependencias entre WO de esta MO con la configuración actual de operaciones."""
        for mo in self:
            if mo.state in ('done', 'cancel'):
                continue
            if not mo.workorder_ids:
                continue
            mo._link_workorders_and_moves()
            # Forzar evaluación de estado (pending/ready/waiting) según nuevos bloqueos.
            mo.workorder_ids.invalidate_recordset(['blocked_by_workorder_ids', 'state'])
            mo.workorder_ids._compute_state()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Secuencia WO recalculada'),
                'message': _('Se actualizaron las dependencias de órdenes de trabajo con la configuración vigente de la LdM.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def _link_workorders_and_moves(self):
        """Tras el enlace estándar, rompe la cadena secuencial en operaciones marcadas en la LdM.

        Odoo con ``allow_operation_dependencies`` desactivado enlaza cada WO con la anterior; eso bloquea
        p. ej. etiquetado PT mientras soplado/semi sigue en progreso. Las líneas de operación con
        ``kc_skip_sequential_wo_dependency`` no enlazan con la anterior; el resto del orden se mantiene.
        """
        super()._link_workorders_and_moves()
        for mo in self:
            if mo.bom_id.allow_operation_dependencies:
                continue

            def workorder_order(wo):
                return (wo.sequence, wo.id)

            previous_workorder = False
            for wo in mo.workorder_ids.sorted(workorder_order):
                op = wo.operation_id
                skip = op and op.kc_skip_sequential_wo_dependency
                if previous_workorder and not skip:
                    wo.blocked_by_workorder_ids = [Command.link(previous_workorder.id)]
                else:
                    wo.blocked_by_workorder_ids = [Command.clear()]
                previous_workorder = wo

    kc_tablet_lot_last_seq = fields.Integer(
        string='Último correlativo lote (tablet)',
        default=0,
        copy=False,
        help='Último correlativo usado en nombres {prefijo empresa}{número MO}-{seq} del asistente tablet.',
    )
    kc_prelabel_limit_policy = fields.Selection(
        [
            ('block', 'Bloquear'),
            ('warn', 'Solo advertencia (confirmación responsable)'),
        ],
        string='Excede pendiente',
        default='block',
        help='Si la suma de cantidades en pre-etiquetas supera lo pendiente por fabricar: '
             'bloquear o permitir con confirmación de usuario con permiso de responsable de fabricación.',
    )
    kc_prelabel_pending_qty = fields.Float(
        string='Cantidad pendiente',
        compute='_compute_kc_prelabel_pending_qty',
        digits='Product Unit of Measure',
    )

    kc_semi_ticket_ids = fields.One2many(
        'mrp.semi.ticket',
        'production_id',
        string='Tickets semiterminado',
    )
    kc_semi_ticket_count = fields.Integer(
        string='Tickets semi',
        compute='_compute_kc_semi_ticket_count',
    )
    kc_semi_adjustment_line_ids = fields.One2many(
        'kc.mrp.production.semi.adjustment.line',
        'production_id',
        string='Ajustes de salida semi',
    )
    kc_semi_adjust_scrap_qty_total = fields.Float(
        string='Total ajustado (merma / desecho)',
        compute='_compute_kc_semi_adjustment_totals',
        digits='Product Unit of Measure',
        help='Suma de cantidades de líneas marcadas como merma por desecho (misma UdM por línea; validar si hay varios productos).',
    )
    kc_semi_adjust_other_qty_total = fields.Float(
        string='Total ajustado (otras salidas)',
        compute='_compute_kc_semi_adjustment_totals',
        digits='Product Unit of Measure',
    )
    kc_resin_scrap_line_ids = fields.One2many(
        'kc.mrp.production.resin.scrap',
        'production_id',
        string='Merma material',
    )
    kc_resin_scrap_qty_total = fields.Float(
        string='Total merma material',
        compute='_compute_kc_resin_scrap_qty_total',
        digits='Product Unit of Measure',
        help='Suma de cantidades registradas; puede mezclar distintas unidades de medida.',
    )
    kc_prelabel_lot_ids = fields.One2many(
        'stock.lot',
        'kc_prelabel_production_id',
        string='Lotes pre-etiquetas',
    )
    kc_prelabel_lot_pending_ids = fields.Many2many(
        'stock.lot',
        string='Pre-etiquetas pendientes',
        compute='_compute_kc_prelabel_lot_pending_ids',
        help='Solo consulta: lotes de etiqueta anticipada en estado «Pendiente de producir» para esta orden. '
             'La creación y anulación se hace desde el asistente tablet.',
    )

    @api.depends('kc_prelabel_lot_ids', 'kc_prelabel_lot_ids.kc_prelabel_state')
    def _compute_kc_prelabel_lot_pending_ids(self):
        for mo in self:
            mo.kc_prelabel_lot_pending_ids = mo.kc_prelabel_lot_ids.filtered(
                lambda l: l.kc_prelabel_state == 'pending'
            )

    def _compute_kc_semi_ticket_count(self):
        for mo in self:
            mo.kc_semi_ticket_count = len(mo.kc_semi_ticket_ids)

    @api.depends(
        'kc_semi_adjustment_line_ids.quantity',
        'kc_semi_adjustment_line_ids.is_scrap_desecho',
    )
    def _compute_kc_semi_adjustment_totals(self):
        for mo in self:
            scrap_lines = mo.kc_semi_adjustment_line_ids.filtered(lambda l: l.is_scrap_desecho)
            other_lines = mo.kc_semi_adjustment_line_ids - scrap_lines
            mo.kc_semi_adjust_scrap_qty_total = sum(scrap_lines.mapped('quantity'))
            mo.kc_semi_adjust_other_qty_total = sum(other_lines.mapped('quantity'))

    def _compute_kc_resin_scrap_qty_total(self):
        for mo in self:
            mo.kc_resin_scrap_qty_total = sum(mo.kc_resin_scrap_line_ids.mapped('quantity'))

    def _kc_tablet_material_scrap_raw_moves(self):
        """Movimientos MP de la MO elegibles para merma en tablet.

        Con producción parcial por lote, Odoo duplica líneas en ``move_raw_ids``:
        las ya consumidas quedan con ``picked=True`` (columna «Consumido» en la MO)
        y las pendientes del siguiente lote con ``picked=False``. La merma debe
        aplicarse sobre el movimiento no consumido (stock aún no backflusheado).
        """
        self.ensure_one()
        return self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id.is_storable
            and not m.picked
        )

    @api.depends('product_qty', 'qty_produced')
    def _compute_kc_prelabel_pending_qty(self):
        Lot = self.env['stock.lot'].sudo()
        for mo in self:
            lots = Lot.search([
                ('kc_prelabel_production_id', '=', mo.id),
                ('kc_prelabel_state', '=', 'pending'),
            ])
            mo.kc_prelabel_pending_qty = sum(lots.mapped('kc_prelabel_qty'))

    def _kc_prelabel_pending_reserved_qty(self):
        self.ensure_one()
        lots = self.env['stock.lot'].search([
            ('kc_prelabel_production_id', '=', self.id),
            ('kc_prelabel_state', '=', 'pending'),
        ])
        return sum(lots.mapped('kc_prelabel_qty'))

    def _kc_prelabel_qty_remaining_to_make(self):
        self.ensure_one()
        return self.product_qty - self.qty_produced

    def _kc_prelabel_assert_can_reserve_print(self, additional_qty, force_manager_confirm=False):
        """Controla que impresión de pre-etiquetas no exceda pendiente según política de la MO."""
        self.ensure_one()
        rounding = self.product_uom_id.rounding
        remaining = self._kc_prelabel_qty_remaining_to_make()
        pending = self._kc_prelabel_pending_reserved_qty()
        total_after = pending + additional_qty
        if float_compare(total_after, remaining, precision_rounding=rounding) <= 0:
            return
        if self.kc_prelabel_limit_policy == 'block':
            raise UserError(
                _(
                    'Con esta tirada se supera lo pendiente por fabricar en la orden %s.\n'
                    'Pendiente de fabricar: %s %s; ya reservado en pre-etiquetas: %s; intento: +%s.\n'
                    'Puede cancelar pre-etiquetas pendientes o cambiar la política en la orden de fabricación.'
                )
                % (
                    self.name,
                    remaining,
                    self.product_uom_id.name,
                    pending,
                    additional_qty,
                )
            )
        if not force_manager_confirm:
            raise UserError(
                _(
                    'Advertencia: la tirada supera lo pendiente en la orden %s (pendiente %s %s; '
                    'reservado en pre-etiquetas %s; +%s). Marque confirmación como responsable de fabricación.'
                )
                % (
                    self.name,
                    remaining,
                    self.product_uom_id.name,
                    pending,
                    additional_qty,
                )
            )
        if not self.env.user.has_group('kc_mrp_wizard.group_kc_mrp_wizard_manager'):
            raise UserError(
                _(
                    'Para autorizar el exceso sobre lo pendiente debe utilizarse un usuario con permisos de '
                    '«Responsable Asistente MRP».'
                )
            )

    def _kc_prelabel_bundle_qty_for_wo(self, workorder):
        """Cantidad por etiqueta según BOM, acotada a lo pendiente (igual tablet)."""
        self.ensure_one()
        batch_qty = workorder._tablet_get_batch_qty()
        rounding = self.product_uom_id.rounding
        remaining = workorder._tablet_normalize_production_qty(
            self._kc_prelabel_qty_remaining_to_make(),
        )
        if float_compare(remaining, 0, precision_rounding=rounding) <= 0:
            raise UserError(_('La orden ya no tiene cantidad pendiente por fabricar.'))
        if float_compare(batch_qty, remaining, precision_rounding=rounding) > 0:
            return remaining
        return batch_qty

    def action_kc_semi_tickets(self):
        self.ensure_one()
        return {
            'name': 'Tickets semiterminado',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.semi.ticket',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
            'context': {'default_production_id': self.id, 'search_default_production_id': self.id},
        }

    def action_kc_semi_stock_adjustment_wizard(self):
        self.ensure_one()
        return {
            'name': _('Salida / ajuste de semi'),
            'type': 'ir.actions.act_window',
            'res_model': 'kc.mrp.semi.stock.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
            },
        }

    def _kc_tablet_sanitize_ref_for_lot_name(self):
        """Parte central del nombre de lote: referencia MO legible sin caracteres conflictivos (GS1/etiquetas)."""
        self.ensure_one()
        base = (self.name or '').strip() or ('MO-%s' % self.id)
        s = base.replace('/', '-')
        s = re.sub(r'[^A-Za-z0-9._-]', '-', s)
        s = re.sub(r'-+', '-', s).strip('-')
        if not s:
            s = 'MO-%s' % self.id
        return s[:80]

    def _kc_tablet_mo_lot_numeric_ref(self):
        """Referencia numérica de la MO para el nombre compacto del lote (p. ej. PA/MO/01027 → 1027)."""
        self.ensure_one()
        name = (self.name or '').strip()
        chunks = re.findall(r'\d+', name)
        if chunks:
            num = chunks[-1]
        else:
            num = str(self.id)
        stripped = num.lstrip('0')
        return stripped or '0'

    def _kc_tablet_lot_name_prefix(self):
        """Prefijo de lote PT por compañía (asistente MRP). Por defecto «LT» si no está configurado."""
        self.ensure_one()
        return self.company_id.kc_tablet_lot_prefix()

    def _kc_tablet_format_lot_name(self, seq):
        """Nombre compacto: {prefijo}{número MO}-{secuencia} (p. ej. LT1031-6 o PA1031-6)."""
        self.ensure_one()
        return '%s%s-%d' % (
            self._kc_tablet_lot_name_prefix(),
            self._kc_tablet_mo_lot_numeric_ref(),
            seq,
        )

    def _kc_tablet_peek_next_lot_name(self):
        """Siguiente nombre de lote sin consumir el correlativo (solo vista previa)."""
        self.ensure_one()
        next_seq = (self.kc_tablet_lot_last_seq or 0) + 1
        return self._kc_tablet_format_lot_name(next_seq)

    def _kc_tablet_next_lot_name(self):
        """Genera el siguiente lote {prefijo}{MO}-{seq} con correlativo por orden (transaccional)."""
        self.ensure_one()
        self.env.cr.execute(
            'SELECT 1 FROM mrp_production WHERE id = %s FOR UPDATE',
            [self.id],
        )
        last = self.kc_tablet_lot_last_seq or 0
        next_seq = last + 1
        name = self._kc_tablet_format_lot_name(next_seq)
        self.write({'kc_tablet_lot_last_seq': next_seq})
        return name
