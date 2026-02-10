# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountTax(models.Model):
    _inherit = "account.tax"

    # Campos fiscales específicos para Honduras
    codigo_sar = fields.Char(string='Código SAR', help='Código del impuesto según SAR')
    tipo_impuesto = fields.Selection([
        ('isv', 'ISV'),
        ('retencion', 'Retención'),
        ('exento', 'Exento'),
        ('exonerado', 'Exonerado'),
        ('otros', 'Otros')
    ], string='Tipo de Impuesto', default='isv')
    
    # Campos para reportes fiscales
    es_deducible = fields.Boolean(string='Es Deducible', default=True, 
                                 help='Indica si el impuesto es deducible para efectos fiscales')
    aplica_retencion = fields.Boolean(string='Aplica Retención', default=False,
                                     help='Indica si este impuesto aplica retención')
    
    # Campo para identificar impuestos de retención
    is_retention = fields.Boolean(string='Es Retención', default=False,
                                     help='Indica si este impuesto es de retención')
    
    @api.model
    def _get_fiscal_taxes(self, tax_type=None):
        """Obtiene impuestos fiscales según el tipo especificado"""
        domain = [('tipo_impuesto', '!=', False)]
        if tax_type:
            domain.append(('tipo_impuesto', '=', tax_type))
        return self.search(domain)
    
    def get_isv_taxes(self):
        """Obtiene impuestos ISV (15% y 18%)"""
        return self._get_fiscal_taxes('isv')
    
    def get_retention_taxes(self):
        """Obtiene impuestos de retención"""
        return self._get_fiscal_taxes('retencion')
    
    def get_exempt_taxes(self):
        """Obtiene impuestos exentos"""
        return self._get_fiscal_taxes('exento')
    
    def get_exonerated_taxes(self):
        """Obtiene impuestos exonerados"""
        return self._get_fiscal_taxes('exonerado')