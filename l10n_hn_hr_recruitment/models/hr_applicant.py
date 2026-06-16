# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    is_internal = fields.Boolean(string="Es interno")
    process_state = fields.Selection([('new', 'Nuevo'), ('processed', 'Procesado')], string='Estado del candidato', default='new')
    
    firstname = fields.Char("First name", size=20, required=True)
    firstname2 = fields.Char("Second name", size=20)
    lastname = fields.Char("Last name", size=20, required=True)
    lastname2 = fields.Char("Second last name", size=20)
    identification_id = fields.Char('Identification No', required=True)
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict', domain="[('country_id', '=?', country_id)]", required=True)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', default=lambda self: self.env['res.country'].search([('code', '=', 'HN')], limit=1))
    city = fields.Char("City", required=True)
    street = fields.Char("Street", required=True)
    street2 = fields.Char("Street2")


    def _get_similar_applicants_domain(self):
        res = super(HrApplicant, self)._get_similar_applicants_domain()
        
        # Remove the filter of partner_phone_sanitized and partner_mobile_sanitized since the phone number cannot be a field to identify a candidate
        
        # Agregar el filtro de identificación para buscar candidatos similares
        if self.identification_id:
            res = expression.OR([res, [('identification_id', '=', self.identification_id)]])

        return res
    
    @api.depends('email_from', 'partner_mobile_sanitized', 'partner_phone_sanitized', 'identification_id')
    def _compute_application_count(self):
        super(HrApplicant, self)._compute_application_count()
        
        if not any(self._ids):
            for applicant in self:
                domain = applicant._get_similar_applicants_domain()
                if domain:
                    applicant.application_count = max(0, self.env["hr.applicant"].with_context(active_test=False).search_count(domain) - 1)
                else:
                    applicant.application_count = 0
            return
        
        self.flush_recordset(['email_normalized', 'partner_phone_sanitized', 'partner_mobile_sanitized'])
        self.env.cr.execute("""
            SELECT
                id,
                (
                    SELECT COUNT(*)
                    FROM hr_applicant AS sub
                    WHERE a.id != sub.id
                     AND ((a.email_normalized <> '' AND sub.email_normalized = a.email_normalized)
                       OR (a.partner_mobile_sanitized <> '' AND a.partner_mobile_sanitized = sub.partner_mobile_sanitized)
                       OR (a.partner_mobile_sanitized <> '' AND a.partner_mobile_sanitized = sub.partner_phone_sanitized)
                       OR (a.partner_phone_sanitized <> '' AND a.partner_phone_sanitized = sub.partner_mobile_sanitized)
                       OR (a.partner_phone_sanitized <> '' AND a.partner_phone_sanitized = sub.partner_phone_sanitized))
                       OR (a.identification_id <> '' AND sub.identification_id = a.identification_id)
                ) AS similar_applicants
            FROM hr_applicant AS a
            WHERE id IN %(ids)s
        """, {'ids': tuple(self._origin.ids)})
        query_results = self.env.cr.dictfetchall()
        mapped_data = {result['id']: result['similar_applicants'] for result in query_results}
        for applicant in self:
            applicant.application_count = mapped_data.get(applicant.id, 0)