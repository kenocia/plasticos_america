from odoo import models, fields, api


class DocumentTypes(models.Model):
    _name = 'document.type'
    _rec_name = 'document_type'

    document_type = fields.Selection([
        ('curriculum', 'Curriculum'),
        ('fotocopia_cert_studio', 'Fotocopia del título o certificado de estudios'),
        ('fotocopia_identidad', 'Fotocopias de identidad'),
        ('constancia_trabajo', 'Constancia de trabajo si ha tenido'),
        ('copia_luz', 'Copia de recibo de luz'),
        ('recomendaciones', 'Recomendaciones'),
        ('tarjeta_salud', 'Tarjeta de salud'),
        ('rtn', 'RTN'),
        ('antecentes_penales', 'Antecedentes penales'),
        ('antecentes_policiales', 'Antecedentes policiales'),
        ('croquis_direccion_domicilio', 'Croquis de la dirección de su domicilio'),
        ('fotografia_carnet', 'Fotografía tamaño carnet'),
        ('cuenta_bancaria_ficohsa', 'Cuenta bancaria FICOHSA'),
    ], string='Tipo de documento')
    is_required = fields.Boolean(string='Es obligatorio')
    qty = fields.Integer(string='Cantidad de documentos', default=1)
    job_id = fields.Many2one('hr.job', string='Puesto de Trabajo')












