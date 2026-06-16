# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND, OR


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    kc_allowed_point_ids = fields.Many2many(
        comodel_name='quality.point',
        compute='_compute_kc_allowed_point_ids',
        string='Puntos de control permitidos (producto)',
    )

    # Norma: no existe campo norm en quality.check estándar; almacenado para read_group del gráfico SPC.
    spc_chart_norm = fields.Float(
        string='Norma (gráfico SPC)',
        related='point_id.norm',
        readonly=True,
        store=True,
    )
    # Mismos nombres que quality_control; aquí store=True para que read_group/webReadGroup agregue en el gráfico.
    tolerance_min = fields.Float(
        related='point_id.tolerance_min',
        readonly=True,
        store=True,
    )
    tolerance_max = fields.Float(
        related='point_id.tolerance_max',
        readonly=True,
        store=True,
    )
    kc_requires_production = fields.Boolean(
        compute='_compute_kc_requires_production',
        string='OP obligatoria (punto fabricación)',
    )

    @api.depends('point_id', 'point_id.picking_type_ids')
    def _compute_kc_requires_production(self):
        for rec in self:
            rec.kc_requires_production = rec._kc_point_requires_mo()

    def _kc_point_requires_mo(self):
        self.ensure_one()
        if not self.point_id:
            return False
        return any(pt.code == 'mrp_operation' for pt in self.point_id.picking_type_ids)

    def _kc_domain_points_for_product(self, product, company):
        """Con producto en el control: solo puntos que declaran ese producto o su categoría.
        No se incluyen puntos «para todos» (sin productos ni categorías), que antes aparecían siempre.
        Sin producto en el control: todos los puntos de la empresa (mismo criterio que antes).
        """
        company_dom = [('company_id', 'in', [False, company.id])]
        if not product:
            return company_dom
        categ_id = product.categ_id.id
        product_match = [('product_ids', 'in', product.ids)]
        if categ_id:
            categ_match = [('product_category_ids', 'parent_of', categ_id)]
            product_dom = OR([product_match, categ_match])
        else:
            product_dom = product_match
        return AND([company_dom, product_dom])

    @api.depends('product_id', 'product_id.categ_id', 'company_id')
    def _compute_kc_allowed_point_ids(self):
        Point = self.env['quality.point']
        for rec in self:
            domain = rec._kc_domain_points_for_product(rec.product_id, rec.company_id)
            rec.kc_allowed_point_ids = Point.search(domain)

    @api.onchange('product_id')
    def _onchange_product_id_kc_filter_point(self):
        if self.point_id and self.point_id not in self.kc_allowed_point_ids:
            self.point_id = False

    @api.onchange('point_id')
    def _onchange_point_id(self):
        res = super()._onchange_point_id()
        for rec in self:
            if rec.point_id:
                rec.measure_on = rec.point_id.measure_on
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            pid = vals.get('point_id')
            if pid:
                point = self.env['quality.point'].browse(pid)
                if point:
                    vals['measure_on'] = point.measure_on
        return super().create(vals_list)

    @api.constrains('point_id', 'product_id', 'company_id')
    def _kc_constrains_point_matches_product(self):
        Point = self.env['quality.point']
        for rec in self:
            if not rec.point_id:
                continue
            allowed = Point.search(rec._kc_domain_points_for_product(rec.product_id, rec.company_id))
            if rec.point_id not in allowed:
                raise ValidationError(_(
                    'El punto de control seleccionado no aplica al producto indicado en este control.'
                ))

    def write(self, vals):
        pid = vals.get('point_id')
        if pid:
            point = self.env['quality.point'].browse(pid)
            if point:
                vals = dict(vals, measure_on=point.measure_on)
        res = super().write(vals)
        if 'product_id' in vals:
            Point = self.env['quality.point']
            for rec in self:
                allowed = Point.search(rec._kc_domain_points_for_product(rec.product_id, rec.company_id))
                if rec.point_id and rec.point_id not in allowed:
                    super(QualityCheck, rec).write({'point_id': False})
        return res

    @api.constrains('point_id', 'production_id')
    def _kc_check_production_required_for_mo_point(self):
        for rec in self:
            if rec._kc_point_requires_mo() and not rec.production_id:
                raise ValidationError(_(
                    'La orden de producción es obligatoria cuando el punto de control '
                    'aplica a operaciones de fabricación.'
                ))
