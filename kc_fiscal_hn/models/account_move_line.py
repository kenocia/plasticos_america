# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Redefinir price_subtotal con 4 dígitos decimales
    price_subtotal = fields.Monetary(compute='_compute_totals', string='Subtotal', store=True, currency_field='currency_id', digits=(16, 4))
    
    # base_imponible = fields.Monetary(string='Base Imponible', compute='_compute_base_imponible', store=True, currency_field='currency_id')
    # porcentaje_retencion = fields.Float(string='Porcentaje Retención', compute='_compute_porcentaje_retencion', store=True)

    base_imponible = fields.Float(string='Base Imponible', required=False)
    porcentaje_retencion = fields.Float(string='% de Retención', required=False)
    importe_isv15 = fields.Monetary(
        string='Importe base 15% (Boletín)',
        currency_field='currency_id',
        compute='_compute_importe_isv15',
        store=True,
        help='Monto de base 15% tomado del subtotal para productos marcados como Boletín (sin ISV).'
    )

    # @api.depends('price_subtotal', 'tax_ids')
    # def _compute_base_imponible(self):
    #     for line in self:
    #         if line.tax_ids:
    #             # Calcular la base imponible considerando los impuestos
    #             taxes_res = line.tax_ids.compute_all(
    #                 line.price_subtotal,
    #                 currency=line.currency_id,
    #                 quantity=1.0,
    #                 product=line.product_id,
    #                 partner=line.partner_id
    #             )
    #             line.base_imponible = taxes_res['total_excluded']
    #         else:
    #             line.base_imponible = line.price_subtotal

    # @api.depends('tax_ids')
    # def _compute_porcentaje_retencion(self):
    #     for line in self:
    #         retencion_tax = line.tax_ids.filtered(lambda t: t.tax_group_id.name == 'Retención')
    #         if retencion_tax:
    #             line.porcentaje_retencion = retencion_tax[0].amount
    #         else:
    #             line.porcentaje_retencion = 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            # Obtener el impuesto de retención del producto
            tax_retention = self.product_id.tax_retention
            invoice_retention = self.move_id.invoice_retention
            if tax_retention:
                self.base_imponible = invoice_retention.amount_untaxed
                self.porcentaje_retencion = abs(tax_retention.amount)

                self.price_unit = self.base_imponible * self.porcentaje_retencion / 100

    @api.depends('quantity', 'price_unit', 'discount', 'product_id')
    def _compute_importe_isv15(self):
        """
        Para líneas cuyo producto está marcado como Boletín (product_tmpl_id.es_boletin),
        el importe base 15% se toma automáticamente del subtotal (sin ISV), es decir:
        cantidad * precio_unit * (1 - descuento%).
        Para las demás líneas, queda en 0.
        """
        for line in self:
            if line.product_id and line.product_id.product_tmpl_id.es_boletin:
                subtotal = line.quantity * line.price_unit
                if line.discount:
                    subtotal = subtotal - (subtotal * line.discount / 100.0)
                line.importe_isv15 = subtotal
            else:
                line.importe_isv15 = 0.0

