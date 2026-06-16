# Plan de implementación — Wizard Tablet MRP (Producción por Fardos)

Basado en el análisis funcional y técnico. Orden ejecutable por sprints/PRs.

---

## Objetivo

Wizard por centro de trabajo: PIN → validación turno/asistencia → MO activa → **Crear lote (X uds)** → producción parcial + lote + viñeta. Sin cerrar MO hasta el final. Consumo desde ubicación local con FIFO para resina loteada.

---

## Fase 0 — Preparación

- [ ] Crear módulo Odoo `kc_mrp_wizard` (o nombre acordado) en addons.
- [x] Dependencias: `mrp_workorder`, `hr`, `stock` (empleados permitidos vía `employee_ids` del workcenter).
- [ ] Estructura base: `models/`, `wizard/`, `views/`, `security/`, `report/`, `static/`.

---

## Sprint 1 — Control de acceso y pantalla PIN

**Entregables**

1. **Extensión `mrp.workcenter`**
   - Campos: `require_pin`, `enforce_shift`. Empleados permitidos: campo estándar `employee_ids` (mrp_workorder). Ubicación de consumo: en la MO (`location_src_id`). Cantidad por lote: de la BOM de la MO (`bom_id.product_qty`).
   - Vista: pestaña "Tablet / Operaciones" con require_pin y enforce_shift; botón Asistente tablet.

2. **Extensión `hr.employee`**
   - `pin_hash` (o `pin` MVP) y método `check_pin(pin)` seguro (sin guardar PIN en logs).
   - Utilidad para setear hash (acción/configuración).

3. **Resolución de workcenter**
   - Opción A: `res.users.workcenter_id` (tablet = usuario fijo).
   - Opción B: `tablet_device_code` en workcenter + URL con código.

4. **Wizard `mrp.tablet.wizard` (esqueleto)**
   - Pantalla A: PIN (teclado numérico) + botón "Entrar".
   - Llamada a `validate_pin(workcenter_id, pin)` → empleado o error.
   - Validaciones: empleado activo, `workcenter.employee_ids` (mrp_workorder), (opcional) turno.
   - Pantalla B: header (centro + empleado), card MO activa (sin acción de producir aún).

**Criterio de cierre:** operador entra con PIN y ve MO activa; no autorizado no entra.

---

## Sprint 2 — MO/WO activa y Crear lote (núcleo)

**Entregables**

1. **Determinar MO/WO activa**
   - `get_active_workorder(workcenter)` → prioridad: state `progress`, luego `ready`; orden: prioridad desc, fecha planificada asc, id asc.
   - `get_active_mo(workcenter)` desde WO.

2. **Modelo `mrp.batch_ticket`**
   - name (secuencia), production_id, workorder_id, workcenter_id, product_id, lot_id, qty, employee_id, user_id, printed_at, print_count, company_id.
   - Índices: (production_id, create_date), (workcenter_id, create_date), (lot_id).
   - ACL: operador create/read; supervisores administración.

3. **`action_create_batch_lot` (blueprint)**
   - Revalidar empleado (PIN/allowed/planning/attendance).
   - Resolver WO/MO activa. Ubicación de consumo = `mo.location_src_id` (configurada en la MO).
   - Cantidad por lote = `mo.bom_id.product_qty` (cantidad más pequeña a producir). `qty_to_produce = min(batch_qty, restante)`; si restante < X, se produce el restante.
   - Lock (FOR UPDATE) sobre WO/MO.
   - Reserva componentes: `move_raw_ids` desde `mo.location_src_id`, `_action_assign` (FIFO).
   - Fallback: si componente con tracking=lote queda sin lot en move_line, asignar lotes FIFO desde ubicación local.
   - Crear `stock.lot` para PT (secuencia + producto).
   - Registrar producción parcial con lote (APIs estándar MRP/WO, sin tocar quants a mano).
   - Crear `mrp.batch_ticket`; disparar impresión; retornar payload para UI.

4. **Pantalla B funcional**
   - Botón "Crear lote (X uds)" / "Crear lote (Restante: Y)".
   - Anti doble click (lock + deshabilitar botón hasta respuesta).

**Criterio de cierre:** un click crea un lote, incrementa producido, no cierra MO, imprime etiqueta; doble click no duplica.

---

## Sprint 3 — Turnos, asistencia y paros/fallas

**Entregables**

1. **Validación de turno (fase 1)**
   - `is_employee_in_working_time(employee, dt)`: resource.calendar del empleado (o compañía).
   - Si `hr_attendance`: `employee_has_open_attendance(employee)`.
   - Regla: permitir operar solo si turno activo (Planning si aplica) + checked-in.

2. **Integración en wizard**
   - Antes de "Crear lote": validar turno + asistencia si `enforce_shift=True`.
   - Mensajes: "No tiene turno activo en este horario." / "Debe registrar entrada (asistencia) antes de producir."

3. **Paro / Falla (mínimo)**
   - Modelo simple: enlace workcenter + WO/MO; tipo (paro/falla), catálogo; iniciar/finalizar (paro); observación (falla).
   - Modal en wizard: Paro | Falla con campos mínimos.
   - Fase 2: integrar a mantenimiento/calidad si el cliente lo usa.

**Criterio de cierre:** con enforce_shift=True no se puede producir fuera de turno ni sin check-in; paro/falla se registran.

---

## Sprint 4 — Consumo local y FIFO (resina loteada)

**Entregables**

1. **Ubicación de consumo**
   - La ubicación de consumo es la de la orden de fabricación (`mo.location_src_id`), configurada en la MO (no en el centro de trabajo).

2. **Reserva FIFO**
   - Antes de registrar producción: `move_raw_ids` con origen en ubicación local; `_action_assign`.
   - Validar faltantes; si hay, UserError con detalle (evitar backflush incompleto).

3. **Fallback lote en componentes rastreables**
   - Si tras reserva queda consumo con tracking=lote sin `lot_id` en move_line: asignar lotes desde ubicación local por FIFO (quants por in_date); crear/actualizar move_line con lot_id.
   - Si no hay stock suficiente por lote: UserError "Resina insuficiente por lote en ubicación local (FIFO)."

4. **Scrap por MO (opcional mismo sprint)**
   - Acción `action_register_scrap(mo_id, product_id, qty, reason)`; no atada al lote de PT.

**Criterio de cierre:** crear fardo consume desde la ubicación de la MO; resina con lote asignada por FIFO sin digitación cuando aplique.

---

## Sprint 5 — Impresión e historial

**Entregables**

1. **Reporte viñeta**
   - QWeb (o ZPL si térmicas); documento principal `mrp.batch_ticket`.
   - Configuración por producto o por workcenter (tablet_printer_id + report_id).

2. **Reimpresión**
   - Historial últimos N lotes (ej. 20) en wizard; botón "Reimprimir".
   - Al reimprimir: incrementar `print_count`, actualizar `printed_at`.

**Criterio de cierre:** etiqueta al crear; reimpresión actualiza contador y fecha.

---

## Sprint 6 — Tests y ajustes

**Entregables**

1. **Tests automatizados**
   - PIN inválido / empleado no autorizado.
   - Bloqueo fuera de turno (enforce_shift).
   - Creación de lote único por click; incremento de qty producido sin cerrar MO.
   - Prevención duplicidad (doble ejecución con lock).
   - Trazabilidad: lote ↔ MO/WO/workcenter/empleado/fecha/cantidad.

2. **QA manual**
   - Según `docs/test_matrix.md`.

**Criterio de cierre:** tests pasan; matriz de pruebas ejecutada.

---

## Orden sugerido de PRs

| PR | Contenido |
|----|-----------|
| 1 | Campos y vistas workcenter (require_pin, enforce_shift) + employee PIN; empleados = employee_ids (mrp_workorder); cantidad por lote = BOM product_qty |
| 2 | Validación PIN + planning + attendance + sesión wizard |
| 3 | MO/WO activa + lock + validación ubicación |
| 4 | Reserva FIFO + fallback lot resina |
| 5 | Producción parcial + mrp.batch_ticket + impresión |
| 6 | Turnos + paros/fallas mínimos |
| 7 | Tests y documentación |

---

## Riesgos y mitigación

- **Performance:** lock corto solo sobre WO/MO durante creación de lote; evitar consultas pesadas en pantalla.
- **Multi-company:** todos los modelos con `company_id`; dominios y reglas por compañía.
- **Permisos:** ACL claros (operador vs supervisor); no exponer PIN en logs ni en front.

---

## Pendientes (TODOs)

1. Definir nombre final del módulo y ruta (addons_custom).
2. Confirmar si Planning es fuente de verdad de turnos (fase 1 vs fase 2).
3. Decidir hash para PIN (bcrypt/argon2 según stack Odoo 18).
4. ZPL vs QWeb según impresora (térmica vs láser).
