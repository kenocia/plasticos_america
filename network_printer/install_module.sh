#!/bin/bash
# Script para instalar el módulo network_printer en Odoo

echo "Instalando módulo network_printer..."

# Copiar el módulo a la ubicación de Odoo
sudo cp -r /home/cmunguia/network_printer_temp /opt/odoo18/addons/kenocia/network_printer

# Ajustar permisos
sudo chown -R odoo:odoo /opt/odoo18/addons/kenocia/network_printer

echo "Módulo copiado exitosamente a /opt/odoo18/addons/kenocia/network_printer"
echo ""
echo "Para instalar el módulo en Odoo, ejecuta:"
echo "sudo -u odoo ./odoo-bin -d NOMBRE_BD -i network_printer --stop-after-init"
echo ""
echo "Luego reinicia Odoo:"
echo "sudo systemctl restart odoo"

