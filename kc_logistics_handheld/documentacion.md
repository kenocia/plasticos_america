# KC Logística Handheld — Documentación

**Módulo:** `kc_logistics_handheld`  
**Versión:** 18.0.1.2.1  
**Plataforma:** Odoo 18  
**Dependencias:** `stock`, `barcodes`, `kc_plasticasa`

---

# 1. Resumen gerencial

## ¿Qué problema resuelve?

Centraliza en una **aplicación móvil (handheld)** las operaciones logísticas de almacén que hoy requieren escaneo GS1: despacho de entregas, movimientos internos por lote y levantamiento físico previo. Reduce digitación manual, errores de producto/lote y tiempos de búsqueda en pantallas de escritorio.

## Valor para el negocio

| Beneficio | Descripción |
|-----------|-------------|
| **Operación unificada** | Un solo menú «Logística» con tres flujos diferenciados según el rol del operador. |
| **Trazabilidad GS1** | Cada escaneo queda registrado (internos: historial auditable por sesión, usuario y transferencia). |
| **Menos errores** | Validación automática de producto, lote, cantidad y disponibilidad en ubicación antes de mover stock. |
| **Control de acceso granular** | Cada usuario ve solo las operaciones que el administrador le habilita (despachos, internos o físico). |
| **Adaptado a dispositivos móviles** | Botones grandes, kanban de despachos optimizado y foco automático en el campo de escaneo. |

## Alcance del módulo

**Incluye:**

- App «Logística» en el menú principal de Odoo.
- Kanban de entregas pendientes/disponibles con acceso directo al escáner GS1 de despacho (proporcionado por `kc_plasticasa`).
- Wizard de transferencias internas por lotes GS1 con creación y validación automática del albarán.
- Acceso handheld al levantamiento físico previo (modelo de `kc_plasticasa`).
- Historial de escaneos internos para supervisión.
- Permisos por usuario y grupo de seguridad «Operador Logística Handheld».

**No incluye:**

- Generación de códigos QR GS1 (se asume que ya existen en producción/etiquetado).
- Operación sin conexión (offline).
- Despachos o físico sin el módulo base `kc_plasticasa`.

## Indicadores sugeridos de seguimiento

- Tiempo promedio entre apertura de entrega y validación de despacho.
- Cantidad de escaneos internos por día / por operador.
- Tasa de rechazo de QR (errores de producto, lote o ubicación).
- Sesiones de toma física abiertas vs. cerradas.

## Requisitos previos de implementación

1. Instalar `kc_logistics_handheld` y su dependencia `kc_plasticasa`.
2. Asignar el grupo **Operador Logística Handheld** a los usuarios de almacén.
3. Configurar en cada usuario qué operaciones puede ejecutar (pestaña «Logística Handheld»).
4. Para **despachos**: activar «Wizard GS1 de despacho» en los tipos de operación de salida correspondientes (`kc_plasticasa`).
5. Para **internos**: verificar que los tipos de operación interna tengan ubicación origen y destino; opcionalmente marcar «baja calidad» si aplica.
6. Para **físico**: configurar ubicaciones permitidas en la compañía (`kc_plasticasa`).

## Riesgos y consideraciones

- Los internos validan disponibilidad en la **ubicación exacta** configurada en el tipo de operación (no incluye sububicaciones).
- Un mismo lote no puede escanearse dos veces en la misma sesión interna.
- El módulo absorbió funcionalidad del antiguo `kc_internal_lot_scanner`; la migración es automática al instalar.

---

# 2. Documento funcional para el usuario

## 2.1 Acceso a la aplicación

1. Inicie sesión en Odoo con su usuario de almacén.
2. En el menú principal, abra **Logística → Operaciones**.
3. Verá la pantalla inicial con uno o más botones según sus permisos:
   - **Despachos** — entregas a clientes.
   - **Operaciones internas** — movimientos entre ubicaciones por lote.
   - **Toma física previo** — conteo/verificación física de lotes.

> Si no aparece ningún botón, el sistema mostrará el mensaje: *«No tiene operaciones habilitadas. Solicite permisos al administrador.»*

### Permisos (configurados por el administrador)

En **Ajustes → Usuarios**, pestaña **Logística Handheld**:

| Campo | Permite |
|-------|---------|
| Handheld: Despachos | Ver kanban de entregas y escanear GS1 en despachos |
| Handheld: Operaciones internas | Abrir wizard de transferencia interna GS1 |
| Handheld: Toma física previo | Ver y trabajar sesiones de levantamiento físico en borrador |

Además, el usuario debe pertenecer al grupo **Operador Logística Handheld**.

---

## 2.2 Despachos GS1

### ¿Cuándo usarlo?

Cuando debe preparar y despachar una **entrega de salida** escaneando los códigos QR GS1 de los lotes que salen al cliente.

### Flujo paso a paso

1. En la pantalla inicial, pulse **Despachos**.
2. Se abre un **kanban** con las entregas en estado:
   - **En espera** (amarillo): aún no tiene stock reservado o está pendiente de disponibilidad.
   - **Disponible** (verde): lista para operar.
3. Use el buscador para localizar por número de entrega, pedido u origen.
4. Filtre por «En espera» o «Disponible» si lo necesita.
5. Pulse **Escanear GS1** en la tarjeta de la entrega deseada.
6. Se abre el wizard de escaneo GS1 de despacho (de `kc_plasticasa`):
   - Escanee cada QR de lote.
   - El sistema valida producto, lote y cantidad contra el pedido.
   - Al finalizar, valide la entrega según el flujo habitual.
7. Para volver al menú principal, use el botón **Menú principal** en la cabecera del kanban.

### Qué entregas aparecen

Solo las que cumplen **todas** estas condiciones:

- Tipo de operación: **salida** (`outgoing`).
- Estado: en espera, confirmada o disponible.
- El tipo de operación tiene activo **Wizard GS1 de despacho** (configuración de inventario).

---

## 2.3 Operaciones internas GS1

### ¿Cuándo usarlo?

Cuando debe mover lotes entre ubicaciones internas del almacén (por ejemplo, de producción a expedición, o a zona de baja calidad) escaneando QR GS1.

### Flujo paso a paso

1. En la pantalla inicial, pulse **Operaciones internas**.
2. Seleccione el **tipo de operación interna** (ej.: «Traslado interno», «Baja calidad», etc.).
   - Al elegirlo, el sistema carga automáticamente las ubicaciones **Origen** y **Destino** del tipo de operación.
3. Si el tipo de operación está marcado como «baja calidad», verá una advertencia: los lotes escaneados se marcarán como baja calidad al validar.
4. En el campo **Escanear QR GS1**, lea o pegue el código del lote.
   - El cursor vuelve automáticamente al campo tras cada escaneo (optimizado para pistola lectora).
5. Revise el **resultado del escaneo**:
   - **Verde (éxito):** lote agregado correctamente.
   - **Rojo (error):** motivo del rechazo (ver sección de errores).
6. En la lista **Lotes escaneados** puede eliminar una línea errónea con el icono de papelera.
7. Cuando termine de escanear todos los lotes, pulse **Crear y Validar Transferencia**.
   - El sistema crea el albarán interno, asigna cantidades por lote y lo valida automáticamente.
8. Tras finalizar, puede pulsar **Ver transferencia** para abrir el albarán generado, o **Cerrar** para salir.

### Formato del QR GS1 esperado

El código debe contener, como mínimo:

| Bloque GS1 | Contenido |
|------------|-----------|
| `240` | Código de producto |
| `10` | Número de lote |
| `30` | Cantidad (entera) |

El sistema acepta códigos con separadores GS1 estándar o concatenados.

### Reglas importantes

- No puede escanear el **mismo lote dos veces** en la misma sesión.
- El lote debe **existir** en Odoo para ese producto.
- Debe haber **stock disponible** en la ubicación origen exacta (cantidad del QR).
- Si el lote está en otra ubicación, el sistema indicará que no está disponible en el origen configurado.

---

## 2.4 Toma física previo

### ¿Cuándo usarlo?

Para registrar en terreno qué lotes existen físicamente en el almacén, comparando cantidades y ubicaciones contra lo que Odoo tiene registrado.

### Flujo paso a paso

1. En la pantalla inicial, pulse **Toma física previo**.
2. Se listan las sesiones en estado **En curso** (borrador).
3. Abra una sesión existente o cree una nueva (desde la lista, si está permitido).
4. Si la compañía tiene varias ubicaciones físicas configuradas, seleccione la **ubicación física por defecto** de la sesión.
5. Pulse **Escanear GS1** y lea los QR de los lotes encontrados en piso.
6. Revise la pestaña **Lotes escaneados**:
   - Cantidad según QR vs. cantidad en Odoo.
   - Ubicación reportada vs. ubicación en sistema.
   - Las filas en rojo indican discrepancia de ubicación.
7. Al terminar el recorrido, pulse **Cerrar sesión**.

> La lógica detallada de escaneo, comparación y ajustes masivos está en el módulo `kc_plasticasa`. Esta app solo proporciona el acceso móvil filtrado a sesiones en borrador.

---

## 2.5 Historial de escaneos internos (supervisores)

Disponible en **Logística → Historial escaneos GS1 internos** (requiere rol de responsable de inventario).

Permite consultar:

- Fecha, usuario, producto, lote, cantidad.
- Ubicaciones origen y destino.
- Albarán generado.
- Estado: Escaneado, Transferido o Cancelado.

Filtros útiles: por usuario, producto, lote, transferencia, fecha y estado.

---

## 2.6 Configuración para administradores

### Usuarios

**Ajustes → Usuarios → [usuario] → Logística Handheld**

Active los toggles según el perfil del operador.

### Tipos de operación interna

**Inventario → Configuración → Tipos de operación → [tipo interno] → sección GS1 Interno**

| Campo | Función |
|-------|---------|
| Disponible en wizard interno GS1 | Si está activo, el tipo aparece en el desplegable del wizard handheld. |
| Marcar lotes como baja calidad | Al validar la transferencia, marca `baja calidad` en todos los lotes escaneados. |

> Al instalar el módulo, todos los tipos internos existentes se activan automáticamente en el wizard.

### Tipos de operación de despacho

**Inventario → Configuración → Tipos de operación → [tipo salida]**

Active **Wizard GS1 de despacho** (campo de `kc_plasticasa`) en los tipos de entrega que deban operarse desde handheld.

### Toma física

**Ajustes → Compañías → [compañía]**

Configure las ubicaciones físicas permitidas para el levantamiento (`kc_plasticasa`).

---

## 2.7 Mensajes de error frecuentes (operaciones internas)

| Mensaje | Causa probable | Acción recomendada |
|---------|----------------|-------------------|
| QR inválido. El primer bloque debe iniciar con 240 | Código dañado o no es GS1 de producto | Reescanear; verificar etiqueta |
| Producto no encontrado para el código GS1 | El código 240 no coincide con barcode, referencia ni código GS1 del producto | Verificar maestro de productos |
| El lote X no existe para el producto Y | Lote no creado en Odoo | Crear lote o corregir etiqueta |
| El lote existe, pero no está disponible en la ubicación origen | Stock en otra ubicación | Mover stock primero o cambiar tipo de operación |
| No tiene disponibilidad suficiente | Cantidad en QR mayor que stock libre en origen | Verificar cantidad del QR o stock |
| Este lote ya fue escaneado en esta sesión | Duplicado | Eliminar línea si fue error, o continuar con otro lote |
| Debe seleccionar un tipo de operación interna | Falta elegir operación | Seleccionar tipo antes de escanear |
| No tiene permiso para operar despachos / esta operación | Permiso no asignado | Solicitar al administrador |

---

## 2.8 Buenas prácticas en piso

1. **Antes de escanear internos:** confirme que eligió el tipo de operación correcto (origen/destino).
2. **Una sesión por tarea:** no mezcle movimientos de distintos traslados en la misma sesión interna.
3. **Revise la lista** antes de «Crear y Validar»; es más fácil corregir antes que revertir un albarán validado.
4. **Despachos:** priorice entregas en estado **Disponible** para evitar esperas por reserva.
5. **Físico:** cierre la sesión al terminar cada recorrido para mantener el listado limpio.

---

## 2.9 Glosario

| Término | Significado |
|---------|-------------|
| **GS1** | Estándar de códigos de barras/QR con bloques de datos (AI 240, 10, 30, etc.). |
| **Sesión** | Agrupación de escaneos de una operación antes de generar el albarán (internos) o antes del cierre (físico). |
| **Handheld** | Interfaz optimizada para uso en dispositivo móvil o terminal con lector de códigos. |
| **Kanban de despachos** | Vista de tarjetas con entregas pendientes y botón de escaneo directo. |
| **Baja calidad** | Marca en el lote que indica material no apto para venta normal; se activa según tipo de operación. |

---

# 3. Documentación técnica

| Archivo | Contenido |
|---------|-----------|
| [`docs/state_stock.md`](docs/state_stock.md) | Estado técnico: modelos, campos, vistas, reglas, riesgos |
| [`docs/decisions.md`](docs/decisions.md) | Decisiones de arquitectura (ADR) |
| [`docs/changelog.md`](docs/changelog.md) | Historial de versiones y migraciones |
| [`docs/test_matrix.md`](docs/test_matrix.md) | Matriz de pruebas manuales |

---

*Documento generado a partir del análisis del código fuente de `kc_logistics_handheld` v18.0.1.2.1.*
