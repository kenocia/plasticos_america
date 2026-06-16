# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class HrContract(models.Model):
    _inherit = 'hr.contract'

    contract_document_ids = fields.One2many('contract.documents', string='Documentos anexados',
                                            inverse_name='employee_id')

    # @api.constrains('contract_document_ids')
    # def _check_required_documents(self):
    #     for contract in self:
    #         required_document_types = contract.job_id.document_type_ids.filtered('is_required')
    #         attached_document_types = contract.contract_document_ids.mapped('document_type')
    #
    #         missing_document_types = required_document_types - attached_document_types
    #         if missing_document_types:
    #             missing_names = ', '.join(missing_document_types.mapped('document_type'))
    #             message = _("Faltan los siguientes documentos requeridos: %s") % missing_names
    #             raise UserError(message)


class ContractDocuments(models.Model):
    _name = 'contract.documents'

    name = fields.Char(string='Nombre del documento')
    document_type = fields.Many2one('document.type', string='Tipo de documento')
    attachment_ids = fields.Many2many('ir.attachment', 'doc_attach_rel', 'doc_id', 'attach_id3', string="Adjunto",
                                      help='Puedes adjuntar una copia de tu documento', copy=False)
    employee_id = fields.Many2one(string='Employee', comodel_name='hr.employee')

