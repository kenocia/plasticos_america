import base64
import io
import calendar
import datetime
import logging
from dateutil import parser
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import xlwt
except ImportError:
    xlwt = None


class ReportDmcLine(models.TransientModel):
    _name = 'kc_fiscal_hn.dmc.line'
    _description = 'Línea DMC para vista'

    dmc_view_id = fields.Many2one('kc_fiscal_hn.dmc.view', string='Vista DMC', required=True, ondelete='cascade')
    sheet_type = fields.Selection([
        ('527-52', '527-52'),
        ('527-53', '527-53'),
        ('527-54', '527-54'),
    ], string='Hoja', required=True)
    # Campos hoja 527-52
    rtn = fields.Char(string='R.T.N')
    proveedor = fields.Char(string='Proveedor')
    clase = fields.Char(string='Clase documento')
    cai = fields.Char(string='CAI')
    f_documento = fields.Char(string='N° Documento')
    r_documento = fields.Char(string='N° Documento (OC)')
    # Campos hojas 527-53, 527-54
    dmc_pasaporte_identificacion_ca = fields.Char(string='Pasaporte/Identificación CA')
    dmc_identificador_tributario_mercantil = fields.Char(string='Identificador tributario mercantil')
    dmc_numero_fyduca = fields.Char(string='N.º FYDUCA')
    dmc_numero_dua = fields.Char(string='N.º DUA')
    # Campos comunes
    fecha_emision = fields.Char(string='Fecha emisión')
    fecha_contable = fields.Char(string='Fecha contable')
    oce = fields.Char(string='Nº OCE')
    importe_exento = fields.Float(string='Importe exento')
    resolucion = fields.Char(string='Nº resolución')
    importe_exonerado_15 = fields.Float(string='Importe exonerado 15%')
    importe_exonerado_18 = fields.Float(string='Importe exonerado 18%')
    importe_isv15 = fields.Float(string='Importe base 15%')
    importe_isv18 = fields.Float(string='Importe base 18%')
    importe_base_15_fuera = fields.Float(string='Importe base 15% (Fuera CA)')
    importe_base_18_fuera = fields.Float(string='Importe base 18% (Fuera CA)')
    costo = fields.Float(string='Monto al costo')
    gasto = fields.Float(string='Monto al gasto')
    deducible = fields.Float(string='Valor no deducible')


class ReportDmcView(models.TransientModel):
    _name = 'kc_fiscal_hn.dmc.view'
    _description = 'Vista DMC con pestañas'

    wizard_id = fields.Many2one('kc_fiscal_hn.wizard.dmc', string='Wizard', ondelete='cascade')
    fecha_desde = fields.Date(string="Fecha Desde", related='wizard_id.fecha_desde', readonly=True)
    fecha_hasta = fields.Date(string="Fecha Hasta", related='wizard_id.fecha_hasta', readonly=True)

    line_ids_527_52 = fields.One2many(
        'kc_fiscal_hn.dmc.line', 'dmc_view_id', string='527-52',
        domain=[('sheet_type', '=', '527-52')])
    line_ids_527_53 = fields.One2many(
        'kc_fiscal_hn.dmc.line', 'dmc_view_id', string='527-53',
        domain=[('sheet_type', '=', '527-53')])
    line_ids_527_54 = fields.One2many(
        'kc_fiscal_hn.dmc.line', 'dmc_view_id', string='527-54',
        domain=[('sheet_type', '=', '527-54')])

    def _populate_dmc_lines(self):
        """Crear registros de línea DMC a partir de get_invoice()."""
        invoice = self.wizard_id.get_invoice()

        def _norm_tipo(value):
            return (value or '').strip().lower()

        def _is_fiduca(value):
            tipo = _norm_tipo(value)
            return 'fiduca' in tipo or 'fyduca' in tipo

        def _is_importacion(value):
            tipo = _norm_tipo(value)
            return 'importacion' in tipo or 'importación' in tipo

        DmcLine = self.env['kc_fiscal_hn.dmc.line']
        vals_527_52 = []
        vals_527_53 = []
        vals_527_54 = []

        for i in invoice:
            fiscal_documento = i.get('f_documento', '')

            if _is_fiduca(i.get('dmc_tipo', '')):
                vals_527_53.append({
                    'dmc_view_id': self.id,
                    'sheet_type': '527-53',
                    'dmc_pasaporte_identificacion_ca': i.get('dmc_pasaporte_identificacion_ca', ''),
                    'dmc_identificador_tributario_mercantil': i.get('dmc_identificador_tributario_mercantil', ''),
                    'proveedor': i.get('proveedor', ''),
                    'dmc_numero_fyduca': i.get('dmc_numero_fyduca', ''),
                    'fecha_emision': i.get('fecha_emision', ''),
                    'fecha_contable': i.get('fecha_contable', ''),
                    'oce': i.get('oce', ''),
                    'importe_exento': i.get('importe_exento') or 0,
                    'resolucion': i.get('resolucion', ''),
                    'importe_exonerado_15': i.get('importe_exonerado_15') or 0,
                    'importe_exonerado_18': i.get('importe_exonerado_18') or 0,
                    'importe_isv15': i.get('importe_isv15') or 0,
                    'importe_isv18': i.get('importe_isv18') or 0,
                    'costo': i.get('costo') or 0,
                    'gasto': i.get('gasto') or 0,
                    'deducible': i.get('deducible') or 0,
                })
            elif _is_importacion(i.get('dmc_tipo', '')):
                vals_527_54.append({
                    'dmc_view_id': self.id,
                    'sheet_type': '527-54',
                    'dmc_pasaporte_identificacion_ca': i.get('dmc_pasaporte_identificacion_ca', ''),
                    'proveedor': i.get('proveedor', ''),
                    'dmc_numero_dua': i.get('dmc_numero_dua', ''),
                    'fecha_emision': i.get('fecha_emision', ''),
                    'fecha_contable': i.get('fecha_contable', ''),
                    'oce': i.get('oce', ''),
                    'importe_exento': i.get('importe_exento') or 0,
                    'resolucion': i.get('resolucion', ''),
                    'importe_exonerado_15': i.get('importe_exonerado_15') or 0,
                    'importe_exonerado_18': i.get('importe_exonerado_18') or 0,
                    'importe_isv15': i.get('importe_isv15') or 0,
                    'importe_base_15_fuera': 0,
                    'importe_isv18': i.get('importe_isv18') or 0,
                    'importe_base_18_fuera': 0,
                    'costo': i.get('costo') or 0,
                    'gasto': i.get('gasto') or 0,
                    'deducible': i.get('deducible') or 0,
                })
            else:
                vals_527_52.append({
                    'dmc_view_id': self.id,
                    'sheet_type': '527-52',
                    'rtn': i.get('rtn', ''),
                    'proveedor': i.get('proveedor', ''),
                    'clase': i.get('clase', ''),
                    'cai': i.get('cai', ''),
                    'f_documento': fiscal_documento,
                    'r_documento': i.get('r_documento', ''),
                    'fecha_emision': i.get('fecha_emision', ''),
                    'fecha_contable': i.get('fecha_contable', ''),
                    'oce': i.get('oce', ''),
                    'importe_exento': i.get('importe_exento') or 0,
                    'resolucion': i.get('resolucion', ''),
                    'importe_exonerado_15': i.get('importe_exonerado_15') or 0,
                    'importe_exonerado_18': i.get('importe_exonerado_18') or 0,
                    'importe_isv15': i.get('importe_isv15') or 0,
                    'importe_isv18': i.get('importe_isv18') or 0,
                    'costo': i.get('costo') or 0,
                    'gasto': i.get('gasto') or 0,
                    'deducible': i.get('deducible') or 0,
                })

        DmcLine.create(vals_527_52)
        DmcLine.create(vals_527_53)
        DmcLine.create(vals_527_54)


class ReportDmcList(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.dmc'
    _description = 'Reporte DMC'

    company_id = fields.Many2one('res.company', 'Company', required=True,
                                 default=lambda s: s.env.company.id, index=True)
    fecha_desde = fields.Date(string="Fecha Desde", default=datetime.date.today(), required=True)
    fecha_hasta = fields.Date(string="Fecha Hasta", default=datetime.date.today(), required=True)
    state = fields.Selection(selection=[('draft', 'Borrador'),
                                        ('posted', 'Posteado'),
                                        ('cancel', 'Cancelado'), ], string='Status', default='posted')

    def action_view_data(self):
        """Crear vista DMC separada con las 3 pestañas."""
        dmc_view = self.env['kc_fiscal_hn.dmc.view'].create({'wizard_id': self.id})
        dmc_view._populate_dmc_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': 'DMC - %s a %s' % (self.fecha_desde, self.fecha_hasta),
            'res_model': 'kc_fiscal_hn.dmc.view',
            'res_id': dmc_view.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def print_report(self):
        invoice = self.get_invoice()
        filename = 'DMC de ' + str(self.fecha_desde) + ' a ' + str(self.fecha_hasta) + '.xls'
        workbook = xlwt.Workbook()
        style = xlwt.easyxf()
        encabezado = xlwt.easyxf('font: name Arial, color black, bold on, height 320; align: horiz center')
        titulos = xlwt.easyxf('font: name Arial, color black, bold on,; align: horiz center')
        subtitulos = xlwt.easyxf('font: name Arial, color black, bold on,height 250; align: horiz center')
        subtitulos_largo = xlwt.easyxf('font: name Arial, color black, bold on, height 250; align: horiz center')
        detalle = xlwt.easyxf('font: name Arial, color black;')
        detalle_moneda = xlwt.easyxf('font: name Arial, color black;')
        detalle_porcentaje = xlwt.easyxf('font: name Arial, color black;')
        detalle_moneda.num_format_str = 'L#,##0.00'
        detalle_porcentaje.num_format_str = '0.00%'

        def _norm_tipo(value):
            return (value or '').strip().lower()

        def _is_fiduca(value):
            tipo = _norm_tipo(value)
            return 'fiduca' in tipo or 'fyduca' in tipo

        def _is_importacion(value):
            tipo = _norm_tipo(value)
            return 'importacion' in tipo or 'importación' in tipo

        def _build_sheet(sheet, sheet_name):
            # ENCABEZADO
            # sheet.write_merge(fila inicial, fila final, columna inicial, columna final)
            # Encabezados eliminados por requerimiento del reporte
            # TITULOS
            # sheet.write(fila, columnas, texto, estilo)

            if sheet_name == '527-53':
                sheet.write(0, 0, '301-Pasaporte o identificación CA', subtitulos)
                sheet.write(0, 1, '302-Nº Identificador tributario mercantil', subtitulos)
                sheet.write(0, 2, '501-Apellidos y nombre/razón social', subtitulos)
                sheet.write(0, 3, '190-N.º FYDUCA', subtitulos)
                sheet.write(0, 4, '901-Fecha emisión', subtitulos)
                sheet.write(0, 5, '101-Fecha contable', subtitulos)
                sheet.write(0, 6, '141-Nº OCE', subtitulos)
                sheet.write(0, 7, '111-Importe exento', subtitulos)
                sheet.write(0, 8, '131-Nº resolución', subtitulos)
                sheet.write(0, 9, '1211-Importe exonerado al 15%', subtitulos)
                sheet.write(0, 10, '1212-Importe exonerado al 18%', subtitulos)
                sheet.write(0, 11, '1512-Importe base 15%', subtitulos)
                sheet.write(0, 12, '1612-Importe base 18%', subtitulos)
                sheet.write(0, 13, '271-Monto al costo', subtitulos)
                sheet.write(0, 14, '281-Monto al gasto', subtitulos)
                sheet.write(0, 15, '291-Valor no deducible', subtitulos)
            elif sheet_name == '527-54':
                sheet.write(0, 0, '303-Pasaporte o identificación CA', subtitulos)
                sheet.write(0, 1, '502-Apellidos y nombre/razón social', subtitulos)
                sheet.write(0, 2, '20-N.º DUA', subtitulos)
                sheet.write(0, 3, '902-Fecha emisión', subtitulos)
                sheet.write(0, 4, '102-Fecha contable', subtitulos)
                sheet.write(0, 5, '142-Nº OCE', subtitulos)
                sheet.write(0, 6, '112-Importe exento', subtitulos)
                sheet.write(0, 7, '132-Nº resolución', subtitulos)
                sheet.write(0, 8, '1221-Importe exonerado al 15%', subtitulos)
                sheet.write(0, 9, '1222-Importe exonerado al 18%', subtitulos)
                sheet.write(0, 10, '1513-Importe base 15%', subtitulos)
                sheet.write(0, 11, '1520-Importe base 15% (Fuera región Centroamericana)', subtitulos)
                sheet.write(0, 12, '1613-Importe base 18%', subtitulos)
                sheet.write(0, 13, '1620-Importe base 18% (Fuera región Centroamericana)', subtitulos)
                sheet.write(0, 14, '272-Monto al costo', subtitulos)
                sheet.write(0, 15, '282-Monto al gasto', subtitulos)
                sheet.write(0, 16, '292-Valor no deducible', subtitulos)
            else:
                sheet.write(0, 0, '200-R.T.N', subtitulos)
                sheet.write(0, 1, 'Nombres Apellidos o Razón Social del Proveedor', subtitulos)
                sheet.write(0, 2, '600-CLASE DE DOCUMENTO', subtitulos)
                sheet.write(0, 3, '7-CAI', subtitulos)
                sheet.write(0, 4, '8-N° Documento', subtitulos)
                sheet.write(0, 5, '71-N° Documento', subtitulos)
                sheet.write(0, 6, '900-Fecha emisión', subtitulos)
                sheet.write(0, 7, '100-Fecha contable', subtitulos)
                sheet.write(0, 8, '140-Nº OCE', subtitulos)
                sheet.write(0, 9, '110-Importe exento', subtitulos)
                sheet.write(0, 10, '130-Nº resolución', subtitulos)
                sheet.write(0, 11, '1201-Importe exonerado al 15%', subtitulos)
                sheet.write(0, 12, '1202-Importe exonerado al 18%', subtitulos)
                sheet.write(0, 13, '1511-Importe base 15%', subtitulos)
                sheet.write(0, 14, '1611-Importe base 18%', subtitulos)
                sheet.write(0, 15, '270-Monto al costo', subtitulos)
                sheet.write(0, 16, '280-Monto al gasto', subtitulos)
                sheet.write(0, 17, '290-Valor no deducible', subtitulos)

            cantidad = 0
            sublps = 0
            subdls = 0
            impuesto = 0
            flete = 0
            comision = 0
            total_lps = 0
            total_dls = 0
            f = 1
            if sheet_name == '527-53':
                rows = [i for i in invoice if _is_fiduca(i.get('dmc_tipo'))]
            elif sheet_name == '527-54':
                rows = [i for i in invoice if _is_importacion(i.get('dmc_tipo'))]
            else:
                rows = [
                    i for i in invoice
                    if not _is_fiduca(i.get('dmc_tipo')) and not _is_importacion(i.get('dmc_tipo'))
                ]
            _logger.info(
                "DMC %s: total=%s fiduca=%s importacion=%s rows=%s",
                sheet_name,
                len(invoice),
                sum(1 for i in invoice if _is_fiduca(i.get('dmc_tipo'))),
                sum(1 for i in invoice if _is_importacion(i.get('dmc_tipo'))),
                len(rows),
            )
            for i in rows:
                estable = ''
                emision = ''
                tipo = ''
                correlativo = ''
                fiscal_documento = ''
                if i['f_documento']:
                    if '-' not in i['f_documento']:
                        fiscal_documento = i['f_documento']
                    else:
                        partes = i['f_documento'].split('-')
                        fiscal_documento = i['f_documento']
                        if len(partes) == 4:
                            estable = partes[0]
                            emision = partes[1]
                            tipo = partes[2]
                            correlativo = partes[3]

                if sheet_name == '527-53':
                    sheet.write(f, 0, i.get('dmc_pasaporte_identificacion_ca', ''), detalle)
                    sheet.write(f, 1, i.get('dmc_identificador_tributario_mercantil', ''), detalle)
                    sheet.write(f, 2, i.get('proveedor', ''), detalle)
                    sheet.write(f, 3, i.get('dmc_numero_fyduca', ''), detalle)
                    sheet.write(f, 4, i.get('fecha_emision', ''), detalle)
                    sheet.write(f, 5, i.get('fecha_contable', ''), detalle)
                    sheet.write(f, 6, i.get('oce', ''), detalle)
                    sheet.write(f, 7, i.get('importe_exento', ''), detalle)
                    sheet.write(f, 8, i.get('resolucion', ''), detalle)
                    sheet.write(f, 9, i.get('importe_exonerado_15', ''), detalle)
                    sheet.write(f, 10, i.get('importe_exonerado_18', ''), detalle)
                    sheet.write(f, 11, i.get('importe_isv15', ''), detalle)
                    sheet.write(f, 12, i.get('importe_isv18', ''), detalle)
                    sheet.write(f, 13, i.get('costo', ''), detalle)
                    sheet.write(f, 14, i.get('gasto', ''), detalle)
                    sheet.write(f, 15, i.get('deducible', ''), detalle)
                elif sheet_name == '527-54':
                    sheet.write(f, 0, i.get('dmc_pasaporte_identificacion_ca', ''), detalle)
                    sheet.write(f, 1, i.get('proveedor', ''), detalle)
                    sheet.write(f, 2, i.get('dmc_numero_dua', ''), detalle)
                    sheet.write(f, 3, i.get('fecha_emision', ''), detalle)
                    sheet.write(f, 4, i.get('fecha_contable', ''), detalle)
                    sheet.write(f, 5, i.get('oce', ''), detalle)
                    sheet.write(f, 6, i.get('importe_exento', ''), detalle)
                    sheet.write(f, 7, i.get('resolucion', ''), detalle)
                    sheet.write(f, 8, i.get('importe_exonerado_15', ''), detalle)
                    sheet.write(f, 9, i.get('importe_exonerado_18', ''), detalle)
                    sheet.write(f, 10, i.get('importe_isv15', ''), detalle)
                    sheet.write(f, 11, '', detalle)
                    sheet.write(f, 12, i.get('importe_isv18', ''), detalle)
                    sheet.write(f, 13, '', detalle)
                    sheet.write(f, 14, i.get('costo', ''), detalle)
                    sheet.write(f, 15, i.get('gasto', ''), detalle)
                    sheet.write(f, 16, i.get('deducible', ''), detalle)
                else:
                    sheet.write(f, 0, i['rtn'], detalle)
                    sheet.write(f, 1, i['proveedor'], detalle)
                    sheet.write(f, 2, i['clase'], detalle)
                    sheet.write(f, 3, i['cai'], detalle)
                    sheet.write(f, 4, fiscal_documento, detalle)
                    sheet.write(f, 5, i['r_documento'], detalle)
                    sheet.write(f, 6, i['fecha_emision'], detalle)
                    sheet.write(f, 7, i['fecha_contable'], detalle)
                    sheet.write(f, 8, i['oce'], detalle)
                    sheet.write(f, 9, i['importe_exento'], detalle)
                    sheet.write(f, 10, i['resolucion'], detalle)
                    sheet.write(f, 11, i['importe_exonerado_15'], detalle)
                    sheet.write(f, 12, i['importe_exonerado_18'], detalle)
                    sheet.write(f, 13, i['importe_isv15'], detalle)
                    sheet.write(f, 14, i['importe_isv18'], detalle)
                    sheet.write(f, 15, i['costo'], detalle)
                    sheet.write(f, 16, i['gasto'], detalle)
                    sheet.write(f, 17, i['deducible'], detalle)
                f += 1

        for sheet_name in ['527-52', '527-53', '527-54']:
            sheet = workbook.add_sheet(sheet_name, cell_overwrite_ok=True)
            _build_sheet(sheet, sheet_name)

        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['kc_fiscal_hn.dmc.excel'].create(
            {'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        fp.close()
        return {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'kc_fiscal_hn.dmc.excel',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new'
        }
        return True

    def get_invoice(self):
        domain = ''
        # if self.payment_state:
        #     domain = [('company_id', '=', self.company_id.id),
        #               ('invoice_date', '>=', self.fecha_desde),
        #               ('invoice_date', '<=', self.fecha_hasta),
        #               ('state', '=', self.state),
        #               ('move_type', '=', 'in_invoice'),
        #               ('payment_state', '=', self.payment_state)]
        # else:
        domain = [('company_id', '=', self.company_id.id),
                  ('invoice_date', '>=', self.fecha_desde),
                  ('invoice_date', '<=', self.fecha_hasta),
                  ('state', '=', self.state),
                  ('move_type', '=', 'in_invoice')]

        invoices = self.env['account.move'].search(domain)

        # Logs de diagnóstico para tipos DMC y campos relacionados
        dmc_tipo_counts = {}
        fiduca_samples = []
        import_samples = []
        for inv in invoices:
            key = inv.dmc_tipo or ''
            dmc_tipo_counts[key] = dmc_tipo_counts.get(key, 0) + 1
            if inv.dmc_numero_fyduca or inv.dmc_identificador_tributario_mercantil:
                fiduca_samples.append((inv.id, inv.name, inv.dmc_tipo))
            if inv.dmc_numero_dua or inv.dmc_pasaporte_identificacion_ca:
                import_samples.append((inv.id, inv.name, inv.dmc_tipo))

        _logger.info("DMC tipos encontrados (valor bruto): %s", dmc_tipo_counts)
        _logger.info("DMC muestras FYDUCA (id, name, tipo): %s", fiduca_samples[:10])
        _logger.info("DMC muestras Importación (id, name, tipo): %s", import_samples[:10])
        dmc_any_domain = [
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', 'in_invoice'),
            '|', '|', '|', '|',
            ('dmc_tipo', '!=', False),
            ('dmc_numero_fyduca', '!=', False),
            ('dmc_numero_dua', '!=', False),
            ('dmc_pasaporte_identificacion_ca', '!=', False),
            ('dmc_identificador_tributario_mercantil', '!=', False),
        ]
        dmc_any = self.env['account.move'].search(dmc_any_domain, limit=10)
        _logger.info(
            "DMC facturas con datos (sin filtro fechas/estado, muestra): %s",
            [(m.id, m.name, m.dmc_tipo, m.invoice_date, m.date, m.state) for m in dmc_any],
        )

        # tasa_cambiarias = self.env['res.currency.rate'].search([('company_id', '=', self.company_id.id),
        #                                                         ('name', '>=', self.fecha_desde),
        #                                                         ('name', '<=', self.fecha_hasta),
        #                                                         ('currency_id.id', '=', self.currency_id.id)], limit=1)
        # tasa_cambiaria = 0
        # for t in tasa_cambiarias:
        #     tasa_cambiaria = round(t.rate, 4)

        def _format_date(value):
            if not value:
                return ''
            if isinstance(value, str):
                try:
                    value = fields.Date.from_string(value)
                except Exception:
                    try:
                        value = fields.Datetime.from_string(value)
                    except Exception:
                        try:
                            value = parser.parse(value)
                        except Exception:
                            return value
            return value.strftime('%d/%m/%Y')

        data = []
        for i in invoices:
            clase_documento = ''
            cai_proveedor = ''
            proveedor = ''
            f_documento = ''
            r_documento = ''
            costo = ''
            gasto = ''
            deducible = ''
            if i.class_document_sar == 'FA':
                cai_proveedor = i.cai_proveedor
                f_documento = i.correlativo_proveedor
                clase_documento = 'FA-FACTURA'
            elif i.class_document_sar == 'OC':
                r_documento = i.correlativo_proveedor
                clase_documento = 'OC-OTROS COMPROBANTES DE PAGO'

            if i.montos_sar == 'costo':
                costo = i.amount_isv15 + i.amount_isv18
            elif i.montos_sar == 'gasto':
                gasto = i.amount_isv15 + i.amount_isv18
            elif i.montos_sar == 'no_deducible':
                deducible = i.amount_isv15 + i.amount_isv18

            invoice = {
                'rtn': i.partner_id.vat,
                'proveedor': i.partner_id.name,
                'clase': clase_documento,
                'cai': cai_proveedor,
                'f_documento': f_documento,
                'r_documento': r_documento,
                'fecha_emision': _format_date(i.femision_proveedor),
                'fecha_contable': _format_date(i.date),
                'oce': i.noOrdenCompraExenta if i.noOrdenCompraExenta else '',
                'importe_exento': i.amount_exento,
                'resolucion': '',
                'importe_exonerado_15': i.amount_exonerado,
                'importe_exonerado_18': 0.0,
                'importe_isv15': i.gravado_isv15,
                'importe_isv18': i.gravado_isv18,
                'costo': costo,
                'gasto': gasto,
                'deducible': deducible,
                'dmc_pasaporte_identificacion_ca': i.dmc_pasaporte_identificacion_ca or '',
                'dmc_identificador_tributario_mercantil': i.dmc_identificador_tributario_mercantil or '',
                'dmc_numero_fyduca': i.dmc_numero_fyduca or '',
                'dmc_numero_dua': i.dmc_numero_dua or '',
                'dmc_tipo': i.dmc_tipo or ''
            }
            data.append(invoice)
        return data


class ReportInvoiceExcel(models.TransientModel):
    _name = "kc_fiscal_hn.dmc.excel"
    _description = "Reporte DMC Excel"

    excel_file = fields.Binary('Lista Factura', readonly=True)
    file_name = fields.Char('Excel File', size=64)
