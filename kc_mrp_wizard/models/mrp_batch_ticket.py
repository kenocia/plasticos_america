# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpBatchTicket(models.Model):
    _name = 'mrp.batch.ticket'
    _description = 'Ticket de lote (fardo) - Asistente tablet'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        required=True,
        ondelete='restrict',
        index=True,
    )
    qty = fields.Float(
        string='Cantidad',
        digits='Product Unit of Measure',
        required=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        related='product_id.uom_id',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='restrict',
        check_company=True,
    )
    is_bad_quality = fields.Boolean(
        string='Mala calidad',
        default=False,
        help='Marcar si el lote corresponde a producción de mala calidad.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
    )
    printed_at = fields.Datetime(
        string='Última impresión',
        readonly=True,
    )
    print_count = fields.Integer(
        string='Veces impreso',
        default=0,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mrp.batch.ticket') or _('New')
        return super().create(vals_list)

    def action_reprint(self):
        """Incrementa contador y dispara impresión."""
        self.ensure_one()
        self.write({
            'printed_at': fields.Datetime.now(),
            'print_count': self.print_count + 1,
        })
        return self._report_print()

    def _report_print(self):
        """Devuelve la acción de impresión del reporte de viñeta."""
        self.ensure_one()
        report = self.env.ref('kc_mrp_wizard.action_report_batch_ticket', raise_if_not_found=False)
        if not report:
            return True
        return report.report_action(self)
