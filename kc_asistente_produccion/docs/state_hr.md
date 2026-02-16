# Estado HR — kc_asistente_produccion

## Scope del módulo

**Cubre:**
- Extensión de `hr.employee`: PIN para acceso al wizard (campo `pin_hash`, método `check_pin`).
- Validación de empleados permitidos por workcenter (`employee_ids` de mrp_workorder).
- Validación de turno (fase 1): `resource.calendar` del empleado o compañía; opcional Planning en fase 2.
- Si existe `hr_attendance`: validación de asistencia abierta (check-in) para permitir "Crear lote".

**No cubre:**
- Cambios a nómina, contratos, planificación avanzada de turnos (fase 1).

---

## Modelos tocados

| Modelo | Tipo | Uso |
|--------|------|-----|
| `hr.employee` | extensión | pin_hash, check_pin(pin) |
| `resource.calendar` | uso | is_employee_in_working_time(employee, dt) |
| `hr.attendance` | uso (si instalado) | employee_has_open_attendance(employee) |

---

## Campos añadidos

- **hr.employee:** `pin_hash` (Char/Password). Método `check_pin(pin)` (comparación segura; no guardar PIN en logs).

---

## Vistas afectadas

- Configuración/utilidad para asignar PIN (setear hash) al empleado. No obligatorio modificar vista formulario estándar de empleado si se usa acción separada.

---

## Reglas de negocio

- Si el centro tiene `workcenter.employee_ids` (mrp_workorder) con valores, solo esos empleados pueden operar; si está vacío, todos pueden.
- Con `enforce_shift=True`: turno vigente (calendario) + asistencia abierta si hr_attendance.
- Mensajes de bloqueo: "PIN inválido", "Empleado no autorizado para este centro", "No tiene turno activo", "Debe registrar entrada (asistencia) antes de producir."

---

## Integraciones / efectos colaterales

- Sin impacto en nómina ni en otros flujos HR; solo lectura de calendario y asistencia para validación.

---

## Riesgos conocidos

- Permisos: no exponer PIN en logs ni en respuestas API.

---

## Pendientes

- Decidir hash (bcrypt/argon2 según stack Odoo 18). MVP con pin en claro solo temporal.

---

## Estado actual

**En progreso** — PIN (pin_hash, check_pin, wizard establecer PIN) implementado. Validación por employee_ids del workcenter (mrp_workorder). Pendiente: validación turno/asistencia (enforce_shift).
