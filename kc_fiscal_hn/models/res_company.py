from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Campo para información bancaria
    banking_information_image = fields.Binary(
        string='Información Bancaria',
        help='Imagen con la información bancaria de la compañía para mostrar en reportes'
    )
    
    # Campo para términos y condiciones
    terms_conditions_image = fields.Binary(
        string='Términos y Condiciones',
        help='Imagen con los términos y condiciones de la compañía para mostrar en reportes'
    ) 