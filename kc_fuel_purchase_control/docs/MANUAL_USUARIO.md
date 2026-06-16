# Manual de usuario — Control de combustible (KC Fuel Purchase Control)

Este módulo enlaza **vales internos de combustible**, **órdenes de compra** y **facturas de proveedor**, con **historial de consumo** y cálculo de **rendimiento** (distancia por unidad de combustible).

---

## Requisitos previos

- Módulos de Odoo: **Compras**, **Contabilidad**, **Empleados** (para motoristas), **Analítica** (cuentas analíticas opcionales).
- **Productos** de combustible configurados en Inventario/Compras (con **costo estándar** si autorizará por volumen).
- **Contactos** marcados como **proveedores** para el surtidor o estación.
- Asignación de grupos de seguridad (ver más abajo).

---

## Dónde está el menú

En **Compras** aparece el submenú **Combustible**, con:

| Entrada | Uso |
|--------|-----|
| **Vehículos** | Maestro de flota: placa, motorista, producto por defecto, odómetro, etc. |
| **Vales de combustible** | Flujo principal: solicitud → aprobación → OC → factura. |
| **Historial de consumo** | Registros generados al validar facturas de combustible; análisis en pivote y gráfico. |

---

## Roles (grupos de seguridad)

| Grupo | Qué puede hacer |
|-------|------------------|
| **Usuario Combustible** | Ver vehículos (solo lectura). Crear y editar vales; **no** borrar vales ni gestionar vehículos. Ver historial de consumo (solo lectura). |
| **Manager Combustible** | Todo lo anterior, más: crear/editar/borrar **vehículos**; **aprobar** vales, **crear OC**, **cerrar** y **cancelar** vales; gestionar historial con permisos completos. |

Los botones **Solicitar**, **Aprobar**, **Crear OC**, **Cerrar**, **Cancelar** y **Reiniciar a borrador** están restringidos según estos grupos en el formulario del vale.

---

## 1. Configurar vehículos (Manager)

1. **Combustible → Vehículos → Crear**.
2. Complete al menos **Nombre**, **Placa** (única por compañía), y si aplica **Motorista**, **Tipo de combustible**, **Producto combustible** por defecto, **Cuenta analítica**, **Unidad de distancia** (km o millas), **Odómetro actual** y **Rendimiento esperado** (distancia por unidad de volumen del combustible).
3. Al elegir un vehículo en un vale, el sistema **rellena** motorista, producto, cuenta analítica, último odómetro, tipo de combustible y unidad de medida del producto cuando corresponde.

---

## 2. Crear y tramitar un vale

### Datos obligatorios

- **Vehículo** y **Proveedor** (debe ser proveedor en Odoo).
- **Producto combustible**.
- **Monto autorizado** *o* **Galones/volumen autorizado** (al menos uno mayor que cero).  
  - Si indica **ambos**, al generar la orden de compra **rige el monto** para el importe de la línea.
- Si solo indica **volumen**, el importe estimado de la OC usa el **costo estándar** del producto × cantidad.

### Odómetros

- **Último odómetro**: referencia del recorrido (suele venir del vehículo).
- **Odómetro proyectado**: no puede ser menor que el último odómetro. La **distancia proyectada** se calcula en la misma unidad que el odómetro (km o millas según el vale/vehículo).

### Flujo de estados

1. **Borrador** — edición libre.
2. **Solicitar** — pasa a **Solicitado** (workflow interno).
3. **Aprobar** — **Manager**; pasa a **Aprobado**.
4. **Crear OC** — **Manager**; genera una **orden de compra** de combustible con una línea (cantidad 1 en la U.M. del producto; el **precio unitario** refleja el monto autorizado o el estimado por volumen). El vale pasa a **OC creada**.
5. En **Compras**, confirme la OC, reciba y cree la **factura de proveedor** desde el flujo habitual (por ejemplo “Crear factura” / facturación desde la OC).

### Al registrar la factura de proveedor

La factura debe estar ligada a la OC de combustible (origen correcto). Al **publicar** la factura de proveedor:

- Si es una **factura de combustible** vinculada al vale, debe cumplirse:
  - **Vehículo** indicado en la pestaña **Combustible** de la factura (o heredado desde la OC).
  - **Odómetro real** obligatorio y coherente (no menor que el último odómetro del vale).
  - Debe haber **cantidad** en las líneas para el **mismo producto combustible** del vale (la “cantidad real” se toma de ahí).

Tras validar la factura, el sistema:

- Marca el vale como **Facturado**, guarda **monto real** y **odómetro real** en el vale.
- Crea un registro en **Historial de consumo**.
- **Actualiza el odómetro actual del vehículo** con el odómetro real de la factura.

6. **Cerrar** — **Manager**, cuando el vale en **Facturado** ya no requiere seguimiento; pasa a **Cerrado**.

**Cancelar** (Manager) puede usarse desde varios estados previos a facturación; **Reiniciar a borrador** según política interna (típicamente desde **Cancelado**).

---

## 3. Orden de compra de combustible

En la OC generada desde el vale verá el bloque **Combustible** (cuando es orden de combustible): vale, vehículo, motorista, odómetros y motivo. Esos datos son de referencia para compras y contabilidad.

---

## 4. Factura de proveedor — pestaña Combustible

Además de la pestaña **Combustible** con odómetro y métricas, puede marcarse **Factura de combustible** y revisarse el vínculo al **Vale**. Campos calculados útiles:

- **Cantidad real combustible** (suma de líneas del producto del vale).
- **Distancia recorrida** y **Rendimiento real** (distancia ÷ cantidad; no es porcentaje).

---

## 5. Historial de consumo

**Combustible → Historial de consumo** lista cada cierre con factura: vehículo, cantidades, distancia, eficiencia, montos y cuenta analítica. Las vistas **Pivote** y **Gráfico** permiten analizar consumo por período, vehículo o proveedor.

Cada factura de combustible genera **como máximo un** registro de historial por factura (evita duplicados).

---

## 6. Impresión del vale

En el formulario del vale use **Imprimir vale** para obtener el reporte PDF del vale interno.

---

## 7. Numeración

- Vales: secuencia tipo `FUELV/AÑO/####`.
- Historial: secuencia tipo `FLOG/AÑO/####`.

---

## Preguntas frecuentes

**¿Por qué no me deja publicar la factura de combustible?**  
Falta vehículo, odómetro real, vínculo al vale o no hay cantidad del producto combustible en las líneas. Revise mensajes de error al confirmar.

**¿Por qué el importe de la OC es cero o no me deja crear la OC?**  
Debe haber monto autorizado o volumen con **costo estándar** del producto &gt; 0 para que el importe sea mayor que cero.

**¿El usuario normal puede borrar vales?**  
No; solo el **Manager** tiene permiso de borrado en vales. Los usuarios suelen crear y editar, no eliminar.

---

*Módulo: KC Fuel Purchase Control (Odoo 18). Documentación orientativa; ajuste procesos internos (aprobaciones, límites) según su empresa.*
