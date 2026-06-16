# -*- coding: utf-8 -*-

from odoo import _


def post_init_hook(env):
    """Migra almacenes PT/MP antiguos a líneas de ubicación de planificación."""
    PlanningLoc = env['kc.sale.planning.location']
    for company in env['res.company'].search([]):
        if company.kc_planning_location_ids:
            continue
        seq = 10
        if company.kc_planning_pt_warehouse_id and company.kc_planning_pt_warehouse_id.lot_stock_id:
            PlanningLoc.create({
                'company_id': company.id,
                'usage_type': 'pt',
                'location_id': company.kc_planning_pt_warehouse_id.lot_stock_id.id,
                'sequence': seq,
                'notes': _('Migrado desde almacén PT'),
            })
            seq += 10
        if company.kc_planning_mp_warehouse_id and company.kc_planning_mp_warehouse_id.lot_stock_id:
            PlanningLoc.create({
                'company_id': company.id,
                'usage_type': 'mp',
                'location_id': company.kc_planning_mp_warehouse_id.lot_stock_id.id,
                'sequence': seq,
                'notes': _('Migrado desde almacén MP'),
            })
