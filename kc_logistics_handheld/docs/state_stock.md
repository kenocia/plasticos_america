# Estado Stock — kc_logistics_handheld

## Scope del módulo

**Cubre:**
- App «Logística» handheld con launcher y tres flujos: despachos, internos GS1 y toma física previo.
- Kanban móvil de entregas (`stock.picking` salida) con acceso al wizard GS1 de despacho (`kc_plasticasa`).
- Wizard de transferencia interna por lotes GS1: sesión, escaneo, creación y validación automática de `stock.picking` interno.
- Modelos de auditoría: `kc.internal.lot.scan.session`, `kc.internal.lot.scan.log`.
- Permisos por usuario (booleanos) y grupo de seguridad «Operador Logística Handheld».
- Campos en `stock.picking.type` para habilitar wizard interno y marcar baja calidad.
- Historial de escaneos internos (solo responsables de inventario).
- Assets JS/CSS para foco automático en escaneo y UI móvil.

**No cubre:**
- Lógica de despacho GS1 (wizard, tolerancias, reservas): vive en `kc_plasticasa`.
- Levantamiento físico previo (sesiones, líneas, comparación): vive en `kc_plasticasa`; este módulo solo expone el acceso handheld.
- Generación de etiquetas QR GS1.
- Operación offline.
- Cambios a valoración contable o reglas de reabastecimiento.

---

## Modelos tocados

| Modelo | Tipo | Uso |
|--------|------|-----|
| `stock.picking` | extensión | Etiquetas handheld, grupo kanban, navegación a GS1 despacho y menú principal |
| `stock.picking.type` | extensión | `kc_enable_internal_lot_scanner`, `kc_mark_low_quality` |
| `res.users` | extensión | Permisos booleanos despachos / internos / físico |
| `kc.logistics.handheld.launcher` | wizard transient | Pantalla inicial con botones según permisos |
| `kc.internal.lot.transfer.wizard` | wizard transient | Escaneo GS1, validación, creación de picking interno |
| `kc.internal.lot.scan.session` | nuevo | Agrupa escaneos de una operación interna |
| `kc.internal.lot.scan.session.line` | nuevo | Línea escaneada (producto, lote, qty, QR raw) |
| `kc.internal.lot.scan.log` | nuevo | Auditoría por escaneo (scanned / transferred / cancelled) |
| `kc.physical.lot.scan.session` | uso (`kc_plasticasa`) | Acceso handheld filtrado a borradores |
| `kc.gs1.picking.scan.wizard` | uso (`kc_plasticasa`) | Invocado desde kanban de despachos |

---

## Campos añadidos

### `stock.picking`
| Campo | Tipo | Compute / Store |
|-------|------|-----------------|
| `kc_handheld_state_label` | Char | compute `_compute_kc_handheld_state_label` |
| `kc_handheld_state_group` | Selection (`waiting`, `assigned`) | compute + store, `@depends('state')`, search custom |

### `stock.picking.type`
| Campo | Tipo | Default |
|-------|------|---------|
| `kc_enable_internal_lot_scanner` | Boolean | True |
| `kc_mark_low_quality` | Boolean | False |

### `res.users`
| Campo | Tipo |
|-------|------|
| `kc_logistics_handheld_despachos` | Boolean |
| `kc_logistics_handheld_internos` | Boolean |
| `kc_logistics_handheld_fisico` | Boolean |

Incluidos en `SELF_READABLE_FIELDS` para lectura fiable en cliente.

### `kc.internal.lot.scan.session`
`name` (secuencia GS1INT/), `user_id`, `picking_type_id`, `location_id`, `location_dest_id`, `picking_id`, `state` (draft/done/cancelled), `line_ids`, `created_date`, `validated_date`, `mark_low_quality`, `company_id`.

### `kc.internal.lot.scan.session.line`
`session_id`, `product_id`, `lot_id`, `qty`, `product_uom_id`, `barcode_raw`, `location_id`, `location_dest_id`.  
SQL: `unique(session_id, lot_id)`.

### `kc.internal.lot.scan.log`
`name` (secuencia GS1LOG/), `session_name`, `picking_id`, `picking_type_id`, `product_id`, `lot_id`, `qty`, `product_uom_id`, `location_id`, `location_dest_id`, `barcode_raw`, `user_id`, `scan_date`, `state` (scanned/transferred/cancelled), `company_id`.

---

## Vistas afectadas

| Vista / menú | Archivo |
|--------------|---------|
| Launcher handheld | `views/logistics_handheld_launcher_views.xml` |
| Kanban despachos + búsqueda | `views/stock_picking_handheld_kanban_views.xml` |
| Wizard interno GS1 | `views/internal_lot_transfer_wizard_views.xml` |
| Historial escaneos | `views/internal_lot_scan_log_views.xml` |
| Tipo de operación (GS1 Interno) | `views/stock_picking_type_views.xml` |
| Usuarios (permisos) | `views/res_users_views.xml` |
| Menú raíz «Logística» | `views/menu.xml` |

Rutas URL (`path`): `logistics`, `logistics-despachos`, `logistics-internos`, `logistics-fisico`.

---

## Reglas de negocio

- **Acceso app:** grupo `group_kc_logistics_handheld`; botones visibles según booleanos en `res.users`.
- **Despachos kanban:** solo `outgoing`, estados `waiting`/`confirmed`/`assigned`, tipo con `kc_enable_gs1_dispatch_wizard` (`kc_plasticasa`).
- **Internos — QR GS1:** bloques `240` (producto), `10` (lote), `30` (cantidad); soporta separadores GS1 y formato concatenado.
- **Internos — producto:** búsqueda por barcode, default_code, `kc_gs1_code` (si existe en producto/plantilla); normalización sin espacios/mayúsculas.
- **Internos — disponibilidad:** validación en ubicación origen **exacta** (no sububicaciones); compara `quantity - reserved_quantity` en quants.
- **Internos — duplicados:** un lote y un `barcode_raw` por sesión; eliminar línea cancela log en estado `scanned`.
- **Internos — validación:** agrupa por producto en moves; crea move_lines por lote; marca `picked`; auto-procesa wizards `stock.immediate.transfer` y `stock.backorder.confirmation`.
- **Internos — baja calidad:** si `kc_mark_low_quality` en tipo de operación, escribe `low_quality=True` en lotes (campo de `kc_plasticasa`) antes de validar.
- **Navegación Odoo 18:** acciones con `target=main` para reemplazar pila de migas (sin launcher técnico encima).
- **Post-init:** activa `kc_enable_internal_lot_scanner` en tipos internos existentes; migra metadatos de `kc_internal_lot_scanner`.

---

## Integraciones / efectos colaterales

| Integración | Efecto |
|-------------|--------|
| `kc_plasticasa` | Despachos GS1, físico previo, campo `low_quality` en lotes, `kc_enable_gs1_dispatch_wizard` |
| `stock` estándar | Pickings, moves, move_lines, quants, validación estándar |
| `barcodes` | Base para widgets de escaneo |
| Secuencias | `GS1INT/` sesiones, `GS1LOG/` logs |
| JS backend | Widget `kc_internal_gs1_barcode_scan`, vista `kc_internal_gs1_scan_wizard` |

Al validar internos se generan movimientos de stock estándar; impacta inventario, trazabilidad por lote y reportes de stock.

---

## Riesgos conocidos

- **Ubicación exacta:** lote en sububicación o ubicación hermana no cuenta como disponible en origen configurado.
- **Multi-compañía:** dominios de tipo de operación y lotes filtran por `company_id`; verificar configuración por compañía.
- **Permisos:** usuario con grupo handheld pero sin booleanos ve pantalla vacía (mensaje de advertencia).
- **Dependencia `kc_plasticasa`:** sin él, despachos y físico no funcionan; internos sí (salvo `low_quality`).
- **Migración:** instalaciones con `kc_internal_lot_scanner` deben actualizar a este módulo; hook marca módulo antiguo `to remove`.
- **Performance:** revalidación de todas las líneas antes de validar transferencia (N consultas a quants).

---

## Pendientes

| Prioridad | Item |
|-----------|------|
| Media | Botón «Menú principal» en wizard internos (hoy solo en kanban despachos). |
| Baja | Vista kanban/list para sesiones internas históricas (hoy solo log). |
| Baja | Tests automatizados de parseo GS1 y disponibilidad. |

---

## Estado actual

**Listo** — v18.0.1.2.1 en producción; funcionalidad interna GS1 completa; launcher y permisos operativos; migración desde `kc_internal_lot_scanner` implementada.
