# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Campos del módulo original
    exento = fields.Boolean(string='Exento', required=False, default=False)
    is_retention = fields.Boolean(string='Es Retención', default=False)
    tax_retention = fields.Many2one(comodel_name='account.tax', string='Impuesto Retención',
                                    required=False)

    # Campos fiscales para productos (del módulo migrado)
    codigo_sar = fields.Char(string='Código SAR', help='Código del producto según SAR')
    es_exento = fields.Boolean(string='Es Exento', default=False,
                              help='Indica si el producto está exento de impuestos')
    es_exonerado = fields.Boolean(string='Es Exonerado', default=False,
                                 help='Indica si el producto está exonerado de impuestos')
    
    # Campos para reportes
    categoria_fiscal = fields.Selection([
        ('bienes', 'Bienes'),
        ('servicios', 'Servicios'),
        ('ambos', 'Bienes y Servicios')
    ], string='Categoría Fiscal', default='bienes')
    
    # Campos para retenciones
    aplica_retencion = fields.Boolean(string='Aplica Retención', default=False)
    porcentaje_retencion = fields.Float(string='Porcentaje de Retención', default=0.0)

    @api.onchange("exento")
    def _set_taxes_id(self):
        for r in self:
            if r.exento == True:
                r.taxes_id = False

    @api.onchange('es_exento', 'es_exonerado')
    def _onchange_exemption_status(self):
        """Actualiza automáticamente los impuestos según el estado de exención"""
        if self.es_exento:
            # Buscar grupo de impuestos exento
            exempt_tax_group = self.env['account.tax.group'].search([('name', '=', 'Exento')], limit=1)
            if exempt_tax_group:
                exempt_taxes = self.env['account.tax'].search([
                    ('tax_group_id', '=', exempt_tax_group.id),
                    ('company_id', '=', self.company_id.id)
                ])
                self.taxes_id = [(6, 0, exempt_taxes.ids)]
        
        elif self.es_exonerado:
            # Buscar grupo de impuestos exonerado
            exonerated_tax_group = self.env['account.tax.group'].search([('name', '=', 'Exonerado')], limit=1)
            if exonerated_tax_group:
                exonerated_taxes = self.env['account.tax'].search([
                    ('tax_group_id', '=', exonerated_tax_group.id),
                    ('company_id', '=', self.company_id.id)
                ])
                self.taxes_id = [(6, 0, exonerated_taxes.ids)]
        
        else:
            # Aplicar impuestos normales ISV
            isv_taxes = self.env['account.tax'].search([
                ('tipo_impuesto', '=', 'isv'),
                ('company_id', '=', self.company_id.id)
            ])
            self.taxes_id = [(6, 0, isv_taxes.ids)]


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Campos del módulo original
    exento = fields.Boolean(string='Exento', readonly=False, compute='_set_exento')
    is_retention = fields.Boolean(
        string='Es Retención',
        related='product_tmpl_id.is_retention',
        readonly=False  # Permite editar el campo desde product.product
    )

    @api.onchange("exento")
    def _set_taxes_id(self):
        for r in self:
            if r.exento == True:
                r.taxes_id = False

    def _set_exento(self):
        for r in self:
            r.exento = r.product_tmpl_id.exento
