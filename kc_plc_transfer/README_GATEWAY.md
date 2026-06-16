# README — Gateway Raspberry Pi (LOGO! 8 ↔ Odoo 18)
## Objetivo
El gateway (Raspberry Pi) integra señales del PLC Siemens LOGO! 8 con Odoo 18 para crear traslados internos por lectura de QR de lote, vía API.

---

## 1) Responsabilidades por componente

### LOGO! 8 (PLC / OT)
- Control de banda: start/stop, sensores, tiempos
- Handshake con gateway por bits/registros (Modbus TCP recomendado):
  - indicar “evento listo” (QR leído)
  - indicar “ocupado” (gateway procesando)
  - recibir “OK” o “FAIL”
  - accionar luz verde/roja/buzzer/paro

### Raspberry Pi (Gateway / IT)
- Leer estado/eventos del PLC (Modbus TCP: coils/registers)
- Obtener QR leído (según arquitectura)
- Generar event_uuid (UUID v4)
- Consumir API Odoo:
  - POST /api/scan/transfer
  - Header X-API-Key
- Manejar respuestas y reenviar resultado al PLC
- Persistir cola offline y reintentos

### Odoo 18 (ERP)
- Validar QR/lote/stock/ubicación
- Crear picking interno + move line por lote
- Validar DONE automático
- Registrar plc.event.log
- Responder JSON con status y reason_code

---

## 2) Dos opciones de entrada del QR (seleccionar según hardware)

### Opción A — Scanner hacia Raspberry (IP/WiFi/Ethernet)
- El scanner envía el texto del QR directo al gateway (HTTP/TCP/serial USB).
- LOGO!8 solo recibe resultado (OK/FAIL) por Modbus.
**Ventaja:** integración más simple, el PLC no necesita “transportar texto”.

### Opción B — Scanner hacia LOGO (cableado al PLC)
- El PLC recibe QR y lo expone al gateway por registros Modbus (string en registros).
- Gateway lee registros, arma payload y llama a Odoo.
**Ventaja:** el PLC tiene control total del evento de lectura.
**Riesgo:** transportar texto vía registros PLC puede ser más engorroso.

---

## 3) Handshake recomendado PLC ↔ Gateway (Modbus TCP)

### Coils (bits)
- C0: EVENT_READY (PLC=1 cuando hay QR listo)
- C1: GATEWAY_BUSY (Gateway=1 mientras procesa)
- C2: RESULT_OK (Gateway=1 si Odoo success)
- C3: RESULT_FAIL (Gateway=1 si rejected/error)
- C4: ACK (PLC=1 para confirmar que vio el resultado; opcional)
- C5: RESET (PLC o Gateway limpia estados; opcional)

### Holding Registers (si se usa Opción B para enviar QR)
- HR100..HR140: QR_TEXT (ASCII/UTF-8 segmentado)
- HR150: QR_LEN (longitud)
- HR151: RESULT_CODE (número mapeado desde reason_code)

---

## 4) Mapeo reason_code Odoo → RESULT_CODE PLC (ejemplo)
1  LOT_NOT_FOUND
2  INVALID_QR_FORMAT
3  NO_STOCK
4  WRONG_LOCATION
5  LOT_SPLIT_MULTIPLE_LOCATIONS
6  SOURCE_NOT_ALLOWED
7  DUPLICATE
8  ODOO_EXCEPTION

---

## 5) Flujo operativo (Gateway)

1. Esperar EVENT_READY=1
2. Set GATEWAY_BUSY=1
3. Leer QR (de scanner directo o desde registros PLC)
4. Generar event_uuid
5. POST a Odoo /api/scan/transfer
6. Si status=success or duplicate:
   - RESULT_OK=1, RESULT_FAIL=0
7. Si status=rejected/error:
   - RESULT_OK=0, RESULT_FAIL=1
   - escribir RESULT_CODE si aplica
8. Esperar ACK (opcional) o esperar T segundos
9. Limpiar RESULT_OK/FAIL, BUSY
10. Si Odoo no responde:
    - guardar evento en cola offline
    - marcar FAIL con ODOO_EXCEPTION (o un código dedicado)
    - reintentar según política

---

## 6) Reintentos / Cola offline
- Persistencia local en Raspberry:
  - SQLite o archivo JSONL
- Política:
  - reintento cada 5s x 3
  - luego cada 30s por 10 min
  - luego cada 5 min hasta éxito
- Importante:
  - Idempotencia por event_uuid evita duplicados en Odoo

---

## 7) Consideración futura: doble confirmación por sensor
Si se activa `require_sensor_confirm` en estación:
- Escaneo crea evento pendiente
- Sensor fin de banda dispara confirmación
Esto requiere endpoint adicional o parámetro confirm=true.
No está incluido en alcance actual.
