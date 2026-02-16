# Estado Stock — kc_asistente_produccion

## Scope del módulo

**Cubre:**
- Creación de `stock.lot` para producto terminado por cada fardo.
- Ubicación de consumo: la definida en la orden de fabricación (`mrp.production.location_src_id`), no en el centro de trabajo.
- Reserva y consumo de componentes desde esa ubicación (FIFO/PEPS cuando aplique); movimientos estándar vía MRP (backflush).
- No creación directa de quants ni move_line fuera del flujo estándar.

**No cubre:**
- Cambios al flujo general de inventario ni a valoración.
- Reabastecimiento de ubicaciones locales (se asume ya configurado).
- Trazabilidad inversa más allá de lote → MO/WO/workcenter/empleado (eso vive en mrp.batch_ticket).

---

## Modelos tocados

| Modelo | Uso |
|--------|-----|
| `stock.lot` | Creación por fardo (nombre por secuencia, producto PT). |
| `stock.location` | Ubicación de consumo = `mrp.production.location_src_id` (configurada en la MO). |
| `stock.move` | move_raw_ids de MO: origen = location_src_id de la MO, reserva y consumo. |
| `stock.move.line` | Reserva/asignación; fallback asignación lot_id para productos con tracking=lote. |
| `stock.quant` | Consulta FIFO (in_date) para fallback de asignación de lote; no escritura directa arbitraria. |

---

## Campos añadidos

- Ninguno en modelos stock puros. La ubicación de consumo es la de la orden de fabricación (`mrp.production.location_src_id`).

---

## Vistas afectadas

- Ninguna vista de stock alterada directamente; el wizard y el flujo MRP consumen las vistas estándar de movimientos/lotes donde aplique.

---

## Reglas de negocio

- Consumo de componentes desde `production.location_src_id` (ubicación configurada en la MO).
- Esa ubicación debe tener estrategia FIFO para asignación automática de lotes.
- Antes de registrar producción parcial: reserva (`_action_assign`) desde esa ubicación; si componente con tracking=lote queda sin lot, fallback asignación FIFO desde quants en ubicación local.
- No crear/alterar quants a mano; seguir APIs estándar de MRP/stock para consumo.

---

## Integraciones / efectos colaterales

- Movimientos de consumo y de producto terminado quedan en el mismo flujo que el MRP estándar (trazabilidad, valoración, reportes de inventario).
- Reportes de inventario por lote incluirán los lotes creados por el wizard.

---

## Riesgos conocidos

- Si la ubicación local no tiene FIFO o no tiene stock suficiente, el wizard debe bloquear con mensaje claro (ej. "Resina insuficiente en ubicación local").
- Redondeos UoM en consumo escalado; con lote base fijo (ej. 44) se minimiza.

---

## Pendientes

- Validar en Odoo 18 nombres exactos de métodos de reserva (`_action_assign` / `action_assign`) y de registro de producción parcial.

---

## Estado actual

**En progreso** — Creación de lote PT y consumo vía flujo estándar MRP; ubicación de consumo = MO.location_src_id. Pendiente: reserva FIFO explícita y fallback lote en componentes rastreables si se requiere.
