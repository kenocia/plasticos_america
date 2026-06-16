# -*- coding: utf-8 -*-

import logging
from contextlib import closing

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.tools.float_utils import float_is_zero
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        related='production_id.product_id',
        readonly=True,
    )
    qty_pending = fields.Float(
        string='Pendiente por producir',
        compute='_compute_qty_pending',
        digits=(16, 2),
    )
    batch_ticket_ids = fields.One2many(
        'mrp.batch.ticket',
        'workorder_id',
        string='Tickets de lote',
    )
    batch_ticket_count = fields.Integer(
        string='Lotes creados',
        compute='_compute_batch_ticket_count',
    )
    kc_semi_ticket_ids = fields.One2many(
        'mrp.semi.ticket',
        'workorder_id',
        string='Tickets semiterminado',
    )
    kc_semi_ticket_count = fields.Integer(
        string='Tickets semi',
        compute='_compute_kc_semi_ticket_count',
    )
    qty_semi_ticket_count = fields.Float(
        string='Semi-terminados (cantidad)',
        compute='_compute_qty_semi_ticket_count',
        digits='Product Unit of Measure',
    )
    kc_wc_creates_pt_lot = fields.Boolean(
        string='Centro genera lote PT (tablet)',
        related='workcenter_id.kc_tablet_creates_pt_lot',
    )
    kc_tablet_register_semi = fields.Boolean(
        string='Operación registra semi (tablet)',
        # operation_id -> línea de operación de la LdM (mrp.routing.workcenter), misma que en la pestaña Operaciones de la BOM
        related='operation_id.kc_tablet_register_semi',
        store=True,
        readonly=True,
    )
    production_reference = fields.Char(
        string='Referencia de la MO',
        related='production_id.name',
        readonly=True,
    )
    product_display_name = fields.Char(
        string='Nombre del producto',
        related='product_id.name',
        readonly=True,
    )
    product_default_code = fields.Char(
        string='Codigo de producto',
        related='product_id.default_code',
        readonly=True,
    )
    kc_tablet_kanban_default_code = fields.Char(
        string='Referencia interna (tablet resumen)',
        compute='_compute_kc_tablet_kanban_default_code',
        help='En operación que registra semi con producto semi en la LdM, la referencia interna de ese producto; '
             'en el resto de casos, la del producto fabricado de la orden.',
    )
    workcenter_name = fields.Char(
        string='Centro de trabajo',
        related='workcenter_id.name',
        readonly=True,
    )
    kc_tablet_session_employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado (sesión PIN)',
        compute='_compute_kc_tablet_session_employee',
        help='Empleado identificado con PIN en el contexto de la sesión tablet (tablet_employee_id).',
    )
    kc_tablet_kanban_uom_name = fields.Char(
        string='UdM resumen tablet',
        compute='_compute_kc_tablet_kanban_uom_name',
        help='UdM del producto terminado de la MO, salvo operación «Registra semiterminado»: entonces UdM del semi '
             '(producto semi o UdM declaración de la operación).',
    )
    kc_tablet_semi_operation_uom_name = fields.Char(
        string='UdM semi (operación LdM)',
        compute='_compute_kc_tablet_semi_operation_uom_name',
        help='Solo declaración semi: misma regla que la línea de operación — UdM del producto semi si existe, '
             'si no la «UdM declaración semi» (mrp.routing.workcenter).',
    )

    def _kc_tablet_semi_declaration_uom(self):
        """UdM de declaración semi según la operación de la LdM (alineado con el wizard de ticket semi)."""
        self.ensure_one()
        op = self.operation_id
        if not op or not op.kc_tablet_register_semi:
            return self.env['uom.uom']
        if op.kc_semi_product_id:
            return op.kc_semi_product_id.uom_id
        return op.kc_semi_uom_id

    @api.depends(
        'operation_id',
        'operation_id.kc_tablet_register_semi',
        'operation_id.kc_semi_product_id',
        'operation_id.kc_semi_product_id.uom_id',
        'operation_id.kc_semi_uom_id',
    )
    def _compute_kc_tablet_semi_operation_uom_name(self):
        for wo in self:
            uom = wo._kc_tablet_semi_declaration_uom()
            wo.kc_tablet_semi_operation_uom_name = uom.name if uom else ''

    @api.depends(
        'kc_tablet_register_semi',
        'operation_id',
        'operation_id.kc_semi_product_id',
        'operation_id.kc_semi_product_id.default_code',
        'product_id',
        'product_id.default_code',
    )
    def _compute_kc_tablet_kanban_default_code(self):
        for wo in self:
            if wo.kc_tablet_register_semi and wo.operation_id and wo.operation_id.kc_semi_product_id:
                wo.kc_tablet_kanban_default_code = wo.operation_id.kc_semi_product_id.default_code or ''
            else:
                wo.kc_tablet_kanban_default_code = wo.product_id.default_code or ''

    @api.depends(
        'kc_tablet_register_semi',
        'operation_id',
        'operation_id.kc_tablet_register_semi',
        'operation_id.kc_semi_product_id',
        'operation_id.kc_semi_product_id.uom_id',
        'operation_id.kc_semi_uom_id',
        'production_id.product_uom_id',
    )
    def _compute_kc_tablet_kanban_uom_name(self):
        for wo in self:
            if wo.kc_tablet_register_semi and wo.operation_id:
                uom = wo._kc_tablet_semi_declaration_uom()
                wo.kc_tablet_kanban_uom_name = uom.name if uom else (wo.production_id.product_uom_id.name or '')
            else:
                wo.kc_tablet_kanban_uom_name = wo.production_id.product_uom_id.name if wo.production_id else ''

    @api.depends_context('tablet_employee_id')
    def _compute_kc_tablet_session_employee(self):
        Employee = self.env['hr.employee']
        eid = self.env.context.get('tablet_employee_id')
        if not eid:
            for wo in self:
                wo.kc_tablet_session_employee_id = False
            return
        emp = Employee.browse(eid).exists()
        for wo in self:
            wo.kc_tablet_session_employee_id = emp

    @api.depends('production_id', 'production_id.product_qty', 'production_id.qty_produced')
    def _compute_qty_pending(self):
        for wo in self:
            if wo.production_id:
                wo.qty_pending = wo.production_id.product_qty - wo.production_id.qty_produced
            else:
                wo.qty_pending = 0.0

    @api.depends('batch_ticket_ids')
    def _compute_batch_ticket_count(self):
        for wo in self:
            wo.batch_ticket_count = len(wo.batch_ticket_ids)

    @api.depends('kc_semi_ticket_ids')
    def _compute_kc_semi_ticket_count(self):
        for wo in self:
            wo.kc_semi_ticket_count = len(wo.kc_semi_ticket_ids)

    @api.depends('kc_semi_ticket_ids.quantity')
    def _compute_qty_semi_ticket_count(self):
        for wo in self:
            wo.qty_semi_ticket_count = sum(wo.kc_semi_ticket_ids.mapped('quantity')) or 0.0

    # -------------------------------------------------------------------------
    # Helpers de sesión / PIN para vista tablet
    # -------------------------------------------------------------------------

    def _tablet_check_pin_timeout(self):
        """Devuelve una acción para revalidar PIN si la sesión caducó, o False si sigue válida.

        La caducidad se controla por centro de trabajo:
        - Si require_pin = False: nunca se pide PIN.
        - Si pin_timeout_minutes <= 0: PIN no caduca mientras dure la sesión.
        - Si han pasado más de pin_timeout_minutes desde tablet_last_pin_ts en el contexto:
          se redirige al menú de centros de trabajo para que el usuario se vuelva a identificar,
          iniciando una nueva raíz de trazabilidad sin acumular la anterior.
        """
        self.ensure_one()
        workcenter = self.workcenter_id
        if not workcenter or not workcenter.require_pin:
            return False
        timeout = workcenter.pin_timeout_minutes or 0
        if timeout <= 0:
            return False
        last_ts = self.env.context.get('tablet_last_pin_ts')
        if not last_ts:
            # Sin timestamp de PIN: forzar volver al menú tablet y reiniciar migas (OWL usa target main)
            action = self.env['ir.actions.act_window']._kc_tablet_action_workcenter_menu()
            action['target'] = 'main'
            return action
        try:
            last_dt = fields.Datetime.from_string(last_ts)
        except Exception:
            last_dt = fields.Datetime.now()
        now = fields.Datetime.now()
        elapsed = (now - last_dt).total_seconds()
        # pin_timeout_minutes del centro: caducidad por inactividad (RPC sin renovar tablet_last_pin_ts)
        if elapsed > timeout * 60:
            action = self.env['ir.actions.act_window']._kc_tablet_action_workcenter_menu()
            action['target'] = 'main'
            return action
        return False

    def action_tablet_exit_to_workcenters(self):
        """Vuelve a la lista de centros del asistente MRP (fin de sesión operativa en el centro).

        Al abrir de nuevo un centro con PIN, el empleado deberá identificarse otra vez. El temporizador
        de inactividad (``pin_timeout_minutes``) se basa en ``tablet_last_pin_ts``; al salir se limpia
        el contexto de sesión para no arrastrar datos obsoletos.
        """
        self.ensure_one()
        action = self.env['ir.actions.act_window']._kc_tablet_action_workcenter_menu()
        action['target'] = 'main'
        raw_ctx = action.get('context')
        if isinstance(raw_ctx, dict):
            ctx = dict(raw_ctx)
        elif isinstance(raw_ctx, str):
            parsed_ctx = safe_eval(raw_ctx, {'uid': self.env.uid})
            ctx = parsed_ctx if isinstance(parsed_ctx, dict) else {}
        else:
            ctx = {}
        for key in ('tablet_last_pin_ts', 'tablet_employee_id', 'tablet_workcenter_id'):
            ctx.pop(key, None)
        action['context'] = ctx
        return action

    def _tablet_context_with_refreshed_pin_ts(self):
        """Contexto para sesión tablet con timestamp de PIN actualizado (reinicia contador de inactividad)."""
        ctx = dict(self.env.context or {})
        ctx['tablet_last_pin_ts'] = fields.Datetime.now()
        return ctx

    def _tablet_return_with_refreshed_pin(self, result):
        """Si la acción devuelve una ventana (act_window), inyecta contexto con PIN actualizado.
        Si no devuelve ventana (None/True), devuelve el resultado sin reabrir el kanban para no alargar la ruta de navegación."""
        ctx = self._tablet_context_with_refreshed_pin_ts()
        if result and isinstance(result, dict) and result.get('type') == 'ir.actions.act_window':
            result = dict(result)
            result.setdefault('context', {})
            if isinstance(result['context'], dict):
                result['context'] = dict(result['context'])
            else:
                result['context'] = {}
            result['context'].update(ctx)
            # Odoo 18 web: `doAction` / `_preprocessAction` exige `views` (no basta `view_mode` solo).
            if not result.get('views'):
                view_mode = (result.get('view_mode') or 'form').split(',')[0]
                vid = result.get('view_id')
                if isinstance(vid, int):
                    result['views'] = [(vid, view_mode)]
                else:
                    result['views'] = [(False, view_mode)]
            return result
        return result

    def _tablet_action_return_kanban_single_wo(self, workcenter=None):
        """Vuelve al kanban tablet filtrado a esta orden de trabajo (tablero de un solo card).

        ``target: main`` evita al refrescar (F5) que la ruta muestre otro centro en la migaja
        heredada del kanban de centros; el cliente limpia la pila de acciones al cargar esta ventana.
        """
        self.ensure_one()
        workcenter = workcenter or self.workcenter_id
        context = self._tablet_context_with_refreshed_pin_ts()
        if workcenter and not context.get('tablet_workcenter_id'):
            context['tablet_workcenter_id'] = workcenter.id
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'name': _('Asistente MRP — %s') % (workcenter.name or self.name),
            'res_model': 'mrp.workorder',
            'view_mode': 'kanban',
            'view_id': self.env.ref('kc_mrp_wizard.mrp_workorder_kanban_tablet').id,
            'domain': [('id', '=', self.id)],
            'target': 'main',
            'context': context,
        })

    def _tablet_validate_session(self):
        """Valida sesión tablet (PIN y empleado autorizado en el centro de trabajo).

        :return: tupla (action, employee_id, employee, workcenter).
            - Si hay que redirigir (p. ej. PIN caducado): (acción_dict, None, None, None).
            - Si la sesión es válida: (None, employee_id, employee, workcenter).
        """
        self.ensure_one()
        action = self._tablet_check_pin_timeout()
        if action:
            return (action, None, None, None)
        employee_id = self.env.context.get('tablet_employee_id')
        if not employee_id:
            raise UserError(_('Sesión tablet no válida. Vuelva a identificar con PIN.'))
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            raise UserError(_('Empleado no encontrado.'))
        workcenter = self.workcenter_id
        if workcenter.employee_ids and employee not in workcenter.employee_ids:
            raise UserError(_('Empleado no autorizado para este centro.'))
        return (None, employee_id, employee, workcenter)

    def _tablet_assert_employee_permission(self, employee, permission_field, action_label):
        """Valida permiso del empleado para ejecutar una acción del tablero tablet."""
        self.ensure_one()
        if not employee:
            raise UserError(_('Sesión tablet no válida. Vuelva a identificar con PIN.'))
        if not getattr(employee, permission_field, False):
            raise UserError(_(
                'El empleado "%s" no tiene permiso para "%s" en el asistente tablet.'
            ) % (employee.display_name, action_label))

    def _tablet_sudo(self):
        """Entorno elevado para mutaciones inventario/MRP tras validar sesión tablet.

        El operador solo lleva el grupo KenoCia; las escrituras en modelos estándar
        (stock.move, scrap, picking, etc.) se ejecutan aquí, no vía ACL de inventario/MRP.
        """
        return self.sudo()

    def _tablet_assert_mo_finished_product_lot_tracked(self):
        """El asistente de producción solo aplica a MO cuyo producto fabricado tenga trazabilidad 'Por lotes'."""
        self.ensure_one()
        product = self.production_id.product_id
        if not product or product.tracking != 'lot':
            raise UserError(
                _(
                    'No puede usarse el asistente con esta orden: el producto a fabricar debe tener en inventario la '
                    'trazabilidad «Por lotes» (no «Por cantidad» ni «Por número de serie»).\n\n'
                    'Producto: %s\n'
                )
                % (product.display_name if product else _('-'),)
            )

    def _tablet_assert_authorized_pt_lot_workcenter(self):
        """Solo operaciones de la LdM marcadas vía su centro «oficial» y centros físicos con flag pueden PT/pre-etiqueta.

        La LdM identifica *qué* operación genera lote (línea cuyo centro por defecto tiene «Genera lote de PT»).
        La OT puede ejecutarse en otro centro físico (p. ej. urgencia) si ese centro también tiene el flag:
        se valida ``operation_id`` frente a la LdM, no la igualdad estricta ``workcenter_id`` con el de la lista.
        """
        self.ensure_one()
        if not self.workcenter_id.kc_tablet_creates_pt_lot:
            raise UserError(_(
                'Este centro de trabajo no está autorizado a crear lote de producto terminado desde el tablet. '
                'Activa "Genera lote de PT (tablet)" en el centro físico donde se ejecuta esta orden de trabajo.'
            ))
        mo = self.production_id
        bom = mo.bom_id
        if bom and bom.operation_ids:
            flagged_wc = bom.operation_ids.workcenter_id.filtered('kc_tablet_creates_pt_lot')
            if not flagged_wc:
                raise UserError(_(
                    'En la pestaña "Operaciones" de la lista de materiales "%s" debe existir un centro con "Genera lote de PT (tablet)".',
                ) % (bom.display_name,))
            # if len(flagged_wc) != 1:
            #     raise UserError(_(
            #         'Solo un centro de la ruta puede tener "Genera lote de PT (tablet)". Revisa la lista de materiales %s.',
            #     ) % (bom.display_name,))
            tablet_op_lines = bom.operation_ids.filtered(lambda o: o.workcenter_id.kc_tablet_creates_pt_lot)
            if self.operation_id not in tablet_op_lines:
                op_names = ', '.join(tablet_op_lines.mapped('display_name'))
                raise UserError(_(
                    'Solo la(s) operación(es) "%s" de la lista de materiales puede crear lote de PT o pre-etiquetas. '
                    'Esta orden de trabajo es "%s" (centro "%s"). Cambie el centro en la misma línea de operación '
                    'o use la orden de trabajo que corresponda a esa operación en la LdM.',
                ) % (op_names, self.operation_id.name or self.name, self.workcenter_id.display_name))

    @api.model
    def kc_resolve_workorder_for_prelabel_consume(self, lot, workcenter):
        """OT en progreso en ``workcenter`` para la MO de la pre-etiqueta (registro supervisor / primer escaneo)."""
        lot.ensure_one()
        workcenter.ensure_one()
        mo = lot.kc_prelabel_production_id
        if not mo:
            raise UserError(
                _('La pre-etiqueta «%s» no está vinculada a una orden de fabricación.') % lot.name
            )
        if mo.state in ('done', 'cancel'):
            raise UserError(
                _('La orden de fabricación %s está en estado «%s»; no se pueden registrar pre-etiquetas.')
                % (mo.name, dict(mo._fields['state'].selection).get(mo.state, mo.state))
            )
        candidates = mo.workorder_ids.filtered(
            lambda w: w.workcenter_id == workcenter and w.state == 'progress'
        )
        if len(candidates) > 1:
            raise UserError(
                _('Hay más de una orden de trabajo en progreso en el centro «%s» para la orden %s. '
                  'Cierre o termine las OT duplicadas antes de escanear.')
                % (workcenter.display_name, mo.name)
            )
        if not candidates:
            bom = mo.bom_id
            fallback = self.env['mrp.workorder']
            if bom:
                tablet_ops = bom.operation_ids.filtered(
                    lambda o: o.workcenter_id.kc_tablet_creates_pt_lot
                )
                if len(tablet_ops) == 1:
                    fallback = mo.workorder_ids.filtered(
                        lambda w: w.operation_id == tablet_ops[0] and w.state == 'progress'
                    )
            if len(fallback) == 1 and fallback.workcenter_id == workcenter:
                candidates = fallback
        if len(candidates) != 1:
            raise UserError(
                _('No hay una orden de trabajo en progreso en el centro «%s» para la orden %s. '
                  'Inicie la OT correspondiente (etiquetado / lote PT) antes de registrar pre-etiquetas.')
                % (workcenter.display_name, mo.name)
            )
        wo = candidates[0]
        wo._tablet_assert_mo_finished_product_lot_tracked()
        wo._tablet_assert_authorized_pt_lot_workcenter()
        return wo

    def kc_consume_prelabel_lots(self, lots, employee=None):
        """Registra producción de varias pre-etiquetas pendientes (sin sesión PIN tablet).

        Cada lote llama a ``_tablet_create_batch_lot_impl`` con ``lot.kc_prelabel_qty``;
        el consumo de resina/MP usa la misma regla que «Crear lote» y «Producción manual``.
        """
        self.ensure_one()
        if self.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de registrar pre-etiquetas.'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()
        mo = self.production_id
        employee = employee or self.env.user.employee_id
        if not employee:
            raise UserError(
                _('Indique un empleado en el asistente o vincule un empleado al usuario %s.')
                % self.env.user.display_name
            )
        workcenter = self.workcenter_id
        lots = lots.filtered(lambda l: l.kc_prelabel_state == 'pending')
        if not lots:
            raise UserError(_('No hay pre-etiquetas pendientes que registrar.'))
        rounding = mo.product_uom_id.rounding
        remaining = mo.product_qty - mo.qty_produced
        total_qty = sum(lots.mapped('kc_prelabel_qty'))
        if float_compare(total_qty, remaining, precision_rounding=rounding) > 0:
            raise UserError(
                _('La suma de las pre-etiquetas (%s %s) supera lo pendiente por producir en la orden (%s %s).')
                % (total_qty, mo.product_uom_id.name, remaining, mo.product_uom_id.name)
            )
        for lot in lots:
            if lot.kc_prelabel_production_id != mo:
                raise UserError(
                    _('La pre-etiqueta «%s» no pertenece a la orden de fabricación %s.') % (lot.name, mo.name)
                )
            if lot.product_id != mo.product_id:
                raise UserError(
                    _('La pre-etiqueta «%s» no corresponde al producto de esta orden.') % lot.name
                )
        res = None
        for lot in lots.sorted(key=lambda l: (l.id,)):
            res = self._tablet_create_batch_lot_impl(
                lot.kc_prelabel_qty,
                employee,
                workcenter,
                lot=lot,
                is_bad_quality=False,
                skip_post_production_print=True,
            )
        return res

    def _kc_tablet_try_print_gs1_label_network(self, lot):
        """Etiqueta de lote GS1/ZPL por impresora de red configurada en el centro (ZD421 RAW 9100)."""
        self.ensure_one()
        if not lot:
            return False
        printer = self.workcenter_id.kc_label_network_printer_id
        if not printer:
            return False
        res = lot.kc_send_lot_label_to_network_printer(printer, workcenter=self.workcenter_id)
        if not res.get('success'):
            _logger.warning(
                'KC tablet: fallo etiqueta lote WO=%s lote=%s: %s',
                self.id, lot.id, res.get('error'),
            )
        return bool(res.get('success'))

    def _tablet_filter_consume_raw_moves(self, raw_moves, consume_move_ids=None):
        """Restringe movimientos de MP cuando el consumo es selectivo (producción manual)."""
        if consume_move_ids is None:
            return raw_moves
        return raw_moves.filtered(lambda m: m.id in consume_move_ids)

    def _tablet_create_batch_lot_impl(
        self,
        qty_to_produce,
        employee,
        workcenter,
        lot=None,
        is_bad_quality=False,
        skip_post_production_print=False,
        consume_move_ids=None,
        allow_create_lot=True,
    ):
        """Lógica común: crea/usa lote PT, valida MP, consumo LdM, ticket e impresión.

        Solo estos flujos tablet deben validar y consumir componentes (misma cadena previa
        a grabar PT): stock + lotes FIFO + prueba savepoint si aplica.

        - **Crear lote PT:** todos los MP con saldo; cantidad = lote sugerido (``bom.product_qty``).
        - **Producción pre-etiqueta** (``kc_consume_prelabel_lots``): todos los MP; cantidad =
          ``lot.kc_prelabel_qty``; lote pendiente ya impreso.
        - **Producción manual** (cantidad): todos los MP; cantidad = asistente; lote opcional.
        - **Producción componentes:** solo ``consume_move_ids``; cantidad = asistente; lote obligatorio.

        No aplica aquí: imprimir pre-etiquetas (sin consumo), semi, merma (validación propia).

        Consumo MP: proporcional al pendiente de la MO (``qty_to_produce / pendiente_MO`` × saldo del movimiento).
        Pre-etiqueta / crear lote: cantidad = fardo LdM (``bom.product_qty``) salvo último tramo.

        :param qty_to_produce: cantidad a producir en el lote.
        :param employee: registro hr.employee.
        :param workcenter: registro mrp.workcenter.
        :param lot: stock.lot existente o None para crear uno nuevo.
        :param is_bad_quality: si True, el ticket se marca como mala calidad.
        :param skip_post_production_print: si True, no reimprime viñeta ni etiqueta GS1 (p. ej. pre-etiqueta ya impresa).
        :param consume_move_ids: ids de ``stock.move`` a consumir; None = todos los de la LdM.
        :param allow_create_lot: si False, ``lot`` es obligatorio (producción manual selectiva).
        :return: acción para volver al kanban tablet (o para cerrar wizard).
        """
        self.ensure_one()
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()

        mo = self.production_id
        qty_to_produce = self._tablet_normalize_production_qty(qty_to_produce)

        rounding = mo.product_uom_id.rounding
        if qty_to_produce <= 0:
            raise UserError(_('La cantidad a producir debe ser mayor que cero.'))
        remaining = mo.product_qty - mo.qty_produced
        if float_compare(qty_to_produce, remaining, precision_rounding=rounding) > 0:
            raise UserError(
                _('La cantidad (%s) no puede ser mayor que lo pendiente por producir (%s).')
                % (qty_to_produce, remaining)
            )
        if not allow_create_lot and not lot:
            raise UserError(_('Debe indicar un lote existente de la orden de fabricación.'))
        consumed_prelabel_pending = False
        if lot:
            if lot.kc_prelabel_state == 'pending':
                if is_bad_quality:
                    raise UserError(_(
                        'No puede usarse una pre-etiqueta pendiente como lote de mala calidad.'
                    ))
                if lot.kc_prelabel_production_id != mo:
                    raise UserError(_('Esta pre-etiqueta está reservada para otra orden de fabricación.'))
                if lot.product_id != mo.product_id:
                    raise UserError(_('La pre-etiqueta no corresponde al producto de esta orden.'))
                if float_compare(qty_to_produce, lot.kc_prelabel_qty, precision_rounding=rounding) != 0:
                    raise UserError(
                        _('La cantidad a producir debe coincidir con la impresa en la pre-etiqueta (%s %s).')
                        % (lot.kc_prelabel_qty, mo.product_uom_id.name)
                    )
                consumed_prelabel_pending = True
        self.env.cr.execute('SELECT 1 FROM mrp_workorder WHERE id = %s FOR UPDATE', [self.id])
        mo.invalidate_recordset(['qty_produced'])
        self._tablet_assert_has_raw_to_consume()
        raw_to_update = self._tablet_raw_moves_with_remaining_consumption()
        raw_to_update.invalidate_recordset(['unit_factor'])
        raw_for_consumption = self._tablet_filter_consume_raw_moves(
            raw_to_update, consume_move_ids,
        )
        if consume_move_ids is not None and not raw_for_consumption:
            raise UserError(_('No hay componentes válidos seleccionados para consumir.'))
        # Tras validaciones de negocio: reserva/consumo/PT con privilegios elevados (sin grupo stock/MRP).
        self = self._tablet_sudo()
        mo = self.production_id
        raw_for_consumption = raw_for_consumption.sudo()
        if lot:
            lot = lot.sudo()
        self._tablet_prepare_moves_for_tablet_consumption(raw_for_consumption)
        raw_for_consumption.filtered(lambda m: m.state not in ('done', 'cancel'))._action_assign()
        self._tablet_assert_raw_stock_for_batch(raw_for_consumption, qty_to_produce)
        self._tablet_reserve_lots_for_raw_consumption(raw_for_consumption, qty_to_produce)
        with closing(self.env.cr.savepoint()):
            self._tablet_set_raw_consumption(raw_for_consumption, qty_to_produce)
        if not lot:
            lot_name = mo._kc_tablet_next_lot_name()
            lot_vals = {
                'product_id': mo.product_id.id,
                'company_id': mo.company_id.id,
                'name': lot_name,
                'kc_prelabel_production_id': mo.id,
            }
            if is_bad_quality and 'low_quality' in self.env['stock.lot']._fields:
                lot_vals['low_quality'] = True
            if 'kc_employee_id' in self.env['stock.lot']._fields:
                lot_vals['kc_employee_id'] = employee.id
            lot = self.env['stock.lot'].create(lot_vals)
            _logger.info('Tablet batch: created lot id=%s name=%s', lot.id, lot.name)
        elif not lot.exists():
            raise UserError(_('El lote indicado ya no existe en el sistema.'))
        if is_bad_quality and 'low_quality' in self.env['stock.lot']._fields:
            lot.write({'low_quality': True})
        if 'kc_employee_id' in self.env['stock.lot']._fields and not consumed_prelabel_pending:
            lot.write({'kc_employee_id': employee.id})
        mo.write({
            'lot_producing_id': lot.id,
            'qty_producing': mo.qty_produced + qty_to_produce,
        })
        # No llamar _set_qty_producing: usa unit_factor y puede chocar con el consumo
        # proporcional de la LdM y con el redondeo de la UdM (p. ej. resina en kg).
        self._tablet_set_raw_consumption(raw_for_consumption, qty_to_produce)
        finish_move = mo.move_finished_ids.filtered(
            lambda m: m.product_id == mo.product_id and m.state not in ('done', 'cancel')
        )
        if not finish_move:
            raise UserError(_('No se encontró el movimiento de producto terminado.'))
        finish_move = finish_move[0]
        qty_produced_before = mo.qty_produced
        raw_moves = raw_for_consumption
        raw_moves.picked = True
        # Mismo orden que _post_inventory de la MO: consumos primero, PT después.
        raw_moves.with_context(skip_mo_check=True)._action_done(cancel_backorder=False)
        self._ensure_finished_move_line_has_lot(finish_move, lot, qty_to_produce)
        if finish_move.product_id.tracking == 'none':
            finish_move._set_quantity_done(qty_to_produce)
        finish_move.picked = True
        finish_move.with_context(skip_mo_check=True)._action_done(cancel_backorder=False)
        mo.invalidate_recordset(['qty_produced', 'move_finished_ids'])
        if float_compare(
            mo.qty_produced,
            qty_produced_before + qty_to_produce,
            precision_rounding=mo.product_uom_id.rounding,
        ) != 0:
            raise UserError(_(
                'No se registró en inventario la cantidad esperada de producto terminado para este lote.\n'
                'Espere %(exp)s %(uom)s y el sistema tiene %(got)s %(uom)s.\n'
                'Revise componentes, ubicaciones y trazabilidad del PT.'
            ) % {
                'exp': qty_to_produce,
                'got': mo.qty_produced - qty_produced_before,
                'uom': mo.product_uom_id.name,
            })
        new_qty_produced = self.qty_produced + qty_to_produce
        self.with_context(bypass_duration_calculation=True).write({
            'qty_produced': new_qty_produced,
        })
        self.invalidate_recordset(['qty_remaining'])
        mo.write({
            'qty_producing': 0.0,
            'lot_producing_id': False,
        })
        mo.invalidate_recordset(['qty_produced'])
        # Odoo puede poner la MO en «Hecho» solo por movimientos cerrados sin cerrar OT; al completar cantidad cerramos OT abiertas.
        if float_compare(mo.qty_produced, mo.product_qty, precision_rounding=mo.product_uom_id.rounding) >= 0:
            open_wos = mo.workorder_ids.filtered(lambda w: w.state not in ('done', 'cancel'))
            if open_wos:
                open_wos.button_finish()
        ticket = self.env['mrp.batch.ticket'].create({
            'production_id': mo.id,
            'workorder_id': self.id,
            'workcenter_id': workcenter.id,
            'product_id': mo.product_id.id,
            'lot_id': lot.id,
            'qty': qty_to_produce,
            'employee_id': employee.id,
            'is_bad_quality': is_bad_quality,
            'company_id': mo.company_id.id,
        })
        if not skip_post_production_print:
            ticket.write({'printed_at': fields.Datetime.now(), 'print_count': 1})
            try:
                ticket._report_print()
            except Exception:
                pass
            self._kc_tablet_try_print_gs1_label_network(lot)
        else:
            _logger.info(
                'KC tablet: ticket lote id=%s sin reimpresión (pre-etiqueta / etiqueta ya emitida).',
                ticket.id,
            )
        if consumed_prelabel_pending:
            lot.write({'kc_prelabel_state': 'produced'})
        return self._tablet_action_return_kanban_single_wo(workcenter)

    def _ensure_finished_move_line_has_lot(self, move, lot, qty):
        """Asegura que el movimiento de PT tenga una move_line con lot_id (productos con tracking)."""
        if move.product_id.tracking == 'none':
            return
        # Actualizar o crear move_line con el lote (sobrescribir lot_id si la línea venía del backorder con lote anterior)
        lines = move.move_line_ids.filtered(lambda ml: ml.product_id == move.product_id)
        if lines:
            ml = lines[0]
            _logger.debug(
                'Tablet batch: move_line id=%s lot_id=%s (antes) -> lot_id=%s (nuevo) qty=%s',
                ml.id, ml.lot_id.id if ml.lot_id else None, lot.id, qty,
            )
            ml.lot_id = lot
            ml.quantity = qty
        else:
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': move.product_id.id,
                'product_uom_id': move.product_uom.id,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'quantity': qty,
                'lot_id': lot.id,
            })

    def _tablet_ensure_planning_dates_before_start(self):
        """Completa fechas si la OT quedó planificada (leave_id) sin inicio/fin.

        Odoo estándar lanza «No es posible anular la planeación de una sola orden…»
        al escribir en una OT con leave_id y date_start o date_finished vacíos (no es
        un bloqueo real de «anular planificación» desde tablet).
        """
        self.ensure_one()
        if not self.leave_id:
            return
        if self.date_start and self.date_finished:
            return
        date_start = self.date_start or fields.Datetime.now()
        date_finished = self.date_finished or self._calculate_date_finished(date_start)
        self.write({
            'date_start': date_start,
            'date_finished': date_finished,
            })

    def action_tablet_start(self):
        """Inicia la orden de trabajo desde la tablet (registra fecha/hora y tiempo)."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_start', _('Iniciar orden'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        # Validar que no haya alertas o solicitudes de mantenimiento abiertas que bloqueen el inicio
        self._tablet_check_blocking_alerts()
        if self.state not in ('ready', 'waiting'):
            raise UserError(_('Solo se puede iniciar una orden en estado Listo o Esperando componentes.'))
        self._tablet_ensure_planning_dates_before_start()
        result = self._tablet_sudo().button_start(raise_on_invalid_state=False)
        self._tablet_notify_material_scrap_reminder()
        return self._tablet_return_with_refreshed_pin(result)

    def _tablet_check_blocking_alerts(self):
        """Si el centro lo requiere, bloquea el inicio si hay alertas/solicitudes abiertas por paro.

        - Alertas de calidad: quality.alert con workcenter_id = centro, by_stop_production = True
          y etapa no finalizada (stage_id.done = False).
        - Solicitudes de mantenimiento: maintenance.request con workcenter_id = centro,
          by_stop_production = True y etapa no finalizada.
        """
        self.ensure_one()
        workcenter = self.workcenter_id
        if not workcenter:
            return
        # Alertas de calidad pendientes
        if workcenter.validate_alert_quality:
            alert = self.env['quality.alert'].search([
                ('workcenter_id', '=', workcenter.id),
                ('by_stop_production', '=', True),
                ('stage_id.done', '=', False),
            ], limit=1)
            if alert:
                raise UserError(_(
                    'No se puede iniciar la orden porque existe al menos una alerta de calidad abierta '
                    'por paro de producción en el centro "%s".'  + '\n' + 'Cierre primero la alerta "%s".'
                ) % (workcenter.display_name, alert.display_name))
        # Solicitudes de mantenimiento pendientes
        if workcenter.validate_alert_maintenance:
            request = self.env['maintenance.request'].search([
                ('workcenter_id', '=', workcenter.id),
                ('by_stop_production', '=', True),
                ('stage_id.done', '=', False),
            ], limit=1)
            if request:
                raise UserError(_(
                    'No se puede iniciar la orden porque existe al menos una solicitud de mantenimiento abierta '
                    'por paro de producción en el centro "%s".'  + '\n' + 'Cierre primero la solicitud "%s".'
                ) % (workcenter.display_name, request.display_name))

    def action_tablet_open_single_board(self):
        """Abre el tablero tablet filtrado solo a esta orden."""
        self.ensure_one()
        self._tablet_assert_mo_finished_product_lot_tracked()
        workcenter = self.workcenter_id
        context = self._tablet_context_with_refreshed_pin_ts()
        if workcenter and not context.get('tablet_workcenter_id'):
            context['tablet_workcenter_id'] = workcenter.id
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'name': _('Asistente MRP — %s') % (workcenter.name or self.name),
            'res_model': 'mrp.workorder',
            'view_mode': 'kanban',
            'view_id': self.env.ref('kc_mrp_wizard.mrp_workorder_kanban_tablet').id,
            'domain': [('id', '=', self.id)],
            'target': 'main',
            'context': context,
        })

    def _tablet_sync_mo_qty_produced(self):
        """Fuerza recálculo de qty_produced en la orden de fabricación tras cerrar la WO."""
        productions = self.mapped('production_id').filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        if productions:
            productions.invalidate_recordset(['qty_produced'])

    def action_finish(self):
        """Marca la orden de trabajo como hecha. Delega al método estándar y sincroniza MO."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_finish', _('Finalizar orden'))
        method = (
            getattr(self, 'action_mark_as_done', None)
            or getattr(self, 'button_finish', None)
            or getattr(self, 'button_done', None)
        )
        if not callable(method):
            raise UserError(_('No se pudo marcar como hecho en esta versión de Odoo.'))
        result = method()
        self._tablet_sync_mo_qty_produced()
        refreshed = self._tablet_return_with_refreshed_pin(result)
        if isinstance(refreshed, dict) and refreshed.get('type') == 'ir.actions.act_window':
            return refreshed
        return self._tablet_action_return_kanban_single_wo(self.workcenter_id)

    def button_pending(self):
        """Sobrescribe el estándar: además de cerrar la línea de productividad, pone la WO en 'ready'.
        Así, al pausar desde el asistente MRP o desde la lista estándar, al refrescar se muestra solo Iniciar."""
        super().button_pending()
        in_progress = self.filtered(lambda wo: wo.state == 'progress')
        if in_progress:
            in_progress.with_context(bypass_duration_calculation=True).write({'state': 'ready'})

    def _tablet_normalize_production_qty(self, qty):
        """Cantidad de PT alineada al redondeo de la UdM del producto fabricado."""
        self.ensure_one()
        rounding = self.production_id.product_uom_id.rounding
        return float_round(qty or 0.0, precision_rounding=rounding, rounding_method='HALF-UP')

    def _tablet_mo_pending_qty(self):
        """Cantidad PT pendiente de registrar en la MO (UdM de la orden)."""
        self.ensure_one()
        mo = self.production_id
        return self._tablet_normalize_production_qty(mo.product_qty - mo.qty_produced)

    def _tablet_get_batch_qty(self):
        """Cantidad por lote = cantidad base de la LdM (``mrp.bom.product_qty``), en UdM de la MO."""
        self.ensure_one()
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        if not mo.bom_id or mo.bom_id.product_qty <= 0:
            raise UserError(_(
                'La orden %s no tiene lista de materiales con cantidad base (> 0).\n'
                'Configure la LdM: el campo «Cantidad» es el tamaño del fardo (p. ej. 600), '
                'no la cantidad total de la orden (p. ej. 12000).'
            ) % mo.name)
        bom = mo.bom_id
        qty = mo.product_uom_id._compute_quantity(
            bom.product_qty,
            bom.product_uom_id,
                rounding_method='HALF-UP',
            )
        qty = self._tablet_normalize_production_qty(qty)
        if float_compare(qty, mo.product_qty, precision_rounding=rounding) >= 0:
            raise UserError(_(
                'La cantidad base de la lista de materiales (%(bom)s %(buom)s) es mayor o igual '
                'que la cantidad de la orden (%(mo)s %(muom)s).\n'
                'Cada «Crear lote» o pre-etiqueta consumiría toda la orden de una vez.\n\n'
                'En la LdM «%(bom_name)s», el campo «Cantidad» debe ser el fardo '
                '(p. ej. 600), no el total planificado de la OF.'
            ) % {
                'bom': bom.product_qty,
                'buom': bom.product_uom_id.name,
                'mo': mo.product_qty,
                'muom': mo.product_uom_id.name,
                'bom_name': bom.display_name,
            })
        return qty

    def _tablet_suggested_batch_lot_qty(self):
        """Cantidad sugerida para un lote PT: LdM base, sin superar lo pendiente de la MO."""
        self.ensure_one()
        rounding = self.production_id.product_uom_id.rounding
        remaining = self._tablet_mo_pending_qty()
        if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
            return 0.0
        batch_qty = self._tablet_get_batch_qty()
        if float_compare(batch_qty, remaining, precision_rounding=rounding) > 0:
            return remaining
        return batch_qty

    def _tablet_count_batches_for_qty(self, qty, batch_qty=None):
        """Número de lotes PT de tamaño ``batch_qty`` para cubrir ``qty`` (redondeo UdM MO)."""
        self.ensure_one()
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        qty = self._tablet_normalize_production_qty(qty)
        batch_qty = batch_qty or self._tablet_get_batch_qty()
        if float_compare(qty, 0.0, precision_rounding=rounding) <= 0:
            return 0
        if float_compare(batch_qty, 0.0, precision_rounding=rounding) <= 0:
            return 0
        count = 0
        left = qty
        while float_compare(left, 0.0, precision_rounding=rounding) > 0:
            count += 1
            piece = batch_qty
            if float_compare(piece, left, precision_rounding=rounding) > 0:
                piece = left
            left = self._tablet_normalize_production_qty(left - piece)
        return count

    def _tablet_raw_move_remaining_qty(self, move):
        """Demanda pendiente del movimiento abierto (UdM del movimiento).

        No usa ``product_uom_qty - _quantity_sml()``: en movimientos abiertos,
        ``_quantity_sml()`` suma las líneas de operación **reservadas** y validadas.
        Con 144 kg reservados y 0 consumidos, eso daba saldo 0 y el tablet bloqueaba
        aunque la MP solo estuviera reservada, no en estado Hecho.
        Tras un consumo parcial, Odoo parte el movimiento; la demanda restante queda
        en la línea hija abierta (``product_uom_qty``).
        """
        move.ensure_one()
        if move.state in ('done', 'cancel'):
            return 0.0
        return move.product_uom_qty

    def _tablet_candidate_raw_moves(self):
        """Movimientos MP de la MO (incluye líneas partidas tras consumo parcial)."""
        self.ensure_one()
        mo = self.production_id
        moves = mo.all_move_raw_ids.filtered(lambda m: not m.scrapped)
        if self.move_raw_ids:
            moves |= self.move_raw_ids.filtered(lambda m: not m.scrapped)
        return moves

    def _tablet_assert_has_raw_to_consume(self):
        """Bloquea crear lote si no hay MP pendiente; mensaje según estado real de la OF."""
        self.ensure_one()
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        pending_pt = self._tablet_mo_pending_qty()
        if float_compare(pending_pt, 0.0, precision_rounding=rounding) <= 0:
            raise UserError(_(
                'La orden %(mo)s ya no tiene producto terminado pendiente por registrar '
                '(%(produced)s de %(qty)s %(uom)s).'
            ) % {
                'mo': mo.name,
                'produced': mo.qty_produced,
                'qty': mo.product_qty,
                'uom': mo.product_uom_id.name,
            })
        raw_moves = self._tablet_candidate_raw_moves()
        open_moves = raw_moves.filtered(lambda m: m.state not in ('done', 'cancel'))
        with_remaining = self._tablet_raw_moves_with_remaining_consumption()
        if with_remaining:
            return
        if open_moves:
            raise UserError(_(
                'Hay líneas de materia prima abiertas en %(mo)s pero ninguna encaja con la LdM '
                'o no tienen demanda (revise productos y cantidades en Componentes).'
            ) % {'mo': mo.name})
        done_moves = raw_moves.filtered(lambda m: m.state == 'done')
        if not open_moves and done_moves:
            sample = []
            for move in done_moves[:3]:
                sample.append(
                    '%(product)s: %(qty)s %(uom)s (consumido)'
                    % {
                        'product': move.product_id.display_name,
                        'qty': move.product_uom_qty,
                        'uom': move.product_uom.name,
                    }
                )
            detail = '\n'.join(sample)
            if len(done_moves) > 3:
                detail += _('\n… y %(n)s componente(s) más.') % {'n': len(done_moves) - 3}
            raise UserError(_(
                'No quedan componentes por consumir en la orden %(mo)s.\n\n'
                'Pendiente por producir (PT): %(pending)s %(uom)s\n'
                'Todas las líneas de materia prima están en estado «Hecho» (consumo validado).\n'
                '%(detail)s\n\n'
                'Suele ocurrir si un registro anterior consumió toda la MP de la orden de una vez '
                '(p. ej. 144 kg de resina y 20 bolsas = total para 12 000 uds con LdM de 600), '
                'aunque solo se haya registrado un lote de PT.\n\n'
                'Revise la pestaña Componentes y el historial de movimientos. '
                'Para seguir fabricando hace falta una orden nueva o corrección por administración.'
            ) % {
                'mo': mo.name,
                'pending': pending_pt,
                'uom': mo.product_uom_id.name,
                'detail': detail,
            })
        raise UserError(_(
            'No quedan componentes por consumir en la orden %(mo)s '
            '(sin movimientos abiertos o sin saldo en componentes).\n'
            'Pendiente PT: %(pending)s %(uom)s. Revise la pestaña Componentes.'
        ) % {
            'mo': mo.name,
            'pending': pending_pt,
            'uom': mo.product_uom_id.name,
        })

    def _tablet_raw_moves_with_remaining_consumption(self):
        """Movimientos de MP abiertos con saldo LdM, uno por producto (evita duplicados en la MO).

        No usa ``manual_consumption``: el tablet calcula cantidades; ese flag solo bloqueaba
        el consumo tras el primer registro parcial.
        """
        self.ensure_one()
        mo = self.production_id
        bom = mo.bom_id
        raw_moves = self._tablet_candidate_raw_moves().filtered(
            lambda m: m.state not in ('done', 'cancel'),
        )
        bom_products = bom.bom_line_ids.product_id if bom else self.env['product.product']
        by_product = {}
        for move in raw_moves:
            if bom and not move.bom_line_id and move.product_id not in bom_products:
                continue
            remaining = self._tablet_raw_move_remaining_qty(move)
            if float_compare(remaining, 0, precision_rounding=move.product_uom.rounding) <= 0:
                continue
            prev = by_product.get(move.product_id.id)
            if not prev:
                by_product[move.product_id.id] = move
                continue
            prev_rem = self._tablet_raw_move_remaining_qty(prev)
            if float_compare(remaining, prev_rem, precision_rounding=move.product_uom.rounding) > 0:
                by_product[move.product_id.id] = move
            elif float_compare(remaining, prev_rem, precision_rounding=move.product_uom.rounding) == 0:
                if move.bom_line_id and not prev.bom_line_id:
                    by_product[move.product_id.id] = move
        return self.env['stock.move'].browse([m.id for m in by_product.values()])

    def _tablet_prepare_moves_for_tablet_consumption(self, moves):
        """Quita ``manual_consumption`` en líneas que el tablet va a consumir por LdM."""
        if not moves:
            return
        to_clear = moves.filtered('manual_consumption')
        if to_clear:
            to_clear.write({'manual_consumption': False})

    def _tablet_round_qty_for_stock_move(self, move, qty_in_move_uom):
        """Redondea según la UdM del movimiento (igual que ``should_consume_qty`` en MRP estándar)."""
        move.ensure_one()
        rounding = move.product_uom.rounding
        if float_is_zero(qty_in_move_uom, precision_rounding=rounding):
            return 0.0
        return float_round(
            qty_in_move_uom,
            precision_rounding=rounding,
            rounding_method='HALF-UP',
        )

    def _tablet_compute_raw_batch_consumption_qtys(self, raw_moves, qty_to_produce):
        """[(move, qty)] proporcional al pendiente de la MO (exacto por fardo LdM).

        Usa ``qty_to_produce / pendiente_MO`` × demanda del movimiento (``product_uom_qty``),
        sin restar reservas en líneas de operación.
        """
        self.ensure_one()
        mo = self.production_id
        pairs = []
        pending_mo = self._tablet_mo_pending_qty()
        rounding_mo = mo.product_uom_id.rounding
        if float_compare(pending_mo, 0.0, precision_rounding=rounding_mo) <= 0:
            return pairs
        qty_to_produce = self._tablet_normalize_production_qty(qty_to_produce)
        ratio = qty_to_produce / pending_mo
        finishes_mo = float_compare(
            mo.qty_produced + qty_to_produce,
            mo.product_qty,
            precision_rounding=rounding_mo,
        ) >= 0
        for move in raw_moves:
            remaining_move = self._tablet_raw_move_remaining_qty(move)
            rounding = move.product_uom.rounding
            if float_compare(remaining_move, 0.0, precision_rounding=rounding) <= 0:
                continue
            if finishes_mo:
                qty_rounded = self._tablet_round_qty_for_stock_move(move, remaining_move)
            else:
                qty_rounded = self._tablet_round_qty_for_stock_move(
                    move, remaining_move * ratio,
                )
                if float_compare(qty_rounded, remaining_move, precision_rounding=rounding) > 0:
                    qty_rounded = self._tablet_round_qty_for_stock_move(move, remaining_move)
            if qty_rounded > 0:
                pairs.append((move, qty_rounded))
        return pairs

    def _tablet_assert_raw_stock_for_batch(self, raw_moves, qty_to_produce):
        """Bloquea el lote si no hay stock (reservado en el movimiento + libre en ubicación) para cada MP inventariable."""
        self.ensure_one()
        Quant = self.env['stock.quant']
        pairs = self._tablet_compute_raw_batch_consumption_qtys(raw_moves, qty_to_produce)
        for move, qty_rounded in pairs:
            product = move.product_id
            if not product.is_storable:
                continue
            if move._should_bypass_reservation():
                continue
            needed_product_uom = move.product_uom._compute_quantity(
                qty_rounded, product.uom_id, rounding_method='HALF-UP',
            )
            if float_is_zero(needed_product_uom, precision_rounding=product.uom_id.rounding):
                continue
            reserved_product_uom = 0.0
            mls_count = move.move_line_ids
            if product.tracking != 'none':
                mls_count = mls_count.filtered('lot_id')
            for ml in mls_count:
                reserved_product_uom += ml.product_uom_id._compute_quantity(
                    ml.quantity, product.uom_id, rounding_method='HALF-UP',
                )
            if float_compare(reserved_product_uom, needed_product_uom, precision_rounding=product.uom_id.rounding) >= 0:
                continue
            short = needed_product_uom - reserved_product_uom
            free_at_loc = Quant._get_available_quantity(product, move.location_id, strict=False)
            if float_compare(free_at_loc, short, precision_rounding=product.uom_id.rounding) < 0:
                raise UserError(_(
                    'No hay inventario suficiente para registrar este lote desde el tablet.\n\n'
                    'Componente: %(product)s\n'
                    'Ubicación de consumo: %(loc)s\n'
                    'Necesario para este lote: %(need)s %(uom)s\n'
                    'Ya reservado para esta orden: %(res)s %(uom)s\n'
                    'Cantidad adicional libre en ubicación: %(free)s %(uom)s\n\n'
                    'Resuelva el stock o la reserva antes de crear el lote; así se evita un lote sin movimiento de PT.'
                ) % {
                    'product': product.display_name,
                    'loc': move.location_id.display_name,
                    'need': needed_product_uom,
                    'res': reserved_product_uom,
                    'free': free_at_loc,
                    'uom': product.uom_id.name,
                })

    def _tablet_unlink_raw_lines_without_lot(self, move):
        """Elimina reservas sin lote en MP trazable (MRP a veces las crea sin lot_id; PEPS no aplica ahí)."""
        bad = move.move_line_ids.filtered(
            lambda ml: not ml.lot_id and not ml.lot_name and ml.quantity,
        )
        if bad:
            _logger.info(
                'Tablet batch: quitando %s línea(s) sin lote del move id=%s producto=%s',
                len(bad), move.id, move.product_id.display_name,
            )
            bad.unlink()

    def _tablet_reserved_qty_with_lot(self, move):
        """Cantidad reservada en el movimiento solo en líneas con lote asignado."""
        qty = 0.0
        for ml in move.move_line_ids.filtered('lot_id'):
            qty += ml.product_uom_id._compute_quantity(
                ml.quantity, move.product_uom, rounding_method='HALF-UP',
            )
        return qty

    def _tablet_reserve_lots_for_raw_consumption(self, raw_moves, qty_to_produce):
        """Reserva FIFO con lot_id en líneas de MP trazables antes de crear el lote PT."""
        self.ensure_one()
        pairs = self._tablet_compute_raw_batch_consumption_qtys(raw_moves, qty_to_produce)
        missing = []
        Quant = self.env['stock.quant'].sudo()
        for move, qty_rounded in pairs:
            product = move.product_id
            if product.tracking == 'none' or move._should_bypass_reservation():
                continue
            self._tablet_unlink_raw_lines_without_lot(move)
            reserved_uom = self._tablet_reserved_qty_with_lot(move)
            if float_compare(reserved_uom, qty_rounded, precision_rounding=move.product_uom.rounding) < 0:
                still_need = qty_rounded - reserved_uom
                taken = move._update_reserved_quantity(still_need, move.location_id, strict=False)
                reserved_uom += taken
            if float_compare(reserved_uom, qty_rounded, precision_rounding=move.product_uom.rounding) < 0:
                still_need = qty_rounded - reserved_uom
                need_product_uom = move.product_uom._compute_quantity(
                    still_need, product.uom_id, rounding_method='HALF-UP',
                )
                remaining_product_uom = need_product_uom
                quants = Quant._gather(
                    product, move.location_id, strict=False, qty=need_product_uom,
                )
                for quant in quants.filtered('lot_id'):
                    if float_is_zero(remaining_product_uom, precision_rounding=product.uom_id.rounding):
                        break
                    avail = quant.quantity - quant.reserved_quantity
                    if float_compare(avail, 0, precision_rounding=product.uom_id.rounding) <= 0:
                        continue
                    slice_product_uom = min(avail, remaining_product_uom)
                    slice_move_uom = product.uom_id._compute_quantity(
                        slice_product_uom, move.product_uom, rounding_method='HALF-UP',
                    )
                    taken = move._update_reserved_quantity(
                        slice_move_uom,
                        move.location_id,
                        lot_id=quant.lot_id,
                        strict=True,
                    )
                    remaining_product_uom -= move.product_uom._compute_quantity(
                        taken, product.uom_id, rounding_method='HALF-UP',
                    )
                    reserved_uom += taken
            reserved_uom = self._tablet_reserved_qty_with_lot(move)
            without_lot = move.move_line_ids.filtered(lambda ml: not ml.lot_id and ml.quantity)
            if float_compare(reserved_uom, qty_rounded, precision_rounding=move.product_uom.rounding) < 0:
                free_lots = Quant._get_available_quantity(
                    product, move.location_id, strict=False,
                )
                missing.append((
                    product, qty_rounded, reserved_uom, move.location_id,
                    without_lot, free_lots,
                ))
            elif without_lot:
                missing.append((
                    product, qty_rounded, reserved_uom, move.location_id,
                    without_lot, 0.0,
                ))
        if missing:
            lines = []
            for product, need, got, loc, without_lot, free_lots in missing:
                extra = ''
                if without_lot:
                    qty_no_lot = sum(without_lot.mapped('quantity'))
                    extra = _(
                        '\n  Hay %(qty)s %(uom)s reservados en líneas sin lote en la orden '
                        '(detalle de operaciones); el tablet exige lote para consumir.'
                    ) % {'qty': qty_no_lot, 'uom': product.uom_id.name}
                if float_compare(free_lots, 0, precision_rounding=product.uom_id.rounding) > 0:
                    extra += _(
                        '\n  Stock libre con lote en ubicación: %(free)s %(uom)s (PEPS/FIFO).'
                    ) % {'free': free_lots, 'uom': product.uom_id.name}
                lines.append(_(
                    '- %(product)s: necesario %(need)s %(uom)s en %(loc)s; '
                    'reservado con lote %(got)s %(uom)s.%(extra)s'
                ) % {
                    'product': product.display_name,
                    'need': need,
                    'got': got,
                    'loc': loc.display_name,
                    'uom': product.uom_id.name,
                    'extra': extra,
                })
            raise UserError(_(
                'No se puede crear el lote de producto terminado: faltan lotes de materia prima '
                'en la ubicación de consumo (reserva FIFO).\n\n%(detail)s\n\n'
                'Revise inventario, lotes disponibles y la ubicación de componentes de la orden.'
            ) % {'detail': '\n'.join(lines)})

    def _tablet_set_raw_consumption(self, raw_moves, qty_to_produce):
        """Establece cantidad a consumir en raw moves según BOM para qty_to_produce.

        Por cada componente: fracción del saldo del movimiento según ``qty_to_produce / pendiente_MO``.
        Tamaño del lote PT: ``bom.product_qty`` (``_tablet_get_batch_qty``).
        """
        mo = self.production_id
        bom = mo.bom_id
        if not bom or bom.product_qty <= 0:
            _logger.warning(
                'Tablet raw consumption: sin BOM o bom.product_qty<=0 mo=%s bom=%s',
                mo.id, bom.id if bom else None,
            )
            return
        _logger.info(
            'Tablet raw consumption: WO=%s qty_to_produce=%s bom.product_qty=%s raw_moves#=%s',
            self.id, qty_to_produce, bom.product_qty, len(raw_moves),
        )
        for move, qty_rounded in self._tablet_compute_raw_batch_consumption_qtys(raw_moves, qty_to_produce):
            try:
                move._set_quantity_done(qty_rounded)
            except UserError:
                raise
            except Exception as err:
                precision_digits = self.env['decimal.precision'].precision_get(
                    'Product Unit of Measure',
                )
                raise UserError(_(
                    'No se pudo registrar el consumo de «%(product)s» (%(qty)s %(uom)s) al crear el lote.\n'
                    'Revise el redondeo de la UdM (p. ej. kg con 0,001) y en Ajustes → Técnico → '
                    'Precisión decimal → «Unidad de medida del producto» (recomendado ≥ %(digits)s decimales '
                    'si la LdM usa gramos o milésimas de kg).\n\n'
                    'Detalle: %(detail)s'
                ) % {
                    'digits': max(3, precision_digits + 1),
                    'product': move.product_id.display_name,
                    'qty': qty_rounded,
                    'uom': move.product_uom.name,
                    'detail': err,
                }) from err
                _logger.info(
                'Tablet raw consumption: move id=%s product=%s _set_quantity_done(%.6f %s) -> move.quantity=%.6f',
                move.id,
                move.product_id.display_name,
                qty_rounded,
                move.product_uom.name,
                move.quantity,
            )

    def action_open_production_board(self):
        """Abre el tablero operativo MRP para esta WO (un solo card), coherente con el resto de acciones."""
        self.ensure_one()
        action = self._tablet_check_pin_timeout()
        if action:
            return action
        self._tablet_assert_mo_finished_product_lot_tracked()
        return self._tablet_action_return_kanban_single_wo(self.workcenter_id)

    def _tablet_notify_material_scrap_reminder(self):
        """Aviso no bloqueante: recordar registrar merma tras paro o al iniciar."""
        self.ensure_one()
        try:
            self.env.user._bus_send(
                'simple_notification',
                {
                    'type': 'warning',
                    'title': _('Merma de material'),
                    'message': _(
                        'Si hubo pérdida de material, puede registrarla con el botón '
                        '«Merma Material» (no es obligatorio para continuar).'
                    ),
                },
            )
        except Exception:
            _logger.debug('No se pudo enviar recordatorio de merma tablet', exc_info=True)

    def _tablet_assert_stock_for_material_scrap(self, move, quantity, lot=None):
        """Valida existencia en ubicación de consumo del componente antes de desechar."""
        self.ensure_one()
        product = move.product_id
        if not product.is_storable or move._should_bypass_reservation():
            return
        rounding = product.uom_id.rounding
        qty_product_uom = move.product_uom._compute_quantity(
            quantity, product.uom_id, rounding_method='HALF-UP',
        )
        if float_is_zero(qty_product_uom, precision_rounding=rounding):
            return
        Quant = self.env['stock.quant']
        if product.tracking != 'none' and lot:
            available = Quant._get_available_quantity(
                product, move.location_id, lot_id=lot.id, strict=True,
            )
        else:
            reserved_product_uom = 0.0
            for ml in move.move_line_ids:
                reserved_product_uom += ml.product_uom_id._compute_quantity(
                    ml.quantity, product.uom_id, rounding_method='HALF-UP',
                )
            free_at_loc = Quant._get_available_quantity(
                product, move.location_id, strict=False,
            )
            available = reserved_product_uom + free_at_loc
        if float_compare(available, qty_product_uom, precision_rounding=rounding) < 0:
            raise UserError(_(
                'No hay inventario suficiente para registrar esta merma.\n\n'
                'Componente: %(product)s\n'
                'Ubicación: %(loc)s\n'
                'Cantidad solicitada: %(need)s %(uom)s\n'
                'Disponible (reservado + libre): %(avail)s %(uom)s'
            ) % {
                'product': product.display_name,
                'loc': move.location_id.display_name,
                'need': qty_product_uom,
                'avail': available,
                'uom': product.uom_id.name,
            })

    def _tablet_finish_material_scrap_wizard(self, wizard):
        """Crea stock.scrap validado y línea de auditoría en la MO."""
        self.ensure_one()
        mo = wizard.production_id
        move = wizard.move_raw_id
        self._tablet_assert_stock_for_material_scrap(
            move, wizard.quantity, lot=wizard.lot_id,
        )
        self = self._tablet_sudo()
        mo = wizard.production_id.sudo()
        move = wizard.move_raw_id.sudo()
        scrap_vals = {
            'production_id': mo.id,
            'workorder_id': self.id,
            'product_id': wizard.product_id.id,
            'scrap_qty': wizard.quantity,
            'product_uom_id': wizard.product_uom_id.id,
            'location_id': move.location_id.id,
            'origin': mo.name,
        }
        if wizard.lot_id:
            scrap_vals['lot_id'] = wizard.lot_id.id
        scrap = self.env['stock.scrap'].create(scrap_vals)
        validate_result = scrap.action_validate()
        if isinstance(validate_result, dict):
            raise UserError(_(
                'No hay inventario suficiente para completar la merma de «%s» en %s.'
            ) % (wizard.product_id.display_name, move.location_id.display_name))
        self.env['kc.mrp.production.resin.scrap'].create({
            'production_id': mo.id,
            'workorder_id': self.id,
            'product_id': wizard.product_id.id,
            'type_id': wizard.type_id.id,
            'scrap_id': scrap.id,
            'employee_id': wizard.employee_id.id,
            'quantity': wizard.quantity,
        })
        try:
            self.env.user._bus_send(
                'simple_notification',
                {
                    'type': 'success',
                    'title': _('Merma registrada'),
                    'message': _(
                        '%(qty)s %(uom)s de %(product)s (%(tipo)s).'
                    ) % {
                        'qty': wizard.quantity,
                        'uom': wizard.product_uom_id.name,
                        'product': wizard.product_id.display_name,
                        'tipo': wizard.type_id.name,
                    },
                },
            )
        except Exception:
            _logger.debug('Notificación merma tablet', exc_info=True)
        return self._tablet_action_return_kanban_single_wo(self.workcenter_id)

    def action_tablet_confirm_material_waste(self):
        """Abre asistente para merma de componentes de la lista de materiales de la MO."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(
            employee, 'kc_tablet_allow_material_scrap', _('Merma de material'),
        )
        mo = self.production_id
        if mo.state in ('done', 'cancel'):
            raise UserError(_('La orden de fabricación está terminada o cancelada.'))
        if self.state == 'done':
            raise UserError(_('La orden de trabajo ya está finalizada.'))
        raw_moves = mo._kc_tablet_material_scrap_raw_moves()
        if not raw_moves:
            raise UserError(_(
                'No hay componentes inventariables pendientes de consumo en esta orden '
                '(líneas sin marcar «Consumido»). Si ya consumió todo el lote actual, '
                'registre primero producción parcial o revise la pestaña Componentes de la MO.'
            ))
        default_move = raw_moves[:1]
        wizard_vals = {
            'workorder_id': self.id,
            'employee_id': employee.id,
            'move_raw_id': default_move.id,
            'quantity': 0.0,
        }
        if len(raw_moves) == 1:
            wizard_vals['move_raw_id'] = default_move.id
        wizard = self.env['mrp.tablet.material.scrap.wizard'].create(wizard_vals)
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'name': _('Merma de material'),
            'res_model': 'mrp.tablet.material.scrap.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        })

    def _tablet_selective_manual_component_line_commands(self):
        """Comandos (0,0,vals) de componentes de la MO para el asistente de consumo selectivo."""
        self.ensure_one()
        commands = []
        seq = 10
        for move in self._tablet_raw_moves_with_remaining_consumption():
            commands.append((0, 0, {'move_id': move.id, 'sequence': seq, 'consume': True}))
            seq += 10
        return commands

    def action_tablet_open_selective_manual_production(self):
        """Producción manual: lote existente obligatorio y componentes de la LdM seleccionables."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(
            employee, 'kc_tablet_allow_selective_manual', _('Producción manual (componentes)'),
        )
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()
        if self.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de registrar producción manual.'))
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        suggested_qty = self._tablet_suggested_batch_lot_qty()
        if float_is_zero(suggested_qty, precision_rounding=rounding):
            raise UserError(_('La orden ya está completa. No hay cantidad por producir.'))
        lots = self.env['stock.lot'].search([
            ('product_id', '=', mo.product_id.id),
            ('kc_prelabel_production_id', '=', mo.id),
            ('kc_prelabel_state', '!=', 'pending'),
        ], order='id desc', limit=1)
        if not lots:
            raise UserError(_(
                'No hay lotes de producto terminado vinculados a esta orden. '
                'Cree al menos un lote con «Crear lote» o producción manual estándar antes de '
                'añadir cantidad a un lote existente con consumo selectivo.'
            ))
        line_cmds = self._tablet_selective_manual_component_line_commands()
        if not line_cmds:
            raise UserError(_(
                'No hay componentes con cantidad pendiente por consumir en esta orden. '
                'Revise la pestaña Componentes (puede haber líneas duplicadas ya cerradas).'
            ))
        wizard = self.env['mrp.tablet.selective.manual.production.wizard'].create({
            'workorder_id': self.id,
            'employee_id': employee.id,
            'product_id': mo.product_id.id,
            'product_uom_id': mo.product_uom_id.id,
            'qty_to_produce': suggested_qty,
            'lot_id': lots[0].id,
            'line_ids': line_cmds,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'name': _('Producción manual (componentes)'),
            'res_model': 'mrp.tablet.selective.manual.production.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        })

    def action_tablet_confirm_manual_production(self):
        """Producción manual: cantidad editable, lote existente o nuevo (sin pre-etiqueta pendiente)."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(
            employee, 'kc_tablet_allow_create_bad_lot', _('Producción manual'),
        )
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()
        if self.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de registrar producción manual.'))
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        suggested_qty = self._tablet_suggested_batch_lot_qty()
        if float_is_zero(suggested_qty, precision_rounding=rounding):
            raise UserError(_('La orden ya está completa. No hay cantidad por producir.'))
        last_ticket = self.env['mrp.batch.ticket'].search([
            ('production_id', '=', mo.id),
            ('product_id', '=', mo.product_id.id),
        ], limit=1, order='id desc')
        default_lot_id = False
        if last_ticket and last_ticket.lot_id:
            lot = last_ticket.lot_id
            if lot.kc_prelabel_state != 'pending':
                default_lot_id = lot.id
        wizard = self.env['mrp.tablet.confirm.batch.lot.bad.qty.wizard'].create({
            'workorder_id': self.id,
            'employee_id': employee.id,
            'product_id': mo.product_id.id,
            'product_uom_id': mo.product_uom_id.id,
            'qty_to_produce': suggested_qty,
            'lot_id': default_lot_id,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'name': _('Producción manual'),
            'res_model': 'mrp.tablet.confirm.batch.lot.bad.qty.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        })

    def action_tablet_confirm_create_batch_lot_bad_qty(self):
        """Alias histórico → producción manual."""
        return self.action_tablet_confirm_manual_production()

    def action_create_batch_lot_bad_qty(self):
        """Alias histórico → producción manual."""
        return self.action_tablet_confirm_manual_production()

    def action_pause_production(self):
        """Abre el modal de selección de motivo de paro: kanban raíz (padres y sin padre); al clic en padre se ven hijos, al clic en no padre se ejecuta el paro."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_pause', _('Pausar/Parar'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        view = self.env.ref(
            'kc_mrp_wizard.mrp_production_stop_type_kanban_root',
            raise_if_not_found=False,
        )
        action_dict = {
            'type': 'ir.actions.act_window',
            'name': _('Paros'),
            'res_model': 'mrp.production.stop.type',
            'view_mode': 'kanban',
            'domain': [
                ('active', '=', True),
                ('parent_id', '=', False),
                '|',
                ('company_id', '=', self.company_id.id),
                ('company_id', '=', False),
            ],
            'context': {'workorder_id': self.id},
            'target': 'new',
        }
        if view:
            action_dict['view_id'] = view.id
        return self._tablet_return_with_refreshed_pin(action_dict)
        
    def action_quality_alert(self):
        """Crea una alerta de calidad para la orden de trabajo y muestra una confirmación al usuario."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_quality_alert', _('Crear alerta de calidad'))
        company = self.company_id or self.env.company
        product = self.production_id.product_id.product_tmpl_id
        workcenter = self.workcenter_id
        title = _('Alerta de calidad: %s en %s — O.T.: %s') % (self.name, workcenter.name, self.display_name)
        description = _('Alerta de calidad: %s — O.T.: %s') % (self.name, self.display_name)
        alert = self._tablet_sudo().env['quality.alert'].create({
            'title': title,
            'description': description,
            'product_tmpl_id': product.id,
            'workcenter_id': workcenter.id,
            'company_id': company.id,
            'priority': '2',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Alerta de calidad creada'),
                'message': _('Se ha creado la alerta de calidad "%s".') % alert.display_name,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_register_stop_type(self, stop_type_id=None):
        """Registra un paro según el tipo indicado: crea alerta de calidad y/o solicitud de mantenimiento según configuración del tipo.
        No abre ventanas; marca la WO en pausa, muestra mensaje y regresa al asistente MRP refrescado."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_pause', _('Pausar/Parar'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        stop_type_id = stop_type_id or self.env.context.get('stop_type_id')
        if not stop_type_id:
            raise UserError(_('Indique el tipo de paro.'))
        stop_type = self.env['mrp.production.stop.type'].browse(stop_type_id)
        if not stop_type.exists():
            raise UserError(_('Tipo de paro no encontrado.'))
        alert = self.env['quality.alert']
        request = self.env['maintenance.request']
        if stop_type.create_quality_alert:
            alert = stop_type.with_user(self.env.user).sudo().action_create_quality_alert_from_workorder(self)
        if stop_type.create_maintenance_request:
            request = stop_type.with_user(self.env.user).sudo().action_create_maintenance_request_from_workorder(self)
        self._tablet_sudo().button_pending()
        # Regresar al tablero filtrado a esta WO (mismo criterio que tras crear lote / "un solo card").
        # Antes se usaba el dominio de todas las WO del centro y se perdía el filtro al operativo.
        result = self._tablet_action_return_kanban_single_wo(self.workcenter_id)
        parts = []
        if alert:
            parts.append(_('Alerta de calidad: %s') % alert.name)
        if request:
            parts.append(_('Solicitud de mantenimiento: %s') % request.name)
        if parts:
            message = ' — '.join(parts)
            result = dict(result)
            ctx = dict(result.get('context') or {})
            ctx['tablet_stop_message'] = message
            result['context'] = ctx
        self._tablet_notify_material_scrap_reminder()
        return result

    def action_tablet_confirm_create_batch_lot(self):
        """Abre wizard de confirmación con Producto, cantidad y unidad; al aceptar crea el lote."""
        self.ensure_one()
        action, employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_create_lot', _('Crear lote'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        qty_to_produce = self._tablet_suggested_batch_lot_qty()
        if float_is_zero(qty_to_produce, precision_rounding=rounding):
            raise UserError(_('La orden ya está completa. No hay cantidad por producir.'))
        self._tablet_assert_has_raw_to_consume()
        batches_left = self._tablet_count_batches_for_qty(self._tablet_mo_pending_qty())
        wizard = self.env['mrp.tablet.confirm.batch.lot.wizard'].create({
            'workorder_id': self.id,
            'employee_id': employee.id,
            'product_id': mo.product_id.id,
            'qty_to_produce': qty_to_produce,
            'product_uom_id': mo.product_uom_id.id,
            'batches_remaining_hint': _('%s lote(s) de este tamaño aprox.') % batches_left,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.confirm.batch.lot.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Confirmar datos del lote'),
        })

    def action_tablet_create_batch_lot(self):
        """Crea lote (fardo) desde la vista MRP; empleado desde context['tablet_employee_id']."""
        self.ensure_one()
        action, employee_id, employee, workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_create_lot', _('Crear lote'))
        mo = self.production_id
        rounding = mo.product_uom_id.rounding
        qty_to_produce = self._tablet_suggested_batch_lot_qty()
        batch_qty = self._tablet_get_batch_qty()
        _logger.info(
            'MRP create batch: WO=%s MO=%s qty_produced=%s lote=%s bom_base=%s pending_mo=%s lotes_aprox=%s',
            self.id, mo.id, mo.qty_produced, qty_to_produce,
            mo.bom_id.product_qty if mo.bom_id else 0,
            self._tablet_mo_pending_qty(),
            self._tablet_count_batches_for_qty(self._tablet_mo_pending_qty()),
        )
        if float_is_zero(qty_to_produce, precision_rounding=rounding):
            raise UserError(_('La orden ya está completa. No hay cantidad por producir.'))
        return self._tablet_create_batch_lot_impl(
            qty_to_produce,
            employee,
            workcenter,
            lot=None,
            is_bad_quality=False,
        )

    def _tablet_finish_semi_ticket_wizard(self, wizard):
        """Crea `mrp.semi.ticket`, albarán interno semi (si aplica), imprime etiqueta y vuelve al kanban MRP."""
        self.ensure_one()
        self = self._tablet_sudo()
        mo = self.production_id
        ticket = self.env['mrp.semi.ticket'].create({
            'production_id': mo.id,
            'workorder_id': self.id,
            'workcenter_id': self.workcenter_id.id,
            'operation_id': wizard.operation_id.id,
            'product_id': wizard.product_id.id if wizard.product_id else False,
            'uom_id': wizard.uom_id.id,
            'quantity': wizard.quantity,
            'employee_id': wizard.employee_id.id,
            'company_id': mo.company_id.id,
        })
        ticket._kc_try_create_semi_internal_picking()
        if ticket._kc_semi_ticket_should_print():
            ticket.write({
                'printed_at': fields.Datetime.now(),
                'print_count': 1,
            })
            try:
                ticket._report_print()
            except Exception:
                _logger.exception('Impresión ticket semiterminado id=%s', ticket.id)
        else:
            _logger.info(
                'KC MRP: ticket semi %s creado sin impresión (requiere «Imprimir ticket» en la operación '
                'e impresora de red en el centro %s).',
                ticket.id,
                self.workcenter_id.display_name if self.workcenter_id else '-',
            )
        return self._tablet_action_return_kanban_single_wo(self.workcenter_id)

    def action_tablet_confirm_register_semi(self):
        """Abre el asistente para registrar semiterminado (operación con flag en la LdM de la BOM)."""
        self.ensure_one()
        action, _employee_id, employee, _workcenter = self._tablet_validate_session()
        if action:
            return action
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_register_semi', _('Registrar semi'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        if self.state != 'progress':
            raise UserError(
                _('Solo puede registrar semiterminado con la orden de trabajo en progreso.')
            )
        if not self.operation_id or not self.operation_id.kc_tablet_register_semi:
            raise UserError(_(
                'Esta operación no está configurada para registrar semiterminado. '
                'Active "Registra semiterminado" en la línea de operación de la LdM.'
            ))
        op = self.operation_id
        uom = self._kc_tablet_semi_declaration_uom()
        if not uom:
            raise UserError(_(
                'Indique "UdM declaración semi" o un producto de semiterminado en la operación de la LdM.'
            ))
        wizard = self.env['mrp.tablet.semi.ticket.wizard'].create({
            'workorder_id': self.id,
            'employee_id': employee.id,
            'operation_id': op.id,
            'product_id': op.kc_semi_product_id.id if op.kc_semi_product_id else False,
            'uom_id': uom.id,
            'quantity': 1.0,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.semi.ticket.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Registrar semiterminado'),
        })

    def action_tablet_open_prelabel_print(self):
        """Abre wizard para generar e imprimir pre-etiquetas (lotes pendientes sin movimiento)."""
        self.ensure_one()
        action, _eid, employee, _wc = self._tablet_validate_session()
        if action:
            return self._tablet_return_with_refreshed_pin(action)
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_prelabels', _('Pre-etiquetas'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()
        if self.state not in ('ready', 'waiting', 'progress', 'pending'):
            raise UserError(_(
                'Pre-etiquetas: la orden de trabajo debe estar en progreso, lista, esperando componentes '
                'o en espera de otra operación.'
            ))
        wizard = self.env['mrp.tablet.prelabel.lot.print.wizard'].create({
            'workorder_id': self.id,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.prelabel.lot.print.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Imprimir pre-etiquetas'),
            'context': {
                'default_employee_id': False,
                'default_kc_employee_id': False,
            },
        })

    def action_tablet_open_consult_lot(self):
        """Abre wizard para consultar un lote (manual o QR GS1) y opcionalmente reimprimir."""
        self.ensure_one()
        action, _eid, employee, _wc = self._tablet_validate_session()
        if action:
            return self._tablet_return_with_refreshed_pin(action)
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()
        if self.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de consultar lotes.'))
        wizard = self.env['mrp.tablet.reprint.label.wizard'].create({
            'workorder_id': self.id,
            'employee_id': employee.id,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.reprint.label.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Consultar lote'),
        })

    def action_tablet_open_reprint_label(self):
        """Alias retrocompatible del botón kanban → consultar lote."""
        return self.action_tablet_open_consult_lot()

    def action_tablet_open_consume_prelabel(self):
        """Abre wizard para escanear una pre-etiqueta y ejecutar producción igual que «Crear lote» (MRP)."""
        self.ensure_one()
        action, _eid, employee, _wc = self._tablet_validate_session()
        if action:
            return self._tablet_return_with_refreshed_pin(action)
        self._tablet_assert_employee_permission(employee, 'kc_tablet_allow_scan_prelabel', _('Escanear pre-etiqueta'))
        self._tablet_assert_mo_finished_product_lot_tracked()
        self._tablet_assert_authorized_pt_lot_workcenter()
        if self.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de escanear la pre-etiqueta.'))
        wizard = self.env['mrp.tablet.consume.prelabel.lot.wizard'].create({
            'workorder_id': self.id,
            'employee_id': employee.id,
        })
        return self._tablet_return_with_refreshed_pin({
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.consume.prelabel.lot.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Escanear pre-etiqueta'),
        })
