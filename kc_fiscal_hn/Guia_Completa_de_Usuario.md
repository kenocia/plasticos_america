# 📚 **GUÍA COMPLETA DEL USUARIO - MÓDULO FISCAL HONDURAS (kc_fiscal_hn)**

## �� **INTRODUCCIÓN**

El módulo **kc_fiscal_hn** es una solución integral para el cumplimiento fiscal en Honduras según los requerimientos del SAR (Sistema de Administración de Rentas). Este módulo proporciona validaciones automáticas, cálculos fiscales precisos, reportes completos y un sistema avanzado de control de secuencias fiscales.

---

## 📋 **TABLA DE CONTENIDOS**

1. [Instalación y Configuración](#instalación-y-configuración)
2. [Validaciones Fiscales](#validaciones-fiscales)
3. [Cálculos Fiscales](#cálculos-fiscales)
4. [Control de Secuencias Fiscales](#control-de-secuencias-fiscales)
5. [Sistema de Alertas](#sistema-de-alertas)
6. [Reportes Fiscales](#reportes-fiscales)
7. [Auditoría y Seguridad](#auditoría-y-seguridad)
8. [Dashboard y Métricas](#dashboard-y-métricas)
9. [Solución de Problemas](#solución-de-problemas)
10. [Glosario Técnico](#glosario-técnico)

---

## 🔧 **INSTALACIÓN Y CONFIGURACIÓN**

### **Requisitos Previos**
- Odoo 18.0 o superior
- Módulo `account` habilitado
- Módulo `sale` habilitado (opcional)
- Módulo `stock` habilitado (opcional)

### **Instalación del Módulo**
1. Copiar el módulo `kc_fiscal_hn` al directorio `addons` de Odoo
2. Actualizar la lista de aplicaciones en Odoo
3. Buscar "Fiscal HN" en las aplicaciones
4. Hacer clic en "Instalar"

### **Configuración Inicial**

#### **1. Configuración de la Empresa**
```
Menú: Fiscal HN > Configuraciones > Secuencias Fiscales
```

**Campos Requeridos:**
- **RTN**: Número de Registro Tributario Nacional
- **CAI**: Clave de Autorización de Impresión (si aplica)
- **Dirección Fiscal**: Dirección registrada en el SAR

#### **2. Configuración de Secuencias Fiscales**
```
Menú: Fiscal HN > Configuraciones > Secuencias Fiscales
```

**Para cada secuencia fiscal:**
- ✅ Marcar "Es Secuencia Fiscal"
- ✅ Seleccionar "Tipo Fiscal" (Factura, Nota de Crédito, etc.)
- ✅ Definir "Inicio de Rango Fiscal" y "Fin de Rango Fiscal"
- ✅ Configurar "Umbral de Alerta" (80% por defecto)
- ✅ Configurar "Umbral de Advertencia" (90% por defecto)
- ✅ Activar "Alertas Automáticas"

**Ejemplo de Configuración:**
```
Nombre: Factura Fiscal
Tipo Fiscal: Factura
Inicio de Rango: 1
Fin de Rango: 10000
Umbral de Alerta: 80%
Umbral de Advertencia: 90%
```

---

## ✅ **VALIDACIONES FISCALES**

### **1. Validación de RTN (Registro Tributario Nacional)**

#### **Validación Automática**
- Se ejecuta automáticamente al crear/modificar contactos
- Valida formato: 9 dígitos numéricos
- Calcula dígito verificador según algoritmo del SAR

#### **Validación Manual**
```
Menú: Fiscal HN > Validaciones > Validación de Contactos
```

**Proceso:**
1. Seleccionar contactos a validar
2. Hacer clic en "Validar RTN"
3. Revisar resultados en la lista

**Estados de Validación:**
- ✅ **Válido**: RTN correcto
- ❌ **Inválido**: RTN incorrecto o formato erróneo
- ⚠️ **Pendiente**: Sin RTN (permitido para consumidores finales)

### **2. Validación de CAI (Clave de Autorización de Impresión)**

#### **Validación Automática**
- Se ejecuta al configurar secuencias fiscales
- Valida formato: 9 dígitos numéricos
- Verifica dígito verificador
- Controla fecha de vencimiento

#### **Validación Manual**
```
Menú: Fiscal HN > Validaciones > Secuencias Fiscales
```

**Proceso:**
1. Seleccionar secuencia fiscal
2. Hacer clic en "Validar CAI"
3. Revisar resultado de validación

### **3. Validación de Secuencias Fiscales**

#### **Validación Completa**
```
Menú: Fiscal HN > Validaciones > Secuencias Fiscales
```

**Verificaciones Incluidas:**
- ✅ Configuración de rangos fiscales
- ✅ Formato de prefijos
- ✅ Validación de CAI
- ✅ Control de uso dentro de rangos
- ✅ Verificación de fechas de vencimiento

---

## 🧮 **CÁLCULOS FISCALES**

### **1. Cálculo de ISV (Impuesto sobre Ventas)**

#### **Tasas Aplicables**
- **15%**: Productos y servicios gravados
- **18%**: Productos y servicios gravados (tasa especial)
- **0%**: Productos exentos
- **Exonerado**: Productos exonerados por ley

#### **Cálculo Automático**
El sistema calcula automáticamente:
- **Base Imponible**: Monto sujeto a impuesto
- **ISV 15%**: Impuesto calculado al 15%
- **ISV 18%**: Impuesto calculado al 18%
- **Total ISV**: Suma de todos los impuestos
- **Total Factura**: Base + ISV

#### **Validaciones de Monto Mínimo**
- **Facturas < L. 500**: No requieren numeración fiscal
- **Facturas ≥ L. 500**: Requieren numeración fiscal obligatoria

### **2. Cálculo de Retenciones**

#### **Tipos de Retención**
- **ISR**: Impuesto sobre la Renta
- **ISV**: Impuesto sobre Ventas
- **Otras**: Retenciones especiales

#### **Cálculo Automático**
- **Base Imponible**: Monto sujeto a retención
- **Porcentaje de Retención**: Según tipo de retención
- **Monto Retenido**: Base × Porcentaje

### **3. Validación Fiscal Masiva**

#### **Proceso de Validación**
```
Menú: Fiscal HN > Validaciones > Validación Fiscal Masiva
```

**Pasos:**
1. Seleccionar rango de fechas
2. Elegir tipo de documento (Facturas, Notas de Crédito, etc.)
3. Hacer clic en "Validar Documentos"
4. Revisar reporte de validación
5. Aplicar correcciones automáticas (si están disponibles)

**Correcciones Automáticas:**
- ✅ Cálculo correcto de ISV
- ✅ Aplicación de redondeo matemático
- ✅ Validación de montos mínimos
- ✅ Corrección de bases imponibles

---

## 🔢 **CONTROL DE SECUENCIAS FISCALES**

### **1. Configuración de Secuencias**

#### **Campos de Control Fiscal**
```
Menú: Fiscal HN > Configuraciones > Secuencias Fiscales
```

**Campos Principales:**
- **Es Secuencia Fiscal**: Habilita control fiscal
- **Tipo Fiscal**: Factura, Nota de Crédito, Recibo, etc.
- **Inicio de Rango Fiscal**: Primer número del rango
- **Fin de Rango Fiscal**: Último número del rango
- **Umbral de Alerta**: Porcentaje para generar alertas (80%)
- **Umbral de Advertencia**: Porcentaje para advertencias (90%)
- **Alertas Automáticas**: Generar alertas automáticamente

#### **Validaciones de Configuración**
- ✅ Rango inicial < Rango final
- ✅ Prefijo alfanumérico válido
- ✅ Umbral de alerta < Umbral de advertencia
- ✅ Configuración de CAI (si aplica)

### **2. Estados de Secuencias Fiscales**

#### **Estados Disponibles**
- **🟢 Activo**: Secuencia funcionando normalmente
- **�� Advertencia**: Uso entre 80% y 90%
- **🔴 Crítico**: Uso entre 90% y 100%
- **⚫ Expirado**: Uso supera el 100%

#### **Cálculo de Estados**
```
Porcentaje de Uso = (Número Actual - Inicio de Rango) / (Fin de Rango - Inicio de Rango) × 100
```

### **3. Gestión de Secuencias**

#### **Verificar Estado de Secuencias**
```
Menú: Fiscal HN > Control de Secuencias > Alertas Avanzadas
```

**Acciones Disponibles:**
- **Ver Estado**: Consultar estado actual
- **Reiniciar Secuencia**: Reiniciar numeración
- **Ver Uso**: Consultar documentos generados
- **Extender Rango**: Solicitar nuevo rango

#### **Reinicio de Secuencias**
```
Menú: Fiscal HN > Control de Secuencias > Alertas Avanzadas
```

**Proceso:**
1. Seleccionar secuencia a reiniciar
2. Hacer clic en "Reiniciar Secuencia"
3. Especificar nuevo número de inicio
4. Describir motivo del reinicio
5. Confirmar acción

**⚠️ Advertencias:**
- Solo administradores contables pueden reiniciar
- Se registra en auditoría automáticamente
- Requiere motivo obligatorio

---

## �� **SISTEMA DE ALERTAS**

### **1. Tipos de Alertas**

#### **Alertas de Secuencias**
- **Advertencia**: Uso entre 80% y 90%
- **Crítico**: Uso entre 90% y 100%
- **Expirado**: Uso supera el 100%

#### **Alertas de Validación**
- **RTN Inválido**: RTN con formato incorrecto
- **CAI Inválido**: CAI con formato incorrecto
- **Secuencia Expirada**: Secuencia fuera de rango

### **2. Gestión de Alertas**

#### **Ver Alertas Activas**
```
Menú: Fiscal HN > Control de Secuencias > Alertas Avanzadas
```

**Filtros Disponibles:**
- **Activas**: Alertas pendientes de resolución
- **Reconocidas**: Alertas reconocidas por usuario
- **Resueltas**: Alertas resueltas
- **Por Tipo**: Advertencia, Crítico, Expirado

#### **Proceso de Resolución**
1. **Reconocer Alerta**: Marcar como reconocida
2. **Resolver Alerta**: Marcar como resuelta
3. **Asignar Tarea**: Asignar a usuario específico
4. **Agendar Seguimiento**: Programar fecha de seguimiento

#### **Acciones de Resolución**
- **Extender Rango**: Solicitar nuevo rango al SAR
- **Reiniciar Secuencia**: Reiniciar numeración
- **Solicitar Nuevo Rango**: Crear solicitud formal
- **Otra Acción**: Acción personalizada

### **3. Notificaciones Automáticas**

#### **Configuración de Alertas**
- **Alertas Automáticas**: Generar automáticamente
- **Umbral de Alerta**: 80% por defecto
- **Umbral de Advertencia**: 90% por defecto

#### **Limpieza Automática**
- **Alertas Expiradas**: Se marcan como expiradas después de 30 días
- **Limpieza Programada**: Se ejecuta automáticamente

---

## 📊 **REPORTES FISCALES**

### **1. Reporte de Ventas SAR**

#### **Acceso al Reporte**
```
Menú: Fiscal HN > Informes > Reporte de Ventas SAR
```

#### **Configuración del Reporte**
**Campos de Configuración:**
- **Fecha Desde**: Fecha inicial del período
- **Fecha Hasta**: Fecha final del período
- **Compañía**: Empresa para el reporte
- **Incluir Borradores**: Incluir facturas en borrador
- **Incluir Canceladas**: Incluir facturas canceladas
- **Agrupar por Tasa de Impuesto**: Agrupar por 15% y 18%
- **Agrupar por Tipo de Cliente**: Con RTN vs Sin RTN

#### **Contenido del Reporte Excel**
**Hojas Incluidas:**
1. **Resumen General**: Totales y métricas principales
2. **Detalle por Factura**: Lista detallada de facturas
3. **Resumen por Tasa**: Agrupado por tasa de impuesto
4. **Resumen por Cliente**: Agrupado por tipo de cliente

**Información Incluida:**
- Número de factura y fecha
- Cliente y RTN
- Base imponible e ISV
- Montos exentos y exonerados
- CAI y estado de factura

### **2. Reporte de Retenciones SAR**

#### **Acceso al Reporte**
```
Menú: Fiscal HN > Informes > Reporte de Retenciones SAR
```

#### **Configuración del Reporte**
**Campos de Configuración:**
- **Fecha Desde**: Fecha inicial del período
- **Fecha Hasta**: Fecha final del período
- **Compañía**: Empresa para el reporte
- **Tipo de Retención**: Todas, ISR, ISV, Otras

#### **Contenido del Reporte Excel**
**Hojas Incluidas:**
1. **Resumen General**: Totales de retenciones
2. **Detalle por Retención**: Lista detallada
3. **Resumen por Tipo**: Agrupado por tipo de retención

**Información Incluida:**
- Número de factura y fecha
- Proveedor y RTN
- Base imponible y monto retenido
- Tipo de retención y porcentaje
- CAI del proveedor

### **3. Reporte de Exenciones SAR**

#### **Acceso al Reporte**
```
Menú: Fiscal HN > Informes > Reporte de Exenciones SAR
```

#### **Configuración del Reporte**
**Campos de Configuración:**
- **Fecha Desde**: Fecha inicial del período
- **Fecha Hasta**: Fecha final del período
- **Compañía**: Empresa para el reporte
- **Tipo de Exención**: Todas, Exento, Exonerado

#### **Contenido del Reporte Excel**
**Hojas Incluidas:**
1. **Resumen General**: Totales de exenciones
2. **Detalle por Factura**: Lista detallada
3. **Resumen por Tipo**: Agrupado por tipo de exención
4. **Productos Exentos/Exonerados**: Detalle de productos

**Información Incluida:**
- Número de factura y fecha
- Cliente/Proveedor y RTN
- Montos exentos y exonerados
- Productos específicos
- Tipo de documento

### **4. Proceso de Generación de Reportes**

#### **Pasos Generales**
1. **Configurar Parámetros**: Fechas, filtros, agrupaciones
2. **Generar Reporte**: Hacer clic en "Generar Reporte"
3. **Revisar Resultados**: Verificar totales y datos
4. **Descargar Excel**: Hacer clic en "Descargar Excel"
5. **Guardar Archivo**: Guardar en ubicación segura

#### **Validaciones del Reporte**
- ✅ Verificación de fechas válidas
- ✅ Control de datos existentes
- ✅ Validación de permisos de usuario
- ✅ Verificación de espacio en disco

---

## 🔍 **AUDITORÍA Y SEGURIDAD**

### **1. Auditoría de Secuencias**

#### **Acceso a Auditoría**
```
Menú: Fiscal HN > Control de Secuencias > Auditoría de Secuencias
```

#### **Información Registrada**
**Acciones Auditadas:**
- **Reinicio**: Cambio de numeración
- **Modificación**: Cambio de configuración
- **Creación**: Nueva secuencia fiscal
- **Eliminación**: Eliminación de secuencia

**Información de Contexto:**
- **Usuario**: Quién realizó la acción
- **Fecha y Hora**: Cuándo se realizó
- **IP Address**: Desde dónde se realizó
- **Sesión**: ID de sesión del usuario
- **Motivo**: Justificación de la acción

#### **Filtros de Auditoría**
- **Por Secuencia**: Filtrar por secuencia específica
- **Por Acción**: Reinicio, modificación, etc.
- **Por Usuario**: Filtrar por usuario específico
- **Por Fecha**: Filtrar por período de tiempo

### **2. Control de Permisos**

#### **Grupos de Usuario**
- **Usuario**: Acceso básico a reportes
- **Contador**: Acceso a validaciones y reportes
- **Administrador Contable**: Acceso completo incluyendo reinicio de secuencias

#### **Permisos Específicos**
- **Ver Alertas**: Todos los usuarios
- **Reconocer Alertas**: Contadores y administradores
- **Resolver Alertas**: Contadores y administradores
- **Reiniciar Secuencias**: Solo administradores contables
- **Ver Auditoría**: Contadores y administradores

### **3. Seguridad de Datos**

#### **Validaciones de Seguridad**
- ✅ Verificación de permisos antes de acciones críticas
- ✅ Registro de todas las acciones en auditoría
- ✅ Validación de datos antes de guardar
- ✅ Control de acceso por compañía (multi-compañía)

#### **Buenas Prácticas**
- **Cambiar contraseñas** regularmente
- **Usar sesiones seguras** (HTTPS)
- **Revisar auditoría** periódicamente
- **Hacer backup** de configuraciones fiscales

---

## �� **DASHBOARD Y MÉTRICAS**

### **1. Métricas Principales**

#### **Secuencias Fiscales**
- **Total de Secuencias**: Número total configuradas
- **Secuencias Activas**: Funcionando normalmente
- **Secuencias en Advertencia**: 80-90% de uso
- **Secuencias Críticas**: 90-100% de uso
- **Secuencias Expiradas**: Más del 100% de uso

#### **Alertas**
- **Alertas Activas**: Pendientes de resolución
- **Alertas por Tipo**: Advertencia, Crítico, Expirado
- **Tiempo Promedio de Resolución**: Eficiencia del equipo

#### **Uso de Secuencias**
- **Porcentaje de Uso General**: Promedio de todas las secuencias
- **Secuencias Más Usadas**: Top 5 de secuencias
- **Tendencia de Uso**: Evolución en el tiempo

### **2. Reportes de Tendencias**

#### **Uso Mensual**
- **Facturas Generadas**: Cantidad por mes
- **Uso de Secuencias**: Porcentaje de uso mensual
- **Alertas Generadas**: Cantidad de alertas por mes

#### **Análisis de Eficiencia**
- **Tiempo de Resolución**: Promedio de días para resolver alertas
- **Secuencias por Usuario**: Distribución de uso
- **Errores de Validación**: Frecuencia de errores

### **3. Configuración de Dashboard**

#### **Personalización**
- **Métricas Favoritas**: Configurar métricas principales
- **Alertas Personalizadas**: Configurar umbrales específicos
- **Reportes Automáticos**: Programar envío de reportes

---

## 🔧 **SOLUCIÓN DE PROBLEMAS**

### **1. Problemas Comunes**

#### **Error: "RTN Inválido"**
**Causa:** RTN con formato incorrecto o dígito verificador erróneo
**Solución:**
1. Verificar formato: 9 dígitos numéricos
2. Validar dígito verificador
3. Consultar con el SAR si es necesario

#### **Error: "CAI Inválido"**
**Causa:** CAI con formato incorrecto o vencido
**Solución:**
1. Verificar formato: 9 dígitos numéricos
2. Validar fecha de vencimiento
3. Renovar CAI si es necesario

#### **Error: "Secuencia Expirada"**
**Causa:** Secuencia fuera del rango autorizado
**Solución:**
1. Solicitar nuevo rango al SAR
2. Reiniciar secuencia (solo administradores)
3. Configurar nueva secuencia

#### **Error: "No se pueden generar reportes"**
**Causa:** Sin datos en el período seleccionado
**Solución:**
1. Verificar fechas del reporte
2. Confirmar existencia de documentos
3. Revisar filtros aplicados

### **2. Validaciones del Sistema**

#### **Verificar Configuración**
```
Menú: Fiscal HN > Validaciones > Validación Fiscal Masiva
```

**Pasos:**
1. Seleccionar período reciente
2. Ejecutar validación completa
3. Revisar reporte de errores
4. Aplicar correcciones automáticas

#### **Verificar Secuencias**
```
Menú: Fiscal HN > Control de Secuencias > Alertas Avanzadas
```

**Pasos:**
1. Revisar estado de todas las secuencias
2. Identificar secuencias problemáticas
3. Tomar acciones correctivas
4. Documentar cambios realizados

### **3. Contacto de Soporte**

#### **Información Necesaria**
- **Versión de Odoo**: 18.0.x
- **Versión del Módulo**: kc_fiscal_hn
- **Descripción del Problema**: Detalle específico
- **Pasos para Reproducir**: Secuencia de acciones
- **Logs de Error**: Si están disponibles

#### **Canales de Soporte**
- **Documentación**: Esta guía completa
- **Foros de Odoo**: Comunidad de usuarios
- **Soporte Técnico**: Contacto directo con desarrolladores

---

## �� **GLOSARIO TÉCNICO**

### **Términos Fiscales**

#### **RTN (Registro Tributario Nacional)**
- **Definición**: Número único de identificación fiscal
- **Formato**: 9 dígitos numéricos
- **Validación**: Algoritmo de dígito verificador del SAR

#### **CAI (Clave de Autorización de Impresión)**
- **Definición**: Clave que autoriza la impresión de documentos fiscales
- **Formato**: 9 dígitos numéricos
- **Vigencia**: Tiene fecha de vencimiento específica

#### **ISV (Impuesto sobre Ventas)**
- **Definición**: Impuesto aplicado a la venta de bienes y servicios
- **Tasas**: 15% (general), 18% (especial), 0% (exento)
- **Cálculo**: Sobre base imponible

#### **Base Imponible**
- **Definición**: Monto sobre el cual se calcula el impuesto
- **Exclusión**: No incluye montos exentos o exonerados
- **Cálculo**: Subtotal - Descuentos + Cargos

### **Términos del Sistema**

#### **Secuencia Fiscal**
- **Definición**: Numeración autorizada por el SAR
- **Rango**: Conjunto de números autorizados
- **Control**: Monitoreo de uso y estado

#### **Alerta**
- **Definición**: Notificación de situación que requiere atención
- **Tipos**: Advertencia, Crítico, Expirado
- **Gestión**: Reconocimiento y resolución

#### **Auditoría**
- **Definición**: Registro de todas las acciones realizadas
- **Propósito**: Trazabilidad y control
- **Retención**: Historial completo de cambios

#### **Validación**
- **Definición**: Verificación automática de datos
- **Tipos**: RTN, CAI, Secuencias, Cálculos
- **Resultado**: Aprobado, Rechazado, Pendiente

### **Términos de Reportes**

#### **Reporte SAR**
- **Definición**: Documento oficial para el SAR
- **Tipos**: Ventas, Retenciones, Exenciones
- **Formato**: Excel (.xls)

#### **Agrupación**
- **Definición**: Organización de datos por criterios
- **Tipos**: Por tasa, por cliente, por fecha
- **Propósito**: Análisis y presentación

#### **Filtros**
- **Definición**: Criterios para seleccionar datos
- **Tipos**: Fecha, estado, tipo de documento
- **Aplicación**: Antes de generar reporte

---

## �� **CONCLUSIÓN**

El módulo **kc_fiscal_hn** proporciona una solución completa y robusta para el cumplimiento fiscal en Honduras. Con sus validaciones automáticas, cálculos precisos, reportes completos y sistema avanzado de control, garantiza el cumplimiento de todos los requerimientos del SAR.

### **Beneficios Principales**
- ✅ **Cumplimiento Automático**: Validaciones y cálculos automáticos
- ✅ **Control Total**: Monitoreo completo de secuencias fiscales
- ✅ **Reportes Oficiales**: Generación de reportes requeridos por el SAR
- ✅ **Auditoría Completa**: Trazabilidad de todas las acciones
- ✅ **Interfaz Intuitiva**: Fácil de usar y entender

### **Recomendaciones**
1. **Configurar correctamente** todas las secuencias fiscales
2. **Revisar regularmente** las alertas del sistema
3. **Validar periódicamente** los datos fiscales
4. **Mantener actualizada** la documentación
5. **Capacitar al personal** en el uso del módulo

### **Soporte Continuo**
El módulo está diseñado para evolucionar con los cambios en la normativa fiscal hondureña. Se recomienda mantener actualizada la versión del módulo para aprovechar las últimas funcionalidades y correcciones.

---

**📞 Para soporte técnico o consultas adicionales, contacte al equipo de desarrollo del módulo kc_fiscal_hn.**