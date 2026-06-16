# Estado MRP — kc_mrp_wizard

## Scope del módulo

**Cubre:**
- Extensión de `mrp.workcenter` (require_pin, enforce_shift). Empleados permitidos y ubicación de consumo usan datos estándar (mrp_workorder y MO).
- Determinación de MO/WO activa por centro (progress → ready; prioridad, fecha planificada).
- Cantidad por lote: según lista de materiales (BOM) de la MO, campo `product_qty` (cantidad más pequeña a producir).
- Acción "Crear lote": producción parcial con lote PT, sin cerrar MO; lock anti doble click.
- Modelo `mrp.batch_ticket` (historial, auditoría, impresión viñeta).
- Wizard `mrp.tablet.wizard` (pantallas PIN y producción; paro/falla).

**No cubre:**
- Replanificación avanzada, WO por lote, cambios profundos al consumo/contabilidad estándar.

---

## Modelos tocados

| Modelo | Tipo | Uso |
|--------|------|-----|
| `mrp.workcenter` | extensión | require_pin, enforce_shift, action_open_tablet_wizard. Empleados: `employee_ids` (mrp_workorder). |
| `mrp.production` | uso | MO activa, location_src_id, bom_id.product_qty, move_raw_ids, registro parcial |
| `mrp.workorder` | uso | WO activa, lock, registro producción |
| `mrp.batch_ticket` | nuevo | historial, auditoría, reporte viñeta |
| `mrp.tablet.wizard` | wizard | PIN, producción, Crear lote, paro/falla |

---

## Campos añadidos

- **mrp.workcenter:** `require_pin` (Boolean), `enforce_shift` (Boolean). No se añaden empleados ni ubicación: se usan `employee_ids` (mrp_workorder) y `location_src_id` de la MO. Cantidad por lote: `production.bom_id.product_qty`.
- **mrp.batch_ticket:** name (secuencia), production_id, workorder_id, workcenter_id, product_id, lot_id, qty, employee_id, user_id, printed_at, print_count, company_id.

---

## Vistas afectadas

- Formulario `mrp.workcenter`: pestaña Tablet/Operaciones (require_pin, enforce_shift); botón Asistente tablet.
- Wizard tablet (PIN, Producción, Crear lote).
- Historial/reimpresión basado en `mrp.batch_ticket`.
- Reporte QWeb viñeta.

---

## Reglas de negocio

- MO activa: WO en progress, luego ready; orden prioridad desc, fecha planificada asc.
- Empleados permitidos: `workcenter.employee_ids` (mrp_workorder); si vacío, todos pueden operar.
- Cantidad por lote: `production.bom_id.product_qty` (convertida a UdM de la MO); si no hay BOM, `production.product_qty`.
- Crear lote = producción parcial; si restante < cantidad lote, se produce el restante.
- Lock transaccional sobre WO para evitar doble lote.
- Ubicación de consumo: la configurada en la MO (`location_src_id`).

---

## Integraciones / efectos colaterales

- MRP estándar para registro de producción y consumo (backflush).
- Reportes de fabricación y trazabilidad.

---

## Riesgos conocidos

- Lock breve solo durante creación de lote; evitar consultas pesadas en pantalla.

---

## Pendientes

- Nombres exactos de métodos de registro parcial en Odoo 18.

---

## Estado actual

**En progreso** — Núcleo implementado: PIN, employee_ids, BOM product_qty, Crear lote, batch_ticket, viñeta. Pendiente: turnos/asistencia, paros/fallas, reserva FIFO explícita.
