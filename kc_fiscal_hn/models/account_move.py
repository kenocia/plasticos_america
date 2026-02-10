# Copyright 2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
import logging
import math

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    # Campo de motivo de emisión para notas de crédito
    motivo_emision = fields.Selection([
        ('anulacion', 'Anulación'),
        ('devolucion', 'Devolución'),
        ('descuento', 'Descuento')
    ], string='Motivo de Emisión', 
       help='Motivo por el cual se emite la nota de crédito',
       invisible="move_type not in ['out_refund', 'in_refund']")

    # Campos fiscales de Honduras
    cai_proveedor = fields.Char(string='CAI Proveedor')
    correlativo_proveedor = fields.Char(
        string='N° Correlativo Proveedor', 
        help='Número de documento del proveedor (se usará como referencia)'
    )
    femision_proveedor = fields.Char(string='Fecha Emisión')
    cai = fields.Char(string='CAI', help='Clave de Autorización de Impresión')
    fechaLimiteEmision = fields.Date(string='Fecha límite de emisión',help='Fecha límite de emisión de facturas')
    numeroInicial = fields.Char(string='Número inicial', help='Número inicial de facturación', )
    numeroFinal = fields.Char(string='Número final', help='Número final de facturación', )
    totalAmountString = fields.Char(string='Monto Total', help='Monto Total', )
    noOrdenCompraExenta = fields.Char(string='No OC exenta', help='Número de orden de compra exenta')
    noConsRegistroExonerado = fields.Char(string='No cons. reg. Exonerado', help='Número constancia de registro exonerado')
    noIdentificacionRegistroSAG = fields.Char(string='No ident. reg. SAG', help='Número identificación registro SAG')
    sale_order_id = fields.Many2one('sale.order', string='Pedido de Venta', compute='_get_saleorder', store=True)
    exonerado = fields.Boolean(string='Exonerado', required=False, default=False)
    exento = fields.Boolean(string='Exento', required=False, default=False)
    amount_discount = fields.Monetary(string='Descuento', store=True, compute='_compute_discount', readonly=True, currency_field='currency_id', digits=(16, 4))
    amount_exento = fields.Monetary(string='Exento', store=True, compute='_compute_exent', readonly=True, currency_field='currency_id', digits=(16, 4))
    amount_exonerado = fields.Monetary(string='Exonerado', store=True, compute='_compute_exent', readonly=True, currency_field='currency_id', digits=(16, 4))
    amount_isv15 = fields.Monetary(string='Isv 15%', store=True, compute='_compute_importe_gravado', readonly=True, currency_field='currency_id', digits=(16, 4))
    gravado_isv15 = fields.Monetary(string='Importe Gravado 15%', store=True, compute='_compute_importe_gravado', readonly=True, currency_field='currency_id', digits=(16, 4))
    amount_isv18 = fields.Monetary(string='Isv 18%', store=True, compute='_compute_importe_gravado', readonly=True, currency_field='currency_id', digits=(16, 4))
    gravado_isv18 = fields.Monetary(string='Importe Gravado 18%', store=True, compute='_compute_importe_gravado', readonly=True, currency_field='currency_id', digits=(16, 4))
    depto = fields.Many2one("res.country.state", string='Departamento', related='partner_id.state_id', store=True)
    class_document_sar = fields.Selection(string='Clase de Documento SAR', selection=[('FA', 'FA-FACTURA'), ('OC', 'OC-OTROS COMPROBANTES DE PAGO')], required=False, )
    montos_sar = fields.Selection(string='Montos SAR', selection=[('costo', 'Monto al Costo'), ('gasto', 'Monto al Gasto'), ('no_deducible', 'Valor no deducible')], default='gasto', required=False, )
    document_fiscal = fields.Selection(string='Documento Fiscal', related='journal_id.document_fiscal', required=False, store=True)
    invoice_retention = fields.Many2one("account.move", string="Factura de retención", domain="[('move_type', '=', 'in_invoice'), ('partner_id', '=', partner_id)]")
    original_print = fields.Boolean(string='Original', default=True)
    vendedor_empleado = fields.Many2one("hr.employee", string='Vendedor Empleado')

    # Campos adicionales para control fiscal mejorado
    fiscal_validation_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('validated', 'Validado'),
        ('error', 'Error')
    ], string='Estado Validación Fiscal', default='pending', readonly=True)
    fiscal_validation_message = fields.Text(string='Mensaje Validación Fiscal', readonly=True)
    requires_fiscal_numbering = fields.Boolean(string='Requiere Numeración Fiscal', compute='_compute_requires_fiscal_numbering', store=True)
    base_imponible_total = fields.Monetary(string='Base Imponible Total', compute='_compute_base_imponible', store=True, readonly=True, currency_field='currency_id', digits=(16, 4))
    isv_total = fields.Monetary(string='ISV Total', compute='_compute_isv_total', store=True, readonly=True, currency_field='currency_id', digits=(16, 4))
    
    # Campo computado para mostrar la referencia completa
    referencia_completa = fields.Char(
        string='Referencia Completa',
        compute='_compute_referencia_completa',
        store=True,
        help='Referencia completa que incluye el número del documento y el correlativo del proveedor'
    )
    
    # Campo para controlar importación de documentos históricos
    is_import = fields.Boolean(
        string='Es Importado',
        default=False,
        help='Marcar como True para documentos importados, no requieren correlativo fiscal'
    )

    # Campos DMC: Importación / FYDUCA
    dmc_tipo = fields.Selection(
        selection=[
            ('importacion', 'Importación DMC'),
            ('fiduca', 'FYDUCA DMC'),
        ],
        string='Tipo DMC'
    )
    dmc_pasaporte_identificacion_ca = fields.Char(string='Pasaporte o identificación CA')
    dmc_identificador_tributario_mercantil = fields.Char(string='Nº Identificador tributario mercantil')
    dmc_numero_fyduca = fields.Char(string='N.º FYDUCA')
    dmc_numero_dua = fields.Char(string='N.º DUA')

    # def action_print_document(self):
    #     """
    #     Método personalizado para imprimir documentos y marcar original_print como True
    #     """
    #     self.ensure_one()
        
    #     # Marcar el documento como impreso
    #     self.write({'original_print': True})
        
    #     # Registrar la acción de impresión
    #     _logger.info(f"Documento {self.name} marcado como impreso")
        
    #     # Retornar la acción de impresión del reporte correspondiente
    #     if self.move_type == 'out_invoice':
    #         return self.env.ref('kc_fiscal_hn.report_invoice_sar').report_action(self)
    #     elif self.move_type == 'out_refund':
    #         return self.env.ref('kc_fiscal_hn.report_credit_note').report_action(self)
    #     elif self.move_type == 'in_invoice':
    #         return self.env.ref('kc_fiscal_hn.report_boleta_compra').report_action(self)
    #     else:
    #         # Para otros tipos de documentos, usar el reporte por defecto
    #         return self.env.ref('account.action_report_invoice').report_action(self)

    # def action_print_original(self):
    #     """
    #     Método específico para imprimir original
    #     """
    #     self.ensure_one()
        
    #     # Marcar el documento como impreso
    #     self.write({'original_print': True})
        
    #     # Registrar la acción de impresión
    #     _logger.info(f"Documento {self.name} marcado como impreso (original)")
        
    #     # Retornar la acción de impresión del reporte correspondiente
    #     if self.move_type == 'out_invoice':
    #         return self.env.ref('kc_fiscal_hn.report_invoice_sar').report_action(self)
    #     elif self.move_type == 'out_refund':
    #         return self.env.ref('kc_fiscal_hn.report_credit_note').report_action(self)
    #     elif self.move_type == 'in_invoice':
    #         return self.env.ref('kc_fiscal_hn.report_boleta_compra').report_action(self)
    #     else:
    #         # Para otros tipos de documentos, usar el reporte por defecto
    #         return self.env.ref('account.action_report_invoice').report_action(self)


    # We must by-pass this constraint of sequence.mixin
    def _constrains_date_sequence(self):
        return True

    def _is_end_of_seq_chain(self):
        invoices_no_gap_sequences = self.filtered(
            lambda inv: inv.journal_id.sequence_id.implementation == "no_gap"
        )
        invoices_other_sequences = self - invoices_no_gap_sequences
        if not invoices_other_sequences and invoices_no_gap_sequences:
            return False
        return super(AccountMove, invoices_other_sequences)._is_end_of_seq_chain()

    @api.depends('invoice_line_ids.discount', 'invoice_line_ids.price_unit',
                 'invoice_line_ids.quantity', 'invoice_line_ids.price_subtotal',
                 'invoice_line_ids.product_id')
    def _compute_discount(self):
        for inv in self:
            discount_total = 0.0
            for line in inv.invoice_line_ids:
                if line.discount:
                    subtotal_line = line.quantity * line.price_unit
                    discount_line = (subtotal_line * line.discount) / 100
                    discount_total += discount_line
                elif line.product_id.product_tmpl_id.default_code == 'Desc':
                    discount_total += abs(line.price_subtotal)
            inv.amount_discount = round(discount_total, 2)

    @api.depends('invoice_line_ids.tax_ids', 'invoice_line_ids.discount',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity',
                 'invoice_line_ids.price_subtotal')
    def _compute_exent(self):
        for inv in self:
            exento = 0.0
            exonerado = 0.0

            for line in inv.invoice_line_ids:
                # Calcular el subtotal de la línea
                subtotal = line.quantity * line.price_unit
                total = subtotal - ((subtotal * line.discount) / 100) if line.discount else subtotal

                # Normalizar nombre de grupos para robustez
                def _name(n):
                    return (n or '').strip().lower()

                # Verificar si la línea está exenta (grupo con nombre que contenga 'exento') o si no tiene impuestos asignados
                # Tratamos líneas sin impuestos como exentas para efectos de totales SAR
                if (not line.tax_ids) or any('exento' in _name(tax.tax_group_id.name) for tax in line.tax_ids):
                    exento += total

                # Verificar si la línea está exonerada (grupo cuyo nombre contenga 'exonerado')
                if any('exonerado' in _name(tax.tax_group_id.name) for tax in line.tax_ids):
                    exonerado += total

                # # Verificar si la línea está exonerada (código de producto específico)
                # if line.product_id.product_tmpl_id.default_code == 'Desc':  # Cambia 'Desc' por el código que identifica productos exonerados
                #     exonerado += total

            # Asignar los valores acumulados a los campos correspondientes
            inv.amount_exento = round(exento, 2)
            inv.amount_exonerado = round(exonerado, 2)

    @api.depends('invoice_line_ids.tax_ids', 'invoice_line_ids.discount',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity',
                 'invoice_line_ids.price_subtotal')
    def _compute_importe_gravado(self):
        """Cálculo mejorado de ISV según SAR de Honduras"""
        for inv in self:
            isv15 = 0.0
            isv18 = 0.0
            importe15 = 0.0
            importe18 = 0.0

            for line in inv.invoice_line_ids:
                # Calcular base imponible correctamente
                subtotal_line = line.quantity * line.price_unit
                
                # Aplicar descuento si existe
                if line.discount:
                    discount_amount = (subtotal_line * line.discount) / 100
                    base_imponible = subtotal_line - discount_amount
                else:
                    base_imponible = subtotal_line

                # Verificar si la línea está exenta o exonerada
                is_exempt = any(tax.tax_group_id.name == 'Exento' for tax in line.tax_ids)
                is_exonerated = any(tax.tax_group_id.name == 'Exonerado' for tax in line.tax_ids)
                
                # Solo calcular ISV si no está exenta ni exonerada
                if not is_exempt and not is_exonerated:
                    # Calcular ISV según SAR (redondeo a 2 decimales)
                    for tax in line.tax_ids:
                        if tax.amount == 15:
                            isv_line = self._round_sar(base_imponible * 0.15)
                            isv15 += isv_line
                            importe15 += base_imponible
                        elif tax.amount == 18:
                            isv_line = self._round_sar(base_imponible * 0.18)
                            isv18 += isv_line
                            importe18 += base_imponible

            # Aplicar redondeo final según SAR
            inv.amount_isv15 = self._round_sar(isv15)
            inv.gravado_isv15 = self._round_sar(importe15)
            inv.amount_isv18 = self._round_sar(isv18)
            inv.gravado_isv18 = self._round_sar(importe18)
    
    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.tax_ids', 'amount_discount', 'amount_exento', 'amount_exonerado')
    def _compute_base_imponible(self):
        """Calcular base imponible total - solo líneas gravadas"""
        for inv in self:
            base_imponible = 0.0
            for line in inv.invoice_line_ids:
                # Calcular el subtotal de la línea
                subtotal_line = line.quantity * line.price_unit
                
                # Aplicar descuento si existe
                if line.discount:
                    discount_amount = (subtotal_line * line.discount) / 100
                    total_line = subtotal_line - discount_amount
                else:
                    total_line = subtotal_line

                # Verificar si la línea está exenta o exonerada
                def _name(n):
                    return (n or '').strip().lower()
                is_exempt = any('exento' in _name(tax.tax_group_id.name) for tax in line.tax_ids)
                is_exonerated = any('exonerado' in _name(tax.tax_group_id.name) for tax in line.tax_ids)
                has_taxes = bool(line.tax_ids)
                
                # Solo incluir en base imponible si la línea tiene impuestos y NO está exenta ni exonerada
                # Así evitamos sumar líneas sin impuestos (consideradas exentas a efectos de totales)
                if has_taxes and not is_exempt and not is_exonerated:
                    base_imponible += total_line
                else:
                    pass
            
            inv.base_imponible_total = self._round_sar(base_imponible)
    
    @api.depends('amount_isv15', 'amount_isv18')
    def _compute_isv_total(self):
        """Calcular ISV total"""
        for inv in self:
            inv.isv_total = self._round_sar(inv.amount_isv15 + inv.amount_isv18)
    
    @api.depends('amount_total')
    def _compute_requires_fiscal_numbering(self):
        """Determinar si requiere numeración fiscal según SAR"""
        for inv in self:
            # Según SAR: Facturas menores a L. 500 no requieren numeración fiscal
            if inv.move_type in ['out_invoice', 'out_refund']:
                inv.requires_fiscal_numbering = inv.amount_total >= 500.0
            else:
                inv.requires_fiscal_numbering = False
    
    def _round_sar(self, amount):
        """Redondeo según SAR de Honduras (redondeo matemático a 2 decimales)"""
        return round(amount, 2)
    
    def _validate_fiscal_amounts(self):
        """Validar montos según requerimientos del SAR"""
        for inv in self:
            if inv.move_type in ['out_invoice', 'out_refund']:
                # Omitir validaciones fiscales para importaciones históricas
                if inv.is_import:
                    _logger.info("Omitiendo validaciones fiscales para movimiento %s - es importación histórica", inv.id)
                    continue
                
                # Validar monto mínimo para facturación fiscal
                if inv.amount_total < 500.0 and inv.requires_fiscal_numbering:
                    raise ValidationError(_('Facturas menores a L. 500 no requieren numeración fiscal'))
                
                # Validar que los montos sean positivos
                if inv.amount_total < 0:
                    raise ValidationError(_('El monto total no puede ser negativo'))
                
                # Validar que ISV sea correcto
                calculated_isv = inv.amount_isv15 + inv.amount_isv18
                if abs(calculated_isv - inv.isv_total) > 0.01:
                    raise ValidationError(_('El ISV total no coincide con la suma de ISV 15% y 18%'))
    
    def validate_fiscal_invoice(self):
        """Validar factura fiscal completa"""
        for inv in self:
            try:
                # Omitir validaciones fiscales para importaciones históricas
                if inv.is_import:
                    _logger.info("Omitiendo validación fiscal completa para movimiento %s - es importación histórica", inv.id)
                    inv.fiscal_validation_status = 'validated'
                    inv.fiscal_validation_message = _('Documento importado del historial - validación fiscal omitida')
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Documento Importado'),
                            'message': _('El documento ha sido marcado como importación histórica.'),
                            'type': 'info',
                        }
                    }
                
                # Validar montos
                inv._validate_fiscal_amounts()
                
                # Validar campos obligatorios
                if inv.move_type in ['out_invoice', 'out_refund']:
                    if not inv.partner_id.vat and inv.partner_id.country_id.code == 'HN':
                        raise ValidationError(_('El cliente debe tener RTN válido'))
                    
                    if inv.requires_fiscal_numbering and not inv.cai:
                        raise ValidationError(_('Facturas que requieren numeración fiscal deben tener CAI'))
                
                # Marcar como validada
                inv.fiscal_validation_status = 'validated'
                inv.fiscal_validation_message = _('Factura validada correctamente')
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Factura Válida'),
                        'message': _('La factura ha sido validada correctamente.'),
                        'type': 'success',
                    }
                }
                
            except ValidationError as e:
                inv.fiscal_validation_status = 'error'
                inv.fiscal_validation_message = str(e)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error de Validación'),
                        'message': str(e),
                        'type': 'danger',
                    }
                }

    @api.depends("sale_order_count")
    def _get_saleorder(self):
        for move in self:
            move.sale_order_id = move.line_ids.sale_line_ids.order_id

    def _set_next_sequence(self):
        """
        Sobrescribimos _set_next_sequence para manejar secuencias fiscales.
        - Para secuencias fiscales (is_fiscal = True): Asignar "/" temporalmente
        - Para secuencias no fiscales: Comportamiento normal de Odoo
        - Para importaciones históricas: Omitir generación de correlativo fiscal
        """
        for move in self:
            if move.move_type == 'out_refund':
                _logger.info(
                    "NC _set_next_sequence: move %s diario %s necesita_fiscal=%s is_import=%s",
                    move.id, move.journal_id.display_name,
                    move.journal_id.needs_fiscal_sequence(move.move_type),
                    move.is_import,
                )
            # ✅ CONDICIÓN: Omitir generación de correlativo para importaciones históricas
            if move.is_import:
                _logger.info("Omitiendo generación de correlativo fiscal para movimiento %s - es importación histórica", move.id)
                # Para importaciones históricas, usar comportamiento normal de Odoo sin secuencia fiscal
                super(AccountMove, move)._set_next_sequence()
                continue
            
            # ✅ CONDICIÓN PRINCIPAL: Solo procesar si el diario necesita secuencia fiscal
            if not move.journal_id.needs_fiscal_sequence(move.move_type):
                # Para diarios que no requieren secuencia fiscal, usar comportamiento normal de Odoo
                super(AccountMove, move)._set_next_sequence()
                _logger.debug("Diario no requiere secuencia fiscal para movimiento %s - usando comportamiento normal de Odoo", move.id)
                if move.move_type in ("in_invoice", "in_refund"):
                    _logger.info("Compras sin secuencia fiscal: movimiento %s (diario %s, tipo %s)", move.id, move.journal_id.display_name, move.move_type)
                continue

            # ✅ OBTENER SECUENCIA FISCAL APROPIADA
            sequence = move.journal_id.get_fiscal_sequence(move.move_type)
            if not sequence:
                if move.move_type == 'out_refund':
                    _logger.warning(
                        "NC _set_next_sequence: sin secuencia fiscal (diario %s, tipo %s)",
                        move.journal_id.display_name, move.move_type,
                    )
                # Si no hay secuencia fiscal configurada, usar comportamiento normal de Odoo
                super(AccountMove, move)._set_next_sequence()
                _logger.debug("No hay secuencia fiscal configurada para movimiento %s - usando comportamiento normal de Odoo", move.id)
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    move.message_post(body=_(
                        "Compras sin secuencia fiscal: el diario '%s' no tiene una secuencia fiscal configurada. "
                        "Configure el Documento Fiscal del diario y una secuencia con 'Es Secuencia Fiscal' marcada."
                    ) % move.journal_id.display_name)
                continue
            
            # ✅ LÓGICA: Solo el campo is_fiscal determina el comportamiento
            if sequence.is_fiscal:
                # Para secuencias fiscales, asignar "/" temporalmente
                # El número real se asignará en _post
                move.name = "/"
                _logger.debug("Secuencia fiscal detectada para movimiento %s - asignando '/' temporalmente", move.id)
                if move.move_type == 'out_refund':
                    _logger.info(
                        "NC _set_next_sequence: asignado '/' (secuencia %s)",
                        sequence.display_name,
                    )
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    _logger.info("Compras con secuencia fiscal: movimiento %s marcado '/' (diario %s)", move.id, move.journal_id.display_name)
            else:
                # Para secuencias no fiscales, usar el comportamiento normal de Odoo
                super(AccountMove, move)._set_next_sequence()
                _logger.debug("Secuencia no fiscal para movimiento %s - usando comportamiento normal de Odoo", move.id)
                if move.move_type == 'out_refund':
                    _logger.info(
                        "NC _set_next_sequence: secuencia NO fiscal (secuencia %s)",
                        sequence.display_name,
                    )
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    _logger.info("Compras con secuencia NO fiscal: movimiento %s (diario %s)", move.id, move.journal_id.display_name)
                    move.message_post(body=_(
                        "Compras sin secuencia fiscal: la secuencia del diario '%s' no está marcada como fiscal. "
                        "Marque 'Es Secuencia Fiscal' en la secuencia."
                    ) % move.journal_id.display_name)

    def _post(self, soft=True):
        """
        Sobrescribimos el método _post para controlar la generación de secuencias fiscales.
        - Para secuencias fiscales (is_fiscal = True): Genera la secuencia fiscal SAR.
        - Para secuencias no fiscales: Se omite, ya que se manejan en _set_next_sequence.
        """
        # Validar facturas fiscales antes de publicar
        for move in self:
            if move.move_type in ['out_invoice', 'out_refund']:
                # Omitir validaciones fiscales para importaciones históricas
                if move.is_import:
                    _logger.info("Omitiendo validación fiscal en _post para movimiento %s - es importación histórica", move.id)
                    continue
                
                try:
                    move._validate_fiscal_amounts()
                except ValidationError as e:
                    move.fiscal_validation_status = 'error'
                    move.fiscal_validation_message = str(e)
                    raise e
        
        posted = super()._post(soft)  # Llamamos al super() al inicio

        # ✅ ACTUALIZAR totalAmountString para TODAS las facturas confirmadas
        # Esto debe hacerse antes de procesar las secuencias fiscales
        # para asegurar que siempre se actualice, incluso si la factura ya tiene un número fiscal
        for move in self:
            if move.state == 'posted' and move.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'in_receipt']:
                if move.amount_total:
                    move.totalAmountString = move.numero_to_letras(move.amount_total)
                    _logger.debug("Actualizado totalAmountString para factura %s (name: %s, amount_total: %s): %s", 
                                 move.id, move.name, move.amount_total, move.totalAmountString)

        for move in self:
            if move.move_type == 'out_refund':
                _logger.info(
                    "NC _post: move %s estado %s name=%s diario %s necesita_fiscal=%s is_import=%s",
                    move.id, move.state, move.name, move.journal_id.display_name,
                    move.journal_id.needs_fiscal_sequence(move.move_type),
                    move.is_import,
                )
            # ✅ CONDICIÓN: Omitir generación de secuencia fiscal para importaciones históricas
            if move.is_import:
                _logger.info("Omitiendo generación de secuencia fiscal para movimiento %s - es importación histórica", move.id)
                continue
            
            # ✅ CONDICIÓN PRINCIPAL: Solo procesar si el diario necesita secuencia fiscal
            if not move.journal_id.needs_fiscal_sequence(move.move_type):
                _logger.debug("Omitiendo generación de secuencia fiscal para movimiento %s - diario no requiere secuencia fiscal", move.id)
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    _logger.info("Compras sin secuencia fiscal en _post: movimiento %s (diario %s, tipo %s)", move.id, move.journal_id.display_name, move.move_type)
                continue

            # ✅ OBTENER SECUENCIA FISCAL APROPIADA
            sequence = move.journal_id.get_fiscal_sequence(move.move_type)
            if not sequence:
                if move.move_type == 'out_refund':
                    _logger.warning(
                        "NC _post: sin secuencia fiscal (diario %s, tipo %s)",
                        move.journal_id.display_name, move.move_type,
                    )
                _logger.debug("Omitiendo generación de secuencia fiscal para movimiento %s - no hay secuencia fiscal configurada", move.id)
                continue
            
            if not sequence.is_fiscal:
                _logger.debug("Omitiendo generación de secuencia fiscal para movimiento %s - secuencia no es fiscal", move.id)
                if move.move_type == 'out_refund':
                    _logger.info(
                        "NC _post: secuencia NO fiscal (secuencia %s)",
                        sequence.display_name,
                    )
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    _logger.info("Compras con secuencia NO fiscal en _post: movimiento %s (diario %s)", move.id, move.journal_id.display_name)
                continue

            # ✅ CONDICIÓN: Solo procesar si el movimiento tiene name = "/" (asignado temporalmente)
            if move.name != "/":
                _logger.debug("Omitiendo generación de secuencia fiscal para movimiento %s - ya tiene nombre: %s", move.id, move.name)
                if move.move_type == 'out_refund':
                    _logger.info("NC _post: no tiene '/' (name %s)", move.name)
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    _logger.info("Compras sin '/' en _post: movimiento %s (name %s)", move.id, move.name)
                continue

            # ✅ CONDICIÓN: Solo procesar si está en estado 'posted'
            if move.state != 'posted':
                _logger.debug("Omitiendo generación de secuencia fiscal para movimiento %s - no está posted", move.id)
                if move.move_type == 'out_refund':
                    _logger.info("NC _post: no esta posted (state %s)", move.state)
                if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                    _logger.info("Compras no posted en _post: movimiento %s (state %s)", move.id, move.state)
                continue

            # ✅ CONDICIÓN: Omitir si es un asiento de inventario (stock valuation)
            if move.stock_valuation_layer_ids:
                _logger.info("Omitiendo generación de secuencia fiscal para movimiento %s - es asiento de inventario", move.id)
                continue

            # ✅ CONDICIÓN: Omitir si es un asiento de pago
            # Un asiento de pago real es:
            # 1. Un movimiento de tipo 'entry' con líneas relacionadas a un pago
            # 2. O un movimiento que está directamente relacionado con account.payment
            # NO usar solo payment_reference porque puede estar en facturas normales
            is_payment_entry = (
                move.move_type == 'entry' and 
                (move.line_ids.filtered(lambda l: l.payment_id) or 
                 hasattr(move, 'payment_id') and move.payment_id)
            )
            if is_payment_entry:
                _logger.info("Omitiendo generación de secuencia fiscal para movimiento %s - es asiento de pago", move.id)
                continue

            # ✅ CONDICIÓN: Omitir si es un asiento de conciliación bancaria
            if move.statement_line_id:
                _logger.info("Omitiendo generación de secuencia fiscal para movimiento %s - es asiento de conciliación bancaria", move.id)
                continue

            # ✅ CONDICIÓN: Omitir si es un asiento de ajuste
            if move.move_type in ('entry', 'out_invoice', 'in_invoice') and not move.invoice_line_ids:
                _logger.info("Omitiendo generación de secuencia fiscal para movimiento %s - es asiento de ajuste", move.id)
                continue

            # ✅ PROCESAR SECUENCIA FISCAL
            if sequence.use_date_range:
                date = move.invoice_date or move.date
                
                # Usar la nueva validación inteligente
                sequence_status = sequence.validate_sequence_continuity(date)
                
                if not sequence_status['valid']:
                    # Solo log de error, sin bloquear operaciones
                    _logger.error("Error de validación fiscal para secuencia %s: %s", sequence.name, sequence_status['message'])
                    continue
                
                # Obtener rango actual
                current_range = sequence_status.get('current_range')
                if not current_range:
                    # Buscar rango futuro
                    next_range = sequence.get_next_available_range(date)
                    if next_range:
                        _logger.warning("No hay rango para fecha %s, pero existe rango futuro desde %s", date, next_range.date_from)
                        continue
                    else:
                        _logger.error("No hay rangos válidos para fecha %s ni futuros", date)
                        continue
                
                # Verificar si el rango actual permite continuar
                if not sequence_status['can_continue']:
                    # Verificar si hay subsecuencias futuras que permitan continuar
                    if sequence.has_valid_future_sequences(date):
                        _logger.warning("Rango actual agotado pero existen subsecuencias futuras disponibles para secuencia %s", sequence.name)
                        # Continuar con la operación
                    else:
                        _logger.error("Rango actual agotado y no hay subsecuencias futuras para secuencia %s", sequence.name)
                        continue
                
                # Registrar advertencias si las hay
                if sequence_status.get('warnings'):
                    for warning in sequence_status['warnings']:
                        _logger.warning("Advertencia fiscal para secuencia %s: %s", sequence.name, warning)
                
                # Verificar que el rango tenga números disponibles
                if hasattr(current_range, 'rangoFinal') and current_range.rangoFinal:
                    if current_range.number_next_actual > current_range.rangoFinal:
                        # Verificar si hay subsecuencias futuras
                        if sequence.has_valid_future_sequences(date):
                            _logger.warning("Rango actual agotado pero existen subsecuencias futuras para secuencia %s", sequence.name)
                            continue
                        else:
                            _logger.error("Rango agotado y no hay subsecuencias futuras para secuencia %s", sequence.name)
                            continue
                
                # Asignar el número de secuencia fiscal
                ctx = dict(self.env.context, ir_sequence_date=date.strftime('%Y-%m-%d'))
                new_name = sequence.with_context(ctx).next_by_id()

                # Preparar valores para escribir
                vals_to_write = {
                    'name': new_name,
                    'cai': current_range.cai if hasattr(current_range, 'cai') else '',
                    'fechaLimiteEmision': current_range.date_to if hasattr(current_range, 'date_to') else False,
                }
                
                # Agregar rangos numéricos si existen
                if hasattr(current_range, 'rangoInicial') and hasattr(current_range, 'rangoFinal'):
                    if current_range.rangoInicial and current_range.rangoFinal:
                        numeroinicial = str(current_range.rangoInicial).zfill(sequence.padding)
                        numeroFinal = str(current_range.rangoFinal).zfill(sequence.padding)
                        vals_to_write.update({
                            'numeroInicial': f"{sequence.prefix or ''}{numeroinicial}",
                            'numeroFinal': f"{sequence.prefix or ''}{numeroFinal}",
                        })
                
                move.write(vals_to_write)
                _logger.info("Número fiscal SAR '%s' asignado a factura %s", new_name, move.id)
            else:
                # Para secuencias fiscales sin rango de fecha
                new_name = sequence.next_by_id(sequence_date=move.date)
                move.write({'name': new_name})
                _logger.info("Número de secuencia fiscal '%s' asignado a factura %s", new_name, move.id)
        
        return posted

    def letra_cifra(self):
        for r in self:
            r.totalAmountString = self.numero_to_letras(r.amount_total)
        return self

    def numero_to_letras(self, numero):
        indicador = [("", ""), ("MIL", "MIL"), ("MILLON", "MILLONES"), ("MIL", "MIL"),
                     ("BILLON", "BILLONES")]
        entero = int(numero)
        decimal = int(round((numero - entero) * 100))
        # Asegurar que los centavos tengan dos dígitos
        decimal_str = f"{decimal:02d}"
        contador = 0
        numero_letras = ""
        while entero > 0:
            a = entero % 1000
            if contador == 0:
                en_letras = self.convierte_cifra(a, 1).strip()
            else:
                en_letras = self.convierte_cifra(a, 0).strip()
            if a == 0:
                numero_letras = en_letras + " " + numero_letras
            elif a == 1:
                if contador in (1, 3):
                    numero_letras = indicador[contador][0] + " " + numero_letras
                else:
                    numero_letras = en_letras + " " + indicador[contador][
                        0] + " " + numero_letras
            else:
                numero_letras = en_letras + " " + indicador[contador][
                    1] + " " + numero_letras
            numero_letras = numero_letras.strip()
            contador = contador + 1
            entero = int(entero / 1000)

        # Agregar "Lempiras" y el formato de centavos con dos dígitos
        numero_letras = numero_letras + " Lempiras con " + decimal_str + "/100 Centavos"

        return numero_letras

    def convierte_cifra(self, numero, sw):
        lista_centana = ["", ("CIEN", "CIENTO"), "DOSCIENTOS", "TRESCIENTOS",
                         "CUATROCIENTOS", "QUINIENTOS",
                         "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
        lista_decena = ["", (
            "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS",
            "DIECISIETE", "DIECIOCHO", "DIECINUEVE"),
                        ("VEINTE", "VEINTI"), ("TREINTA", "TREINTA Y "),
                        ("CUARENTA", "CUARENTA Y "),
                        ("CINCUENTA", "CINCUENTA Y "), ("SESENTA", "SESENTA Y "),
                        ("SETENTA", "SETENTA Y "), ("OCHENTA", "OCHENTA Y "),
                        ("NOVENTA", "NOVENTA Y ")
                        ]
        lista_unidad = ["", ("UN", "UNO"), "DOS", "TRES", "CUATRO", "CINCO", "SEIS",
                        "SIETE", "OCHO", "NUEVE"]
        centena = int(numero / 100)
        decena = int((numero - (centena * 100)) / 10)
        unidad = int(numero - (centena * 100 + decena * 10))
        # print "centena: ",centena, "decena: ",decena,'unidad: ',unidad

        texto_centena = ""
        texto_decena = ""
        texto_unidad = ""

        # Validad las centenas
        texto_centena = lista_centana[centena]
        if centena == 1:
            if (decena + unidad) != 0:
                texto_centena = texto_centena[1]
            else:
                texto_centena = texto_centena[0]

        # Valida las decenas
        texto_decena = lista_decena[decena]
        if decena == 1:
            texto_decena = texto_decena[unidad]
        elif decena > 1:
            if unidad != 0:
                texto_decena = texto_decena[1]
            else:
                texto_decena = texto_decena[0]
        # Validar las unidades
        # print "texto_unidad: ",texto_unidad
        if decena != 1:
            texto_unidad = lista_unidad[unidad]
            if unidad == 1:
                texto_unidad = texto_unidad[sw]

        return "%s %s %s" % (texto_centena, texto_decena, texto_unidad)

    def action_post(self):
        for move in self:
            if not self.env.context.get('skip_fiscal_warning'):
                # Omitir validaciones fiscales para importaciones históricas
                if move.is_import:
                    _logger.info("Omitiendo validación de secuencia fiscal en action_post para movimiento %s - es importación histórica", move.id)
                    continue
                
                # Solo para facturas fiscales
                if not move.journal_id.needs_fiscal_sequence(move.move_type):
                    continue
                    
                sequence = move.journal_id.get_fiscal_sequence(move.move_type)
                if sequence and sequence.is_fiscal and sequence.use_date_range:
                    date = move.invoice_date or move.date
                    
                    # Usar la nueva validación inteligente
                    sequence_status = sequence.validate_sequence_continuity(date)
                    
                    if not sequence_status['valid']:
                        # Solo log de error, sin bloquear operaciones
                        _logger.error("Error de validación fiscal para secuencia %s: %s", sequence.name, sequence_status['message'])
                        continue
                    
                    # Obtener rango actual
                    current_range = sequence_status.get('current_range')
                    if not current_range:
                        # Buscar rango futuro
                        next_range = sequence.get_next_available_range(date)
                        if next_range:
                            _logger.warning("No hay rango para fecha %s, pero existe rango futuro desde %s", date, next_range.date_from)
                            continue
                        else:
                            _logger.error("No hay rangos válidos para fecha %s ni futuros", date)
                            continue
                    
                    # Verificar si el rango actual permite continuar
                    if not sequence_status['can_continue']:
                        # Verificar si hay subsecuencias futuras que permitan continuar
                        if sequence.has_valid_future_sequences(date):
                            _logger.warning("Rango actual agotado pero existen subsecuencias futuras disponibles para secuencia %s", sequence.name)
                            # Continuar con la operación
                        else:
                            _logger.error("Rango actual agotado y no hay subsecuencias futuras para secuencia %s", sequence.name)
                            continue
                    
                    # LÓGICA INTELIGENTE: Siempre generar alertas, pero verificar subsecuencias futuras para determinar si bloquear
                    
                    # Días de advertencia
                    if sequence.dias_alerta and hasattr(current_range, 'date_to') and current_range.date_to:
                        fecha_limite = current_range.date_to
                        fecha_actual = fields.Date.today()
                        dias_restantes = (fecha_limite - fecha_actual).days
                        _logger.info("Validación días: fecha límite %s, fecha actual %s, días restantes %d, alerta en %d", 
                                   fecha_limite, fecha_actual, dias_restantes, sequence.dias_alerta)
                        
                        if dias_restantes <= 0:
                            # VERIFICAR si hay subsecuencias futuras que cubran el rango de fechas
                            future_ranges = sequence.get_available_future_ranges(date)
                            if future_ranges:
                                # NO mostrar alerta - hay subsecuencias futuras, continuar transparentemente
                                _logger.info("Fecha límite vencida (%s) pero existen %d subsecuencias futuras para secuencia %s - continuando sin alertas", 
                                           fecha_limite, len(future_ranges), sequence.name)
                                # Continuar sin mostrar alertas al usuario
                            else:
                                # BLOQUEAR - no hay subsecuencias futuras que cubran
                                mensaje = _('ERROR: La fecha límite de emisión (%s) ha vencido y no hay subsecuencias futuras disponibles. No se puede publicar la factura.') % (fecha_limite)
                                raise UserError(mensaje)
                        elif dias_restantes <= sequence.dias_alerta:
                            # SOLO ADVERTENCIA (no bloquea) cuando quedan pocos días
                            mensaje = _('Advertencia: La fecha límite de emisión (%s) está próxima a vencer. Quedan %d días para la fecha límite.') % (fecha_limite, dias_restantes)
                            _logger.warning("Generando alerta de días para secuencia %s: %s", sequence.name, mensaje)
                            return {
                                'type': 'ir.actions.act_window',
                                'res_model': 'account.move.warning.wizard',
                                'view_mode': 'form',
                                'target': 'new',
                                'context': {
                                    'default_warning_message': mensaje,
                                    'default_move_id': move.id,
                                    'active_id': move.id,
                                }
                            }
                    
                    # Números de advertencia
                    if sequence.numeros_alerta and hasattr(current_range, 'rangoInicial') and hasattr(current_range, 'rangoFinal'):
                        if current_range.rangoInicial and current_range.rangoFinal:
                            numeros_restantes = current_range.rangoFinal - current_range.number_next_actual + 1
                            _logger.info("Validación números: rango %d-%d, actual %d, restantes %d, alerta en %d", 
                                       current_range.rangoInicial, current_range.rangoFinal, 
                                       current_range.number_next_actual, numeros_restantes, sequence.numeros_alerta)
                            
                            if numeros_restantes <= 0:
                                # VERIFICAR si hay subsecuencias futuras que cubran el rango numérico
                                future_ranges = sequence.get_available_future_ranges(date)
                                if future_ranges:
                                    # NO mostrar alerta - hay subsecuencias futuras, continuar transparentemente
                                    _logger.info("Rango agotado (%d-%d) pero existen %d subsecuencias futuras para secuencia %s - continuando sin alertas", 
                                               current_range.rangoInicial, current_range.rangoFinal, len(future_ranges), sequence.name)
                                    # Continuar sin mostrar alertas al usuario
                                else:
                                    # BLOQUEAR - no hay subsecuencias futuras que cubran
                                    mensaje = _('ERROR: El rango de numeración está completamente agotado (%d-%d) y no hay subsecuencias futuras disponibles. No se puede publicar la factura.') % (current_range.rangoInicial, current_range.rangoFinal)
                                    raise UserError(mensaje)
                            elif numeros_restantes <= sequence.numeros_alerta:
                                # SOLO ADVERTENCIA (no bloquea) cuando quedan pocos números
                                mensaje = _('Advertencia: El rango de numeración está próximo a agotarse. Quedan %d números disponibles del rango %d-%d.') % (numeros_restantes, current_range.rangoInicial, current_range.rangoFinal)
                                _logger.warning("Generando alerta de números para secuencia %s: %s", sequence.name, mensaje)
                                return {
                                    'type': 'ir.actions.act_window',
                                    'res_model': 'account.move.warning.wizard',
                                    'view_mode': 'form',
                                    'target': 'new',
                                    'context': {
                                        'default_warning_message': mensaje,
                                    'default_move_id': move.id,
                                        'active_id': move.id,
                                    }
                                }
        return super().action_post()

    def _get_name_invoice_report(self):
        """
        Sobrescribir para mostrar el correlativo del proveedor en el nombre del reporte
        para facturas y notas de crédito de proveedor
        """
        self.ensure_one()
        
        if self.move_type in ['in_invoice', 'in_refund']:
            # Para facturas y notas de crédito de proveedor
            if self.correlativo_proveedor:
                # Concatenar el nombre del documento con el correlativo del proveedor
                return f"{self.correlativo_proveedor} - {self.name}"
            else:
                return self.name
        else:
            # Para otros tipos de documentos, comportamiento normal
            return super()._get_name_invoice_report()

    def name_get(self):
        """
        Sobrescribir para mostrar el correlativo del proveedor en las vistas de lista
        """
        result = []
        for move in self:
            if move.move_type in ['in_invoice', 'in_refund'] and move.correlativo_proveedor:
                # Para facturas y notas de crédito de proveedor, mostrar ambos números
                display_name = f"{move.correlativo_proveedor} - {move.name}"
            else:
                display_name = move.name
            result.append((move.id, display_name))
        return result

    @api.depends("name", "correlativo_proveedor")
    def _compute_referencia_completa(self):
        for move in self:
            if move.move_type in ['in_invoice', 'in_refund'] and move.correlativo_proveedor:
                move.referencia_completa = f"{move.correlativo_proveedor} - {move.name}"
            else:
                move.referencia_completa = move.name or ''

    def marcar_como_importacion_historica(self):
        """
        Método helper para marcar documentos como importación histórica
        Útil para procesos de importación masiva
        """
        self.ensure_one()
        self.write({'is_import': True})
        _logger.info("Documento %s marcado como importación histórica", self.name)
        return True

    @api.model
    def crear_documento_historico(self, vals):
        """
        Método helper para crear documentos históricos sin correlativo fiscal
        """
        # Asegurar que el documento se marque como importación histórica
        vals['is_import'] = True
        
        # Crear el documento
        documento = self.create(vals)
        
        _logger.info("Documento histórico creado: %s (ID: %s)", documento.name, documento.id)
        return documento

    def copy(self, default=None):
        """
        Sobrescribir el método copy para manejar correctamente la duplicación de facturas fiscales.
        Cuando se duplica una factura confirmada, se debe resetear el nombre fiscal a "/" 
        para que se genere un nuevo número de secuencia al confirmar la factura duplicada.
        """
        default = default or {}
        
        # Para facturas que requieren secuencia fiscal, resetear el nombre y campos fiscales
        for move in self:
            if move.journal_id and move.journal_id.needs_fiscal_sequence(move.move_type):
                # Resetear el nombre a "/" para que se genere un nuevo número al confirmar
                default['name'] = "/"
                
                # Resetear campos fiscales relacionados
                default['cai'] = False
                default['fechaLimiteEmision'] = False
                default['numeroInicial'] = False
                default['numeroFinal'] = False
                default['totalAmountString'] = False
                
                # Resetear estado de validación fiscal
                default['fiscal_validation_status'] = 'pending'
                default['fiscal_validation_message'] = False
                
                # Resetear campos fiscales de proveedor si existen
                default['cai_proveedor'] = False
                default['correlativo_proveedor'] = False
                default['femision_proveedor'] = False
                
                _logger.info("Reseteando campos fiscales para duplicación de factura %s (ID: %s)", move.name, move.id)
        
        # Llamar al método copy estándar de Odoo
        new_move = super().copy(default)
        
        # Asegurar que la factura duplicada esté en estado 'draft' y tenga name = "/"
        if new_move.journal_id and new_move.journal_id.needs_fiscal_sequence(new_move.move_type):
            if new_move.name != "/":
                new_move.write({'name': "/"})
                _logger.info("Asegurando que factura duplicada %s (ID: %s) tenga name = '/'", new_move.name if new_move.name != "/" else "nueva", new_move.id)
        
        return new_move

    # @api.model
    # def action_create_debit_note(self):
    #     """
    #     Método para crear una nota de débito de cliente.
    #     Busca automáticamente el diario con documento_fiscal='debit' de la empresa actual.
    #     """
    #     # Buscar el diario de Nota de Débito para la empresa actual
    #     journal = self.env['account.journal'].search([
    #         ('document_fiscal', '=', 'debit'),
    #         ('company_id', '=', self.env.company.id),
    #         ('type', '=', 'sale')
    #     ], limit=1)
        
    #     if not journal:
    #         raise UserError(_(
    #             'No se encontró un diario de Nota de Débito configurado para la empresa %s.\n'
    #             'Por favor, configure un diario con Documento Fiscal = "Nota de Debito" '
    #             'y Tipo = "Ventas" en Contabilidad > Configuración > Diarios.'
    #         ) % self.env.company.name)
        
    #     # Retornar acción para crear nueva factura con el diario pre-seleccionado
    #     action = {
    #         'name': _('Nota de Débito'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.move',
    #         'view_mode': 'form',
    #         'target': 'current',
    #         'context': {
    #             'default_move_type': 'out_invoice',
    #             'default_journal_id': journal.id,
    #             'default_company_id': self.env.company.id,
    #         }
    #     }
        
    #     return action

# class AccountMoveLineExtended(models.Model):
#     _inherit = 'account.move.line'

#     analytic_distribution_text = fields.Char(string='Distribución Analítica',
#                                              compute='get_name_analytic_distribution')

#     @api.depends("analytic_distribution")
#     def get_name_analytic_distribution(self):
#         for r in self:
#             r.analytic_distribution_text = ""
#             if r.analytic_distribution:
#                 for ad in r.analytic_distribution:
#                     analytic = self.env['account.analytic.account'].search(
#                         [('id', '=', ad)])
#                     if r.analytic_distribution_text == False:
#                         r.analytic_distribution_text = ""
#                         r.analytic_distribution_text = str(analytic.name)
#                     else:
#                         r.analytic_distribution_text = str(
#                             r.analytic_distribution_text) + ", " + str(analytic.name)
#                         print(r.analytic_distribution_text)

