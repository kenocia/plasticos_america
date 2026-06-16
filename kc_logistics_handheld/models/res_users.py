# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

KC_LOGISTICS_HANDHELD_USER_FIELDS = [
    'kc_logistics_handheld_despachos',
    'kc_logistics_handheld_internos',
    'kc_logistics_handheld_fisico',
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    kc_logistics_handheld_despachos = fields.Boolean(
        string='Handheld: Despachos',
        help='Permite abrir el flujo de despachos GS1 desde la app Logística.',
    )
    kc_logistics_handheld_internos = fields.Boolean(
        string='Handheld: Operaciones internas',
        help='Permite abrir transferencias internas GS1 desde la app Logística.',
    )
    kc_logistics_handheld_fisico = fields.Boolean(
        string='Handheld: Toma física previo',
        help='Permite abrir el levantamiento físico previo desde la app Logística.',
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + KC_LOGISTICS_HANDHELD_USER_FIELDS

    def kc_logistics_handheld_permissions(self):
        """Permisos handheld del usuario (lectura fiable en servidor)."""
        self.ensure_one()
        user = self.sudo()
        return {
            'despachos': user.kc_logistics_handheld_despachos,
            'internos': user.kc_logistics_handheld_internos,
            'fisico': user.kc_logistics_handheld_fisico,
        }

    @api.model
    def kc_logistics_handheld_permissions_for_uid(self, uid=None):
        user = self.sudo().browse(uid or self.env.uid)
        return user.kc_logistics_handheld_permissions()
