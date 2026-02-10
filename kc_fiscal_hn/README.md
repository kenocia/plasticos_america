# Módulo Fiscal Honduras (kc_fiscal_hn) - Odoo 18

## Descripción General

El módulo **kc_fiscal_hn** es una solución integral para la gestión fiscal en Honduras, diseñado para cumplir con los requisitos del Servicio de Administración de Rentas (SAR) y las regulaciones fiscales hondureñas. Este módulo extiende las funcionalidades estándar de Odoo 18 para incluir características específicas del sistema fiscal hondureño.

## Características Principales

### 🏢 **Gestión de Secuencias Fiscales**
- Configuración de secuencias automáticas para documentos fiscales
- Control de rangos de fechas para secuencias
- Alertas automáticas para secuencias próximas a agotarse
- Integración con códigos CAI (Código de Autorización de Impresión)
- Asociación de secuencias con tipos de operación de albaranes

### 📊 **Reportes Fiscales Especializados**
- **Declaración DMC**: Generación de reportes para la Declaración Mensual de Compras
- **Factura - Producto**: Análisis detallado de facturas por producto
- **Ventas Netas**: Reporte de ventas netas para efectos fiscales

### 💰 **Gestión de Impuestos Hondureños**
- Configuración de impuestos ISV (15% y 18%)
- Manejo de impuestos de retención
- Productos exentos y exonerados
- Cálculos automáticos de bases imponibles
- Códigos SAR para productos e impuestos

### 📋 **Documentos Fiscales**
- Facturas con formato fiscal hondureño
- Notas de crédito y débito
- Guías de remisión con información de transporte
- Comprobantes de retención
- Boletas de compra

### 📦 **Gestión de Inventario Fiscal**
- Control de costos en movimientos de stock
- Cálculo automático de bases imponibles e ISV
- Información de facturas relacionadas con movimientos
- Control de cantidades disponibles y costos residuales

## Instalación y Configuración

### Requisitos Previos
- Odoo 18.0 o superior
- Módulos base: `account`, `stock`, `purchase`, `sale`
- Configuración de empresa con país Honduras

### Pasos de Instalación
1. Copiar el módulo a la carpeta `addons` de Odoo
2. Actualizar la lista de aplicaciones
3. Buscar "Fiscal HN" en las aplicaciones
4. Instalar el módulo
5. Configurar las secuencias fiscales

## Configuración Inicial

### 1. Configuración de Secuencias Fiscales

#### Acceso a Secuencias
- Ir a **Fiscal HN > Configuraciones > Secuencias**
- O navegar a **Configuración > Técnico > Secuencias**

#### Crear Nueva Secuencia Fiscal
1. Hacer clic en **Crear**
2. Completar los campos obligatorios:
   - **Nombre**: Nombre descriptivo de la secuencia
   - **Código**: Código único para la secuencia
   - **Prefijo**: Prefijo para los números (ej: "FAC-")
   - **Sufijo**: Sufijo opcional
   - **Próximo número**: Número inicial
   - **Incremento**: Incremento entre números (normalmente 1)
   - **Relleno**: Número de dígitos (ej: 8 para 00000001)

3. **Configuración Fiscal**:
   - Marcar **Es Fiscal** si es para documentos fiscales
   - **Días de Alerta**: Días antes de agotarse para recibir alertas
   - **Números de Alerta**: Cantidad restante para recibir alertas

#### Configurar Rangos de Fecha
1. En la secuencia, activar **Usar rangos de fecha**
2. Ir a la pestaña **Rangos de fecha**
3. Agregar rangos con:
   - **Fecha desde** y **Fecha hasta**
   - **CAI**: Código de Autorización de Impresión
   - **Rango inicial** y **Rango final**

#### Asociar Secuencias con Tipos de Operación
1. Ir a **Inventario > Configuración > Tipos de Operación**
2. Editar el tipo de operación deseado
3. En el campo **Secuencia SAR Remisión**, seleccionar la secuencia fiscal correspondiente

### 2. Configuración de Impuestos

#### Crear Impuestos ISV
1. Ir a **Contabilidad > Configuración > Impuestos**
2. Crear impuestos con:
   - **Tipo de Impuesto**: ISV
   - **Porcentaje**: 15% o 18%
   - **Código SAR**: Código según catálogo del SAR
   - **Es Retención**: Marcar si es impuesto de retención

#### Configurar Impuestos de Retención
1. Crear impuesto con **Tipo de Impuesto**: Retención
2. Marcar **Es Retención**
3. Configurar porcentaje y código SAR correspondiente

### 3. Configuración de Productos

#### Productos Fiscales
1. En **Inventario > Productos**, editar un producto
2. En la pestaña **Información General**:
   - **Exento**: Marcar si el producto está exento de ISV
   - **Es Retención**: Marcar si aplica retención
   - **Retención**: Seleccionar impuesto de retención si aplica
   - **Código SAR**: Código del producto según SAR
   - **Es Exento/Exonerado**: Estado fiscal del producto
   - **Categoría Fiscal**: Bienes, Servicios, o Ambos

## Funcionalidades por Módulo

### 📄 **Facturación (account.move)**

#### Campos Fiscales Agregados
- **Base Imponible 15%**: Base para ISV 15%
- **Base Imponible 18%**: Base para ISV 18%
- **ISV 15%**: Monto del impuesto al 15%
- **ISV 18%**: Monto del impuesto al 18%
- **Total ISV**: Suma de ambos impuestos
- **Retención**: Monto de retención aplicada

#### Configuración de Facturas
1. Al crear una factura, los campos fiscales se calculan automáticamente
2. Los montos se basan en los impuestos configurados en los productos
3. Las retenciones se aplican según la configuración del producto

### 📦 **Inventario (stock.move.line)**

#### Información de Costos
- **Quantity Real**: Cantidad real del movimiento (con signo según tipo)
- **Costo**: Costo unitario del producto
- **Total Costo**: Costo total del movimiento
- **Cantidad Anterior**: Stock disponible antes del movimiento
- **Residual**: Stock disponible después del movimiento
- **Total Residual**: Costo total del stock residual
- **Ubicación**: Ubicación propia según tipo de operación

#### Información Fiscal
- **Base Imponible**: Base fiscal del movimiento
- **Monto ISV**: Impuesto calculado

#### Información de Documentos
- **Facturas**: Enlaces a facturas relacionadas
- **Pedido de Compra**: Orden de compra asociada
- **Pedido de Venta**: Orden de venta asociada
- **Contacto**: Cliente o proveedor

#### Funcionalidades Especiales
- **Cálculo automático de costos**: Basado en capas de valuación
- **Historial de costos**: Trazabilidad completa de costos
- **Actualización automática**: Al confirmar movimientos

### 🚚 **Albaranes (stock.picking)**

#### Información SAR
- **Nombre SAR**: Nombre de la secuencia fiscal
- **CAI**: Código de Autorización de Impresión
- **Número Inicial/Final**: Rango de numeración
- **Fecha Límite de Emisión**: Fecha límite para emisión
- **Motivo de Traslado**: Razón del traslado (venta, importación, etc.)

#### Información del Transportista
- **Nombre del Transportista**: Conductor o empresa
- **RTN/Identidad**: Número de identificación
- **Marca y No. de Placa**: Información del vehículo
- **Licencia de Conducir**: Número de licencia

#### Funcionalidades
- **Botón "Actualizar Numeración SAR"**: Actualiza información fiscal automáticamente
- **Generación automática de números de guía**: Para albaranes de salida
- **Cálculo de totales fiscales**: Base imponible e ISV total

### 🏪 **Productos (product.template y product.product)**

#### Campos Fiscales
- **Exento**: Si el producto está exento de ISV
- **Es Retención**: Si aplica retención
- **Retención**: Impuesto de retención específico
- **Código SAR**: Código del producto según SAR
- **Es Exento/Exonerado**: Estado fiscal detallado
- **Categoría Fiscal**: Clasificación para reportes

#### Funcionalidades
- **Actualización automática de impuestos**: Al cambiar estado de exención
- **Configuración de retenciones**: Por producto
- **Códigos SAR**: Para reportes fiscales

## Reportes Disponibles

### 📊 **Declaración DMC**
**Ubicación**: Fiscal HN > Informes > Declaración DMC

Este reporte genera la información necesaria para la Declaración Mensual de Compras del SAR.

**Parámetros**:
- **Fecha desde/hasta**: Período del reporte
- **Compañía**: Empresa para el reporte
- **Tipo de documento**: Facturas, notas de crédito, etc.

**Información incluida**:
- Detalle de compras por proveedor
- Bases imponibles por tipo de impuesto
- Totales de ISV pagado
- Retenciones aplicadas

### 📋 **Factura - Producto**
**Ubicación**: Fiscal HN > Informes > Factura - Producto

Análisis detallado de facturas desglosado por producto.

**Características**:
- Agrupación por producto
- Totales por período
- Análisis de impuestos por producto
- Exportación a Excel

### 💰 **Ventas Netas**
**Ubicación**: Fiscal HN > Informes > Ventas Netas

Reporte de ventas netas para efectos fiscales.

**Incluye**:
- Ventas brutas y netas
- Desglose por tipo de impuesto
- Exenciones y exoneraciones
- Totales por período

## Documentos Fiscales

### 🧾 **Facturas**
- Formato adaptado a requisitos hondureños
- Numeración automática con secuencias fiscales
- Cálculo automático de impuestos
- Campos para retenciones

### 📝 **Notas de Crédito/Débito**
- Generación automática de numeración
- Referencia a documentos originales
- Cálculo de ajustes fiscales

### 🚚 **Guías de Remisión**
- Formato estándar hondureño
- Información de transporte completa
- Validaciones fiscales
- Numeración automática con CAI

### 📄 **Comprobantes de Retención**
- Generación automática
- Cálculo de retenciones
- Formato oficial

## Alertas y Validaciones

### ⚠️ **Alertas de Secuencias**
- Notificaciones cuando las secuencias están próximas a agotarse
- Configuración de días y números de alerta
- Reportes de secuencias con bajo stock

### ✅ **Validaciones Fiscales**
- Verificación de códigos SAR
- Validación de rangos de fechas
- Control de límites de secuencias
- Validación de CAI en albaranes

### 🔄 **Actualizaciones Automáticas**
- Cálculo automático de costos en movimientos
- Actualización de información SAR en albaranes
- Cálculo de impuestos en facturas

## Mantenimiento

### 🔄 **Actualizaciones**
- Mantener el módulo actualizado con las últimas versiones
- Revisar cambios en regulaciones fiscales
- Actualizar códigos SAR según catálogos oficiales

### 📋 **Respaldo de Datos**
- Realizar respaldos regulares de configuraciones fiscales
- Exportar reportes importantes
- Mantener historial de cambios

### 🛠️ **Mantenimiento de Secuencias**
- Revisar regularmente el estado de las secuencias
- Actualizar rangos de fechas cuando sea necesario
- Solicitar nuevos CAI al SAR cuando se agoten

## Soporte y Contacto

### 🆘 **Solución de Problemas Comunes**

#### Error: "Secuencia agotada"
- Verificar configuración de rangos de fecha
- Actualizar números de secuencia
- Contactar al SAR para nuevos rangos

#### Error: "Código SAR inválido"
- Verificar catálogo oficial del SAR
- Actualizar códigos en productos
- Validar formato de códigos

#### Error: "Impuesto no configurado"
- Revisar configuración de impuestos
- Verificar tipos de impuesto
- Comprobar códigos SAR de impuestos

#### Error: "CAI no encontrado"
- Verificar configuración de rangos de fecha en secuencias
- Comprobar que el CAI esté ingresado en el rango
- Validar fechas de vigencia del CAI

#### Problemas con costos en movimientos
- Verificar configuración de valuación de inventario
- Revisar capas de valuación
- Comprobar costos estándar de productos

### 📞 **Contacto**
Para soporte técnico o consultas sobre el módulo:
- **Email**: soporte@expologistic.com
- **Teléfono**: +504 XXXX-XXXX
- **Horario**: Lunes a Viernes 8:00 AM - 5:00 PM

## Notas Importantes

### ⚖️ **Cumplimiento Legal**
- Este módulo está diseñado para cumplir con las regulaciones fiscales hondureñas
- Es responsabilidad del usuario mantener la información actualizada
- Se recomienda consultar con un contador o asesor fiscal

### 🔒 **Seguridad**
- Mantener respaldos regulares de la información fiscal
- Controlar acceso a configuraciones fiscales
- Revisar logs de cambios importantes

### 📈 **Mejores Prácticas**
- Configurar secuencias con suficiente margen
- Revisar reportes antes de presentarlos al SAR
- Mantener documentación de configuraciones
- Capacitar usuarios en el uso del módulo
- Revisar regularmente la configuración de impuestos
- Validar códigos SAR con el catálogo oficial

### 🔧 **Funcionalidades Técnicas**
- **Compatibilidad**: Odoo 18.0+
- **Base de datos**: PostgreSQL recomendado
- **Rendimiento**: Optimizado para grandes volúmenes de datos
- **Seguridad**: Validaciones de acceso por grupos de usuario

---

**Versión del módulo**: 1.0  
**Compatible con**: Odoo 18.0+  
**Última actualización**: Julio 2025  
**Estado**: Migrado y optimizado para Odoo 18

# 📋 **REPORTE DE ANÁLISIS DEL MÓDULO FISCAL HONDURAS**

##  **ANÁLISIS GENERAL**

### **Estado Actual del Módulo**
- ✅ **Migración exitosa** a Odoo 18
- ✅ **Campos fiscales completos** del módulo original
- ✅ **Funcionalidades básicas** implementadas
- ⚠️ **Faltan validaciones críticas** del SAR
- ⚠️ **Lógica de negocio incompleta** para requerimientos fiscales

---

##  **PROBLEMAS CRÍTICOS IDENTIFICADOS**

### **1. VALIDACIONES FISCALES FALTANTES**

#### **❌ Problema: No hay validaciones de CAI**
```python
<code_block_to_apply_changes_from>
```

#### **❌ Problema: No hay validaciones de RTN**
```python
# FALTA EN res.partner
def _validate_rtn(self):
    """Validar formato RTN según SAR"""
    # Validar formato: 14 dígitos
    # Validar dígito verificador
    # Validar tipo de contribuyente
```

#### **❌ Problema: No hay validaciones de numeración fiscal**
```python
# FALTA EN ir_sequence.py
def _validate_fiscal_sequence(self):
    """Validar secuencia fiscal según SAR"""
    # Validar rango de fechas
    # Validar límites de numeración
    # Validar CAI asociado
```

### **2. LÓGICA DE CÁLCULO FISCAL INCOMPLETA**

#### **❌ Problema: Cálculo de ISV incorrecto**
```python
# EN account_move.py línea 120-140
# El cálculo no considera:
# - Productos exentos correctamente
# - Base imponible después de descuentos
# - Redondeo según SAR
```

#### **❌ Problema: No hay validación de montos mínimos**
```python
# FALTA: Validación de montos mínimos para facturación
# Según SAR: Facturas < L. 500 no requieren numeración fiscal
```

### **3. REPORTES INCOMPLETOS**

#### **❌ Problema: Reporte DMC incompleto**
```python
# EN wizard/report_dmc_excel.py
# Faltan campos requeridos por SAR:
# - Validación de códigos de producto
# - Clasificación correcta de gastos
# - Totales por tipo de impuesto
```

#### **❌ Problema: No hay reporte de ventas SAR**
```python
# FALTA: Reporte de ventas para SAR
# - Declaración mensual de ventas
# - Totales por tipo de contribuyente
# - Exenciones y exoneraciones
```

### **4. GESTIÓN DE SECUENCIAS PROBLEMÁTICA**

#### **❌ Problema: No hay control de secuencias agotadas**
```python
# EN ir_sequence.py
# Falta:
# - Alerta automática cuando se agota secuencia
# - Bloqueo de facturación sin secuencia válida
# - Validación de rangos de fecha
```

#### **❌ Problema: No hay validación de CAI en secuencias**
```python
# FALTA: Validación de CAI en rangos de fecha
# - Verificar que CAI esté vigente
# - Validar rango de numeración
# - Alertar sobre vencimiento próximo
```

---

##  **ANÁLISIS DE VISTAS Y REFERENCIAS**

### **✅ Vistas Correctas**
- `account_move.xml`: Campos fiscales bien referenciados
- `stock_move_line.xml`: Campos de costo correctos
- `product_template.xml`: Campos fiscales completos

### **⚠️ Vistas con Problemas**
- `stock_picking.xml`: Campo `fechaLimiteEmision` no se actualiza automáticamente
- `ir_sequence.xml`: Falta validación de rangos de fecha

---

## 🎯 **REQUERIMIENTOS DEL SAR NO IMPLEMENTADOS**

### **1. VALIDACIONES OBLIGATORIAS**
- ❌ **Validación de RTN**: Formato y dígito verificador
- ❌ **Validación de CAI**: Formato y vigencia
- ❌ **Validación de numeración**: Rango y formato
- ❌ **Validación de montos**: Límites mínimos y máximos

### **2. REPORTES FISCALES**
- ❌ **Declaración Mensual de Ventas**
- ❌ **Reporte de Retenciones**
- ❌ **Reporte de Exenciones**
- ❌ **Reporte de Exoneraciones**

### **3. CONTROL DE SECUENCIAS**
- ❌ **Alerta de secuencias agotadas**
- ❌ **Validación de CAI vencido**
- ❌ **Control de rangos de fecha**
- ❌ **Bloqueo de facturación sin secuencia**

### **4. CÁLCULOS FISCALES**
- ❌ **Redondeo según SAR**
- ❌ **Base imponible correcta**
- ❌ **Cálculo de retenciones**
- ❌ **Validación de exenciones**

---

## 🔧 **RECOMENDACIONES DE MEJORA**

### **1. VALIDACIONES CRÍTICAS (PRIORIDAD ALTA)**

#### **A. Validación de RTN**
```python
# Agregar en res.partner
def _validate_rtn_format(self):
    """Validar formato RTN según SAR"""
    if self.vat and len(self.vat) != 14:
        raise ValidationError(_('RTN debe tener 14 dígitos'))
    
    # Validar dígito verificador
    rtn = self.vat.replace('-', '')
    if not self._validate_rtn_check_digit(rtn):
        raise ValidationError(_('RTN inválido - dígito verificador incorrecto'))
```

#### **B. Validación de CAI**
```python
# Agregar en ir.sequence.date_range
def _validate_cai_format(self):
    """Validar formato CAI según SAR"""
    if self.cai and len(self.cai) != 9:
        raise ValidationError(_('CAI debe tener 9 dígitos'))
    
    # Validar dígito verificador
    if not self._validate_cai_check_digit(self.cai):
        raise ValidationError(_('CAI inválido - dígito verificador incorrecto'))
```

#### **C. Validación de Secuencias**
```python
# Agregar en ir.sequence
def _validate_fiscal_sequence(self):
    """Validar secuencia fiscal"""
    if self.is_fiscal:
        # Validar que tenga rangos de fecha
        if not self.date_range_ids:
            raise ValidationError(_('Secuencia fiscal debe tener rangos de fecha'))
        
        # Validar que tenga CAI
        for date_range in self.date_range_ids:
            if not date_range.cai:
                raise ValidationError(_('Rango de fecha debe tener CAI'))
```

### **2. MEJORAS EN CÁLCULOS FISCALES (PRIORIDAD ALTA)**

#### **A. Cálculo Correcto de ISV**
```python
# Mejorar en account_move.py
def _compute_importe_gravado(self):
    """Cálculo correcto de ISV según SAR"""
    for inv in self:
        isv15 = 0.0
        isv18 = 0.0
        importe15 = 0.0
        importe18 = 0.0

        for line in inv.invoice_line_ids:
            # Calcular base imponible correctamente
            base_imponible = line.price_subtotal
            
            # Aplicar redondeo según SAR
            for tax in line.tax_ids:
                if tax.amount == 15:
                    isv_line = round(base_imponible * 0.15, 2)
                    isv15 += isv_line
                    importe15 += base_imponible
                elif tax.amount == 18:
                    isv_line = round(base_imponible * 0.18, 2)
                    isv18 += isv_line
                    importe18 += base_imponible

        inv.amount_isv15 = isv15
        inv.gravado_isv15 = importe15
        inv.amount_isv18 = isv18
        inv.gravado_isv18 = importe18
```

#### **B. Validación de Montos Mínimos**
```python
# Agregar en account_move.py
def _validate_minimum_amount(self):
    """Validar monto mínimo para facturación fiscal"""
    if self.move_type in ['out_invoice', 'out_refund']:
        total_amount = self.amount_total
        if total_amount < 500:  # L. 500 mínimo según SAR
            raise ValidationError(_('Facturas menores a L. 500 no requieren numeración fiscal'))
```

### **3. REPORTES FISCALES COMPLETOS (PRIORIDAD MEDIA)**

#### **A. Reporte de Ventas SAR**
```python
# Crear nuevo wizard
class ReportSalesSAR(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.sales_sar'
    _description = 'Reporte de Ventas SAR'
    
    def generate_sales_report(self):
        """Generar reporte de ventas para SAR"""
        # Implementar reporte completo de ventas
        pass
```

#### **B. Reporte de Retenciones**
```python
# Crear nuevo wizard
class ReportRetentionsSAR(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.retentions_sar'
    _description = 'Reporte de Retenciones SAR'
    
    def generate_retentions_report(self):
        """Generar reporte de retenciones para SAR"""
        # Implementar reporte de retenciones
        pass
```

### **4. CONTROL DE SECUENCIAS MEJORADO (PRIORIDAD MEDIA)**

#### **A. Alerta de Secuencias Agotadas**
```python
# Agregar en ir.sequence
def _check_sequence_expiration(self):
    """Verificar secuencias próximas a agotarse"""
    for sequence in self:
        if sequence.is_fiscal:
            # Verificar números restantes
            remaining = sequence.number_final - sequence.number_next_actual
            if remaining <= sequence.numeros_alerta:
                # Enviar alerta
                self._send_sequence_alert(sequence)
```

#### **B. Validación de CAI Vencido**
```python
# Agregar en ir.sequence.date_range
def _check_cai_expiration(self):
    """Verificar CAI próximos a vencer"""
    today = fields.Date.today()
    for date_range in self:
        if date_range.date_to <= today + timedelta(days=30):
            # Enviar alerta de CAI próximo a vencer
            self._send_cai_expiration_alert(date_range)
```

### **5. MEJORAS EN LA INTERFAZ (PRIORIDAD BAJA)**

#### **A. Dashboard Fiscal**
```python
# Crear vista de dashboard
class FiscalDashboard(models.Model):
    _name = 'kc_fiscal_hn.dashboard'
    _description = 'Dashboard Fiscal'
    
    def get_fiscal_summary(self):
        """Obtener resumen fiscal"""
        # Implementar dashboard con métricas fiscales
        pass
```

#### **B. Alertas en Tiempo Real**
```python
# Agregar notificaciones
def _send_fiscal_alert(self, message, type='warning'):
    """Enviar alerta fiscal"""
    # Implementar sistema de notificaciones
    pass
```

---

## 📋 **PLAN DE IMPLEMENTACIÓN**

### **FASE 1: VALIDACIONES CRÍTICAS (1-2 semanas)**
1. ✅ Implementar validación de RTN
2. ✅ Implementar validación de CAI
3. ✅ Implementar validación de secuencias
4. ✅ Mejorar cálculos fiscales

### **FASE 2: REPORTES FISCALES (2-3 semanas)**
1. ✅ Reporte de ventas SAR
2. ✅ Reporte de retenciones
3. ✅ Mejorar reporte DMC
4. ✅ Reporte de exenciones

### **FASE 3: CONTROL DE SECUENCIAS (1-2 semanas)**
1. ✅ Alertas de secuencias agotadas
2. ✅ Validación de CAI vencido
3. ✅ Control de rangos de fecha
4. ✅ Bloqueo de facturación

### **FASE 4: MEJORAS DE INTERFAZ (1 semana)**
1. ✅ Dashboard fiscal
2. ✅ Alertas en tiempo real
3. ✅ Mejoras en vistas
4. ✅ Documentación actualizada

---

##  **CONCLUSIONES**

### **Estado Actual**
- ✅ **Migración exitosa** a Odoo 18
- ✅ **Funcionalidades básicas** operativas
- ⚠️ **Faltan validaciones críticas** del SAR
- ⚠️ **Reportes incompletos** para requerimientos fiscales

### **Recomendaciones Prioritarias**
1. **Implementar validaciones críticas** (RTN, CAI, secuencias)
2. **Mejorar cálculos fiscales** según SAR
3. **Completar reportes fiscales** requeridos
4. **Implementar control de secuencias** robusto

### **Impacto de las Mejoras**
- 🔒 **Mayor cumplimiento fiscal** con SAR
- 📊 **Reportes más precisos** y completos
- ⚡ **Menos errores** en facturación
- 🎯 **Mejor control** de secuencias fiscales

El módulo tiene una base sólida pero necesita implementar las validaciones y reportes críticos requeridos por el SAR de Honduras para ser completamente funcional y cumplir con todas las regulaciones fiscales.

# Módulo Fiscal Honduras - KC Fiscal HN

## Funcionalidad de Impresión Automática

### Descripción
Este módulo incluye una funcionalidad que permite marcar automáticamente los documentos como impresos cuando se genera un reporte PDF o HTML.

### Características

#### Campo `original_print`
- **Tipo**: Boolean
- **Valor por defecto**: True
- **Descripción**: Indica si el documento ha sido impreso

#### Métodos de Impresión

1. **`action_print_document()`**
   - Imprime el documento y marca `original_print` como `True`
   - Disponible en la barra de herramientas del formulario

2. **`action_print_original()`**
   - Método específico para imprimir original
   - Marca `original_print` como `True`

3. **`action_print_with_mark()`**
   - Imprime y marca automáticamente como impreso
   - Solo visible si el documento no ha sido impreso previamente

4. **`_mark_as_printed()`**
   - Método interno para marcar el documento como impreso
   - Se ejecuta automáticamente al generar reportes

#### Interceptación Automática de Reportes

El módulo sobrescribe los métodos de `ir.actions.report` para interceptar automáticamente la impresión:

- **`_render_qweb_pdf()`**: Marca como impreso al generar PDF
- **`_render_qweb_html()`**: Marca como impreso al generar HTML

#### Filtros de Búsqueda

Se han agregado filtros adicionales en la vista de búsqueda:
- **Documentos Impresos**: Muestra documentos con `original_print = True`
- **Documentos No Impresos**: Muestra documentos con `original_print = False`

#### Vista de Lista

Se ha agregado el campo `original_print` en la vista de lista como columna opcional.

### Uso

1. **Impresión Manual**:
   - Usar los botones "Imprimir Documento", "Imprimir Original" o "Imprimir y Marcar"
   - Los botones están disponibles en la barra de herramientas del formulario

2. **Impresión Automática**:
   - Al usar cualquier reporte de factura (PDF o HTML), el documento se marca automáticamente como impreso
   - No requiere acción adicional del usuario

3. **Seguimiento**:
   - Usar los filtros de búsqueda para ver documentos impresos vs no impresos
   - El campo `original_print` se muestra en el formulario y lista

### Configuración

No se requiere configuración adicional. La funcionalidad está habilitada por defecto para todos los documentos de tipo factura (`out_invoice`, `out_refund`, `in_invoice`, `in_refund`).

### Logs

El módulo registra automáticamente las acciones de impresión en los logs del sistema para auditoría.
