# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campos adicionales para validación fiscal
    # rtn_validated = fields.Boolean(string='RTN Validado', default=False)
    # rtn_validation_date = fields.Date(string='Fecha Validación RTN')
    # rtn_validation_error = fields.Text(string='Error Validación RTN')
    # vendedor_empleado = fields.Many2one("hr.employee", string='Vendedor Empleado', store=True)
    contacto_cliente = fields.Char(string='Contacto', store=True)

    # @api.constrains('vat')
    # def _validate_rtn_format(self):
    #     """Validar formato RTN según SAR de Honduras"""
    #     for partner in self:
    #         if partner.vat and partner.country_id.code == 'HN':
    #             # Limpiar RTN de caracteres especiales
    #             rtn = re.sub(r'[^0-9]', '', partner.vat)
                
    #             # Validar longitud
    #             if len(rtn) != 14:
    #                 partner.rtn_validated = False
    #                 partner.rtn_validation_error = _('RTN debe tener exactamente 14 dígitos')
    #                 raise ValidationError(_('RTN debe tener exactamente 14 dígitos'))
                
    #             # Validar que sean solo números
    #             if not rtn.isdigit():
    #                 partner.rtn_validated = False
    #                 partner.rtn_validation_error = _('RTN debe contener solo números')
    #                 raise ValidationError(_('RTN debe contener solo números'))
                
    #             # Validar dígito verificador
    #             if not self._validate_rtn_check_digit(rtn):
    #                 partner.rtn_validated = False
    #                 partner.rtn_validation_error = _('RTN inválido - dígito verificador incorrecto')
    #                 raise ValidationError(_('RTN inválido - dígito verificador incorrecto'))
                
    #             # Si pasa todas las validaciones
    #             partner.rtn_validated = True
    #             partner.rtn_validation_error = False
    #             partner.rtn_validation_date = fields.Date.today()

    # def _validate_rtn_check_digit(self, rtn):
    #     """
    #     Validar dígito verificador del RTN según algoritmo del SAR
    #     Algoritmo: Multiplicar cada dígito por su peso y sumar, luego calcular módulo 11
    #     """
    #     if len(rtn) != 14:
    #         return False
        
    #     # Pesos para validación RTN (últimos 13 dígitos)
    #     weights = [3, 2, 7, 6, 5, 4, 3, 2, 7, 6, 5, 4, 3]
        
    #     # Tomar los primeros 13 dígitos
    #     rtn_13 = rtn[:13]
    #     check_digit = int(rtn[13])
        
    #     # Calcular suma ponderada
    #     total = 0
    #     for i, digit in enumerate(rtn_13):
    #         total += int(digit) * weights[i]
        
    #     # Calcular dígito verificador esperado
    #     remainder = total % 11
    #     expected_check = 11 - remainder if remainder > 0 else 0
        
    #     # Si el resultado es 10, el dígito verificador debe ser 0
    #     if expected_check == 10:
    #         expected_check = 0
        
    #     return check_digit == expected_check

    # def validate_rtn_manual(self):
    #     """Método para validar RTN manualmente"""
    #     for partner in self:
    #         if partner.vat and partner.country_id.code == 'HN':
    #             try:
    #                 partner._validate_rtn_format()
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'title': _('RTN Válido'),
    #                         'message': _('El RTN %s ha sido validado correctamente.') % partner.vat,
    #                         'type': 'success',
    #                     }
    #                 }
    #             except ValidationError as e:
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'title': _('Error de Validación'),
    #                         'message': str(e),
    #                         'type': 'danger',
    #                     }
    #                 }
    #         else:
    #             return {
    #                 'type': 'ir.actions.client',
    #                 'tag': 'display_notification',
    #                 'params': {
    #                     'title': _('Información'),
    #                     'message': _('Solo se pueden validar RTN de contactos de Honduras.'),
    #                     'type': 'warning',
    #                 }
    #             }

    # @api.onchange('vat')
    # def _onchange_vat_rtn_validation(self):
    #     """Validar RTN cuando cambia el campo VAT"""
    #     if self.vat and self.country_id.code == 'HN':
    #         try:
    #             self._validate_rtn_format()
    #         except ValidationError:
    #             # No lanzar error en onchange, solo mostrar advertencia
    #             pass 