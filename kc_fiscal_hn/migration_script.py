#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migración para Kenocia Fiscal Honduras
Odoo 17 -> Odoo 18
"""

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate_fiscal_data(env):
    """
    Migra datos fiscales de la versión anterior
    """
    _logger.info("Iniciando migración de datos fiscales...")
    
    # Migrar secuencias existentes
    sequences = env['ir.sequence'].search([])
    for sequence in sequences:
        if not sequence.is_fiscal:
            # Verificar si es una secuencia fiscal basada en el nombre o código
            if any(keyword in sequence.name.lower() for keyword in ['fiscal', 'sar', 'factura', 'nota']):
                sequence.is_fiscal = True
                _logger.info(f"Secuencia {sequence.name} marcada como fiscal")
    
    # Migrar impuestos existentes
    taxes = env['account.tax'].search([])
    for tax in taxes:
        if not tax.tipo_impuesto:
            # Asignar tipo de impuesto basado en el nombre
            if 'isv' in tax.name.lower() or '15%' in tax.name or '18%' in tax.name:
                tax.tipo_impuesto = 'isv'
                if '15' in tax.name:
                    tax.codigo_sar = '01'
                elif '18' in tax.name:
                    tax.codigo_sar = '02'
            elif 'exento' in tax.name.lower():
                tax.tipo_impuesto = 'exento'
                tax.codigo_sar = '03'
            elif 'exonerado' in tax.name.lower():
                tax.tipo_impuesto = 'exonerado'
                tax.codigo_sar = '04'
            elif 'retencion' in tax.name.lower():
                tax.tipo_impuesto = 'retencion'
                tax.codigo_sar = '05'
            else:
                tax.tipo_impuesto = 'otros'
    
    # Migrar productos existentes
    products = env['product.template'].search([])
    for product in products:
        if not product.es_exento and not product.es_exonerado:
            # Verificar si el producto tiene impuestos exentos
            exempt_taxes = product.taxes_id.filtered(lambda t: t.tipo_impuesto == 'exento')
            if exempt_taxes:
                product.es_exento = True
            else:
                exonerated_taxes = product.taxes_id.filtered(lambda t: t.tipo_impuesto == 'exonerado')
                if exonerated_taxes:
                    product.es_exonerado = True
    
    _logger.info("Migración de datos fiscales completada")


def create_fiscal_groups(env):
    """
    Crea grupos de impuestos fiscales si no existen
    """
    _logger.info("Creando grupos de impuestos fiscales...")
    
    # Crear grupos de impuestos si no existen
    tax_groups_data = [
        {'name': 'ISV', 'sequence': 10},
        {'name': 'Exento', 'sequence': 20},
        {'name': 'Exonerado', 'sequence': 30},
        {'name': 'Retención', 'sequence': 40},
    ]
    
    for group_data in tax_groups_data:
        existing_group = env['account.tax.group'].search([('name', '=', group_data['name'])], limit=1)
        if not existing_group:
            env['account.tax.group'].create(group_data)
            _logger.info(f"Grupo de impuestos {group_data['name']} creado")
    
    _logger.info("Grupos de impuestos fiscales verificados")


def update_sequences_alerts(env):
    """
    Actualiza alertas en secuencias existentes
    """
    _logger.info("Actualizando alertas en secuencias...")
    
    fiscal_sequences = env['ir.sequence'].search([('is_fiscal', '=', True)])
    for sequence in fiscal_sequences:
        if not sequence.dias_alerta:
            sequence.dias_alerta = 30
        if not sequence.numeros_alerta:
            sequence.numeros_alerta = 100
    
    _logger.info("Alertas de secuencias actualizadas")


def migrate_analytic_distribution(env):
    """
    Migra datos de distribución analítica antigua
    """
    _logger.info("Migrando distribución analítica...")
    
    # Buscar líneas de asiento con distribución analítica antigua
    move_lines = env['account.move.line'].search([
        ('analytic_distribution', '!=', False)
    ])
    
    for line in move_lines:
        if line.analytic_distribution:
            # La distribución analítica ya está en el formato correcto en Odoo 18
            # Solo necesitamos asegurar que se recalcule el campo computado
            line._compute_analytic_distribution_text()
    
    _logger.info("Distribución analítica migrada")


def run_migration(env):
    """
    Ejecuta toda la migración
    """
    _logger.info("=== INICIANDO MIGRACIÓN KENOCIA FISCAL HONDURAS ===")
    
    try:
        # 1. Crear grupos de impuestos
        create_fiscal_groups(env)
        
        # 2. Migrar datos fiscales
        migrate_fiscal_data(env)
        
        # 3. Actualizar alertas de secuencias
        update_sequences_alerts(env)
        
        # 4. Migrar distribución analítica
        migrate_analytic_distribution(env)
        
        _logger.info("=== MIGRACIÓN COMPLETADA EXITOSAMENTE ===")
        
    except Exception as e:
        _logger.error(f"Error durante la migración: {str(e)}")
        raise


def migrate_fiscal_module(cr, registry):
    """
    Hook de migración para ser llamado manualmente
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    run_migration(env)


if __name__ == "__main__":
    # Para ejecutar manualmente
    import odoo
    odoo.cli.main() 