from odoo import models, fields

class ProjectTask(models.Model):
    _inherit = 'project.task'

    @property
    def SELF_READABLE_FIELDS(self):
        """ Extend readable fields for portal users """
        base_fields = super().SELF_READABLE_FIELDS
        return base_fields | {
            'task_properties',
            # Add other fields you need to make readable
        }

    @property
    def SELF_WRITABLE_FIELDS(self):
        """ Extend writable fields for portal users """
        base_fields = super().SELF_WRITABLE_FIELDS
        return base_fields | {
            'task_properties',
            # Add other fields you need to make writable
        }