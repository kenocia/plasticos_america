# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class KcLotLabelPrintWizard(models.TransientModel):
    _name = 'kc.lot.label.print.wizard'
    _description = 'Enviar etiquetas de lote a impresora Zebra en red'

    printer_id = fields.Many2one(
        'network.printer',
        string='Impresora de red',
        domain=[('active', '=', True)],
        help='Impresora Zebra (RAW TCP, habitualmente puerto 9100).',
    )
    lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes',
        required=True,
    )
    label_profile = fields.Selection(
        [
            ('manufacturing', 'Fabricación (GS1 / lote interno)'),
            ('raw_material', 'Materia prima (GS1 / lote interno)'),
            ('supplier', 'Recepción proveedor'),
        ],
        string='Tipo de etiqueta',
        required=True,
        default='manufacturing',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán de recepción',
        help='Solo para etiquetas de proveedor: enlace al albarán de entrada.',
    )
    lock_supplier_profile = fields.Boolean(
        string='Bloquear perfil proveedor',
        default=False,
        help='Técnico: evita cambiar el tipo cuando se abre desde recepción.',
    )
    kc_pdf_visible = fields.Boolean(compute='_compute_kc_pdf_visible')

    @api.depends('lot_ids')
    def _compute_kc_pdf_visible(self):
        for wiz in self:
            wiz.kc_pdf_visible = len(wiz.lot_ids) == 1

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        ctx = self.env.context
        if ctx.get('default_picking_id') and 'picking_id' in field_list:
            res['picking_id'] = ctx['default_picking_id']
        if ctx.get('kc_lock_supplier_label'):
            res['lock_supplier_profile'] = True
            res['label_profile'] = 'supplier'
        if (
            'printer_id' in field_list
            and 'printer_id' not in res
            and not ctx.get('default_printer_id')
        ):
            printer = self.env['network.printer'].search([('active', '=', True)], limit=1)
            if printer:
                res['printer_id'] = printer.id
        return res

    def action_print_zebra(self):
        self.ensure_one()
        if not self.printer_id:
            raise UserError(_('Seleccione una impresora de red.'))
        if not self.lot_ids:
            raise UserError(_('No hay lotes para imprimir.'))
        chunks = []
        for lot in self.lot_ids:
            if self.label_profile == 'supplier':
                chunks.append(lot._kc_build_supplier_reception_zebra_zpl(self.picking_id))
            elif self.label_profile == 'raw_material':
                chunks.append(lot._kc_build_raw_material_zebra_zpl())
            else:
                fn = getattr(lot, '_kc_build_zebra_lot_gs1_zpl', None)
                if not callable(fn):
                    raise UserError(
                        _('La etiqueta de fabricación requiere el módulo «KenoCia MRP Wizard» (kc_mrp_wizard).')
                    )
                chunks.append(fn())
        payload = ''.join(chunks).encode('utf-8', errors='replace')
        send = getattr(self.printer_id, 'send_tcp_raw_binary', None)
        if not callable(send):
            raise UserError(
                _('El modelo de impresora de red no expone envío RAW TCP. Revise el módulo network_printer / KC.')
            )
        result = send(payload)
        if not result.get('success'):
            raise UserError(result.get('error') or _('No se pudo enviar a la impresora.'))
        return {'type': 'ir.actions.act_window_close'}

    def action_open_pdf_label(self):
        """Etiqueta PDF (GS1) del primer lote o lote único — útil como respaldo."""
        self.ensure_one()
        lots = self.lot_ids
        if len(lots) != 1:
            raise UserError(_('Abrir PDF solo está disponible cuando hay un único lote seleccionado.'))
        return self.env.ref('kc_plasticasa.action_report_kc_lot_label').report_action(lots)
