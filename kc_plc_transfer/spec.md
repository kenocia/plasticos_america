# SPEC — Integración PLC (Siemens LOGO! 8 / Gateway) ↔ Odoo 18
## Proyecto: kc_plc_transfer

### 1) Objetivo
Automatizar traslados internos de inventario basados en lectura de QR de **lotes**:
- Flujo Receiving: **WIP → Receiving PT**
- Flujo Reproceso: **PT (ubicación actual cualquiera) → WIP**
Reglas clave:
- QR representa **LOTE**
- **NO** movimientos parciales: se mueve **la existencia total del lote**
- Traslado queda **DONE automático** (validación automática)
- Registrar bitácora de eventos con estados y errores (`plc.event.log`)
- Idempotencia obligatoria por `event_uuid`

---

## 2) Arquitectura
Scanner → LOGO!8 → Gateway/Edge (Node-RED/Python) → API Odoo

Odoo expone endpoint REST:
POST /api/scan/transfer

---

## 3) Modelos

### 3.1 Modelo: plc.station
Propósito: parametrizar estaciones de banda/escaneo.

**Campos**
- name (Char, required)
- station_code (Char, required, unique por company)
- mode (Selection required): receiving / reprocess
- company_id (Many2one res.company, required)
- picking_type_id (Many2one stock.picking.type, required) — tipo Internal Transfers
- location_src_id (Many2one stock.location, required si receiving)
- location_dest_id (Many2one stock.location, required)
- auto_validate (Boolean, required) — True en este alcance
- require_sensor_confirm (Boolean, required) — False en este alcance (feature flag)
- allowed_source_parent_id (Many2one stock.location, optional) — para reproceso: limitar origen al árbol PT
- active (Boolean, required)

**Constraints**
- station_code único por company
- Si mode=receiving => location_src_id obligatorio
- Si mode=reprocess => location_src_id se ignora
- location_dest_id debe existir siempre

---

### 3.2 Modelo: plc.event.log
Propósito: trazabilidad industrial, auditoría, fallos y control de duplicados.

**Campos**
- event_uuid (Char, required, unique por company)
- station_id (Many2one plc.station, required)
- timestamp (Datetime, required) — default now server
- qr_raw (Char, required)
- lot_id (Many2one stock.lot)
- product_id (Many2one product.product)
- state (Selection, required): pending, success, rejected, error, duplicate, timeout
- reason_code (Selection)
- reason_message (Text)
- from_location_id (Many2one stock.location)
- to_location_id (Many2one stock.location)
- qty (Float)
- picking_id (Many2one stock.picking)
- attempts (Integer, required, default 1)
- processed_at (Datetime)
- payload_json (Text)
- response_json (Text)

**reason_code (catálogo)**
- LOT_NOT_FOUND
- INVALID_QR_FORMAT
- NO_STOCK
- WRONG_LOCATION
- LOT_SPLIT_MULTIPLE_LOCATIONS
- SOURCE_NOT_ALLOWED
- DUPLICATE
- ODOO_EXCEPTION
- SENSOR_TIMEOUT

**Índices**
- Unique: (company_id, event_uuid)
- Index: (station_id, timestamp), (lot_id, state)

---

## 4) Endpoint REST

### 4.1 URL
POST /api/scan/transfer

### 4.2 Auth
Header obligatorio:
- X-API-Key: <api_key>

La API Key se valida contra configuración de la estación (o repositorio de keys asociado).
Sin clave válida: 401/403.

### 4.3 Payload (JSON)
{
  "event_uuid": "<uuid>",
  "station_code": "RCV-01",
  "qr": "LOT:ABC123"
}

Campos obligatorios: event_uuid, station_code, qr

### 4.4 Response (JSON)
- status: success | rejected | duplicate | error
- code: reason_code (si aplica)
- message
- picking_id (si aplica)
- lot, product, qty, from_location, to_location (si aplica)

HTTP:
- 200: respuesta válida de negocio (success/duplicate/rejected)
- 400: payload inválido
- 401/403: auth
- 500: excepción no controlada

---

## 5) Reglas de negocio (VALIDACIONES)

### 5.1 Parse QR
Formato permitido: "LOT:<lot_name>"
Si no cumple => rejected INVALID_QR_FORMAT

### 5.2 Resolver lote
Buscar stock.lot por name=lot_name (y company si aplica).
Si no existe => rejected LOT_NOT_FOUND

### 5.3 Determinar stock del lote (NO parcial)
Buscar stock.quant del lote con quantity > 0.
- Si sum(quantity)=0 => rejected NO_STOCK
- Si quantity>0 en más de una ubicación => rejected LOT_SPLIT_MULTIPLE_LOCATIONS

NOTA: Esta regla es obligatoria para cumplir "no parcial".

### 5.4 Flujo receiving (station.mode=receiving)
- from_location debe ser EXACTAMENTE station.location_src_id (WIP)
- si el quant está en otra ubicación => rejected WRONG_LOCATION
- to_location = station.location_dest_id (Receiving PT)

### 5.5 Flujo reprocess (station.mode=reprocess)
- from_location = ubicación real del quant
- si station.allowed_source_parent_id existe:
    - validar from_location es hija del árbol allowed_source_parent_id
    - si no => rejected SOURCE_NOT_ALLOWED
- to_location = station.location_dest_id (WIP)

### 5.6 Idempotencia
Si existe plc.event.log con mismo event_uuid:
- si state=success o duplicate => devolver status duplicate + picking_id
- no crear nuevos movimientos

---

## 6) Creación del movimiento (DONE automático)

Para ambos flujos:
- Crear stock.picking (Internal Transfer) con picking_type_id de estación
- Crear stock.move.line con:
    - product_id
    - lot_id
    - location_id (from_location)
    - location_dest_id (to_location)
    - qty_done = total del lote (sum quants)
- Confirm/Assign/Validate => DONE automático

Actualizar plc.event.log:
- success + qty/from/to/picking_id/processed_at
o rejected/error con reason_code/mensaje.

---

## 7) Operación / feedback PLC (fuera de Odoo)
Gateway decide señales OK/FAIL hacia LOGO!8.
Odoo solo responde JSON.

Feature futura: doble confirmación por sensor (require_sensor_confirm)
- No implementada en este alcance.
