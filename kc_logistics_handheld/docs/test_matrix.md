# Matriz de pruebas — kc_logistics_handheld

Casos manuales clave. Marcar: ✅ OK · ❌ Falla · ⏭ N/A

**Precondiciones generales:**
- Módulos `kc_logistics_handheld` y `kc_plasticasa` instalados.
- Usuario de prueba con grupo **Operador Logística Handheld**.
- Productos con lote, stock en ubicaciones configuradas, QR GS1 válidos (240/10/30).

---

## 1. Acceso y permisos

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| P-01 | Sin grupo handheld | Usuario solo `stock.group_stock_user`, sin grupo Logística | No ve menú «Logística» | |
| P-02 | Grupo sin booleanos | Grupo handheld; los 3 booleanos en False | Menú visible; launcher muestra aviso «No tiene operaciones habilitadas» | |
| P-03 | Solo despachos | `kc_logistics_handheld_despachos=True`, resto False | Solo botón Despachos visible | |
| P-04 | Solo internos | `kc_logistics_handheld_internos=True`, resto False | Solo botón Operaciones internas | |
| P-05 | Solo físico | `kc_logistics_handheld_fisico=True`, resto False | Solo botón Toma física previo | |
| P-06 | Los tres permisos | Los 3 booleanos True | Tres botones visibles | |
| P-07 | Acceso sin permiso vía RPC | Usuario sin despachos intenta abrir acción despachos | UserError de permiso | |

---

## 2. Launcher y navegación

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| N-01 | Abrir app | Logística → Operaciones | Formulario launcher a pantalla completa (`target=main`) | |
| N-02 | Volver al menú desde despachos | Despachos → Menú principal | Vuelve al launcher | |
| N-03 | Rutas URL | Navegar a `/odoo/logistics`, `/odoo/logistics-despachos`, etc. | Carga acción correcta sin error | |

---

## 3. Despachos GS1

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| D-01 | Kanban filtra salidas | Abrir Despachos | Solo pickings `outgoing` en waiting/confirmed/assigned | |
| D-02 | Filtro wizard GS1 | Tipo salida sin `kc_enable_gs1_dispatch_wizard` | No aparece en kanban | |
| D-03 | Etiqueta En espera | Picking en `waiting` o `confirmed` | Badge amarillo «En espera» | |
| D-04 | Etiqueta Disponible | Picking en `assigned` | Badge verde «Disponible» | |
| D-05 | Búsqueda | Buscar por nombre entrega / origin / pedido | Filtra correctamente | |
| D-06 | Abrir escáner | Escanear GS1 en tarjeta | Abre wizard `kc.gs1.picking.scan.wizard` (plasticasa) | |
| D-07 | Sin permiso despachos | Usuario sin booleano despachos pulsa Escanear GS1 | UserError | |

---

## 4. Operaciones internas GS1 — escaneo

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| I-01 | Sin tipo de operación | Escanear QR sin elegir tipo | Advertencia: debe seleccionar operación | |
| I-02 | QR válido con separadores GS1 | Escanear código 240+10+30 con FNC1 | Línea agregada; mensaje éxito verde | |
| I-03 | QR concatenado | Escanear sin separadores (formato compacto) | Parseo correcto; línea agregada | |
| I-04 | QR inválido (sin 240) | Escanear código EAN simple | Error: primer bloque debe iniciar con 240 | |
| I-05 | Producto inexistente | QR con código 240 no registrado | Error: producto no encontrado | |
| I-06 | Lote inexistente | QR con lote no creado en Odoo | Error: lote no existe | |
| I-07 | Stock en otra ubicación | Lote con stock solo en ubicación distinta al origen del tipo | Error: no disponible en ubicación origen | |
| I-08 | Stock insuficiente | QR con cantidad mayor al disponible en origen | Error con disponible vs. requerido | |
| I-09 | Duplicado mismo lote | Escanear mismo lote dos veces en sesión | Error: ya escaneado | |
| I-10 | Eliminar línea | Papelera en línea escaneada | Línea eliminada; log pasa a `cancelled` | |
| I-11 | Foco automático | Tras escaneo exitoso | Cursor vuelve al campo QR | |
| I-12 | Advertencia baja calidad | Tipo con `kc_mark_low_quality=True` | Alerta visible antes de escanear | |

---

## 5. Operaciones internas GS1 — validación

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| V-01 | Sin líneas | Crear y Validar con lista vacía | Error: no hay lotes escaneados | |
| V-02 | Flujo feliz | Escanear N lotes → Crear y Validar | Picking interno `done`; sesión `done`; logs `transferred` | |
| V-03 | Move lines por lote | Revisar picking generado | Una move_line por lote con cantidad del QR | |
| V-04 | Origen en picking | Revisar campo origin del picking | Contiene referencia sesión GS1INT y usuario | |
| V-05 | Ver transferencia | Tras validar, botón Ver transferencia | Abre formulario del picking creado | |
| V-06 | Sesión finalizada | Intentar escanear tras `state=done` | No permite nuevos escaneos | |
| V-07 | Marca baja calidad | Tipo con flag activo; validar | Lotes escaneados con `low_quality=True` | |
| V-08 | Revalidación stock | Otro usuario consume stock entre escaneo y validar | Error al validar si ya no hay disponibilidad | |

---

## 6. Toma física previo

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| F-01 | Listado borradores | Abrir Toma física previo | Solo sesiones `state=draft` | |
| F-02 | Escanear en sesión | Abrir sesión → Escanear GS1 | Wizard plasticasa abre correctamente | |
| F-03 | Cerrar sesión | Cerrar sesión con líneas | Estado `done`; desaparece del listado handheld | |
| F-04 | Sin permiso físico | Usuario sin booleano físico | No ve botón en launcher | |

---

## 7. Historial y administración

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| H-01 | Acceso historial | Usuario stock manager | Ve menú Historial escaneos GS1 internos | |
| H-02 | Filtro transferidos | Abrir historial (default) | Filtro «Transferido» activo por defecto | |
| H-03 | Tipo operación interno | Desactivar `kc_enable_internal_lot_scanner` | Tipo no aparece en wizard interno | |
| H-04 | Post-init tipos internos | Instalar en BD con tipos internos | Todos quedan con scanner habilitado | |

---

## 8. Migración kc_internal_lot_scanner

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| M-01 | Metadatos migrados | Instalar con `kc_internal_lot_scanner` previo | `ir.model.data` apunta a `kc_logistics_handheld` | |
| M-02 | Módulo antiguo | Tras migración | `kc_internal_lot_scanner` en estado `to remove` | |

---

## 9. Regresión multi-compañía (si aplica)

| ID | Caso | Pasos | Resultado esperado | Estado |
|----|------|-------|-------------------|--------|
| C-01 | Tipos por compañía | Usuario en compañía A | Solo tipos internos de compañía A (o sin compañía) en wizard | |
| C-02 | Lotes por compañía | Escanear lote de otra compañía | Error o lote no encontrado según reglas | |

---

## Notas de ejecución

| Campo | Valor |
|-------|-------|
| Entorno probado | |
| Versión Odoo | 18.0 |
| Versión módulo | 18.0.1.2.1 |
| Ejecutado por | |
| Fecha | |
