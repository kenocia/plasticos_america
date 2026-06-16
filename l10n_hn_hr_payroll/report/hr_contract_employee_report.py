# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrContractEmployeeReport(models.Model):
    _inherit = "hr.contract.employee.report"

    job_id = fields.Many2one('hr.job', readonly=True, string='Job Position')
    count_employee_permanently = fields.Integer('Employee Permanently', readonly=True)
    count_employee_temporary = fields.Integer('Employee Temporality', readonly=True)
    count_employee_recruit_perm = fields.Integer('# Temporary Employees Recruit', readonly=True)
    count_employee_recruit_temp = fields.Integer('# Permanently Employees Recruit', readonly=True)

    def _query(self, fields='', from_clause='', outer=''):
        type_id = [self.env.ref('hr.contract_type_permanent'),
                   self.env.ref('hr.contract_type_temporary')]
        fields += f""",
        c.job_id as job_id,
        CASE
         WHEN date_part('month', c.date_start) = date_part('month', serie) 
                AND date_part('year', c.date_start) = date_part('year', serie)
                AND c.contract_type_id = {type_id and type_id[0].id}
                    THEN 1 ELSE 0 END as count_employee_permanently,
        CASE
         WHEN date_part('month', c.date_start) = date_part('month', serie)
                AND date_part('year', c.date_start) = date_part('year', serie)
                AND c.contract_type_id = {type_id and type_id[1].id}
                    THEN 1 ELSE 0 END as count_employee_temporary,
                    
        CASE WHEN date_part('month', c.date_start) = date_part('month', serie) 
            AND date_part('year', c.date_start) = date_part('year', serie) AND j.no_of_recruit_perm > 0
            AND j.contract_type_id = {type_id and type_id[0].id}
                THEN j.no_of_recruit_perm ELSE 0 END as count_employee_recruit_perm,
        
        CASE WHEN date_part('month', c.date_start) = date_part('month', serie) 
            AND date_part('year', c.date_start) = date_part('year', serie) AND j.no_of_recruit_temp > 0
            AND j.contract_type_id = {type_id and type_id[1].id}
                THEN j.no_of_recruit_temp ELSE 0 END as count_employee_recruit_temp
        """

        from_clause += """
            LEFT JOIN hr_job j ON j.id = c.job_id
        """

        return super(HrContractEmployeeReport, self)._query(fields, from_clause, outer)
