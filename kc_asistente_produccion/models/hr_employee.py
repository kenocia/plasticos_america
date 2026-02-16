# -*- coding: utf-8 -*-

import hashlib
import hmac
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pin_hash = fields.Char(
        string='PIN (hash)',
        copy=False,
        help='Hash del PIN para acceso al asistente de producción. No se almacena el PIN en claro.',
    )

    def check_pin(self, pin):
        """Comparación segura del PIN. No registrar el PIN en logs."""
        self.ensure_one()
        if not pin or not isinstance(pin, str):
            return False
        pin_clean = pin.strip()
        if not pin_clean or not self.pin_hash:
            return False
        try:
            # Hash almacenado: hex(salt + hash). Salt primeros 32 chars hex = 16 bytes.
            stored = self.pin_hash
            if len(stored) < 32:
                return False
            salt_hex = stored[:32]
            expected_hash = stored[32:]
            salt = bytes.fromhex(salt_hex)
            computed = hashlib.pbkdf2_hmac('sha256', pin_clean.encode('utf-8'), salt, 100000).hex()
            return hmac.compare_digest(computed, expected_hash)
        except Exception:
            return False

    def set_pin(self, pin):
        """Establece el PIN generando salt y hash. No guardar PIN en logs."""
        self.ensure_one()
        if not pin or not isinstance(pin, str):
            raise UserError(_('El PIN no puede estar vacío.'))
        pin_clean = pin.strip()
        if len(pin_clean) < 4:
            raise UserError(_('El PIN debe tener al menos 4 caracteres.'))
        salt = secrets.token_bytes(16)
        h = hashlib.pbkdf2_hmac('sha256', pin_clean.encode('utf-8'), salt, 100000).hex()
        self.pin_hash = salt.hex() + h

    def action_set_pin_wizard(self):
        self.ensure_one()
        return {
            'name': _('Establecer PIN'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.pin.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id},
        }
