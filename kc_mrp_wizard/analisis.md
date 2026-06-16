## Especificación Funcional y Técnica

### Wizard Tablet MRP — Producción por Lotes (Fardos) con PIN + Centro de Trabajo + Validación de Turno

---

# 0) Resumen ejecutivo

Se implementará un **Wizard Tablet** por **Centro de Trabajo (máquina)** que permite a un operador:

* Identificarse mediante **PIN**.
* Validar que el empleado esté **permitido** para ese centro.
* Validar que el empleado esté **en turno** (horario asignado) antes de operar.
* Seleccionar automáticamente la **Orden de Producción (MO)** activa por planificación/estado.
* Con un solo botón: **Crear Lote (fardo)** de cantidad parametrizada **X**, **registrar producción parcial** (sin cerrar la MO) e **imprimir viñeta**.
* Registrar **paros** y **fallas** desde el mismo flujo.

> Principio clave: **cada fardo = producción parcial + lote**, la MO solo se cierra al final.
> Esto evita la complejidad de backorders/split por cada parcial.

---

# 1) Alcance

## Incluye

* Configuración de **empleados permitidos** por `mrp.workcenter`.
* Autenticación **por PIN** (HR Employee).
* Validación de **turno/horario** (versión mínima + extensible).
* Determinación de **MO/WO activa** por workcenter.
* Acción **Crear lote**:

  * Crear `stock.lot`
  * Registrar producción parcial asociada al lote
  * Registrar evento en historial
  * Imprimir etiqueta
* Historial de lotes creados + reimpresión.
* Registro básico de **paro/falla** anclado a workcenter + WO/MO.

## No incluye (fase 1)

* Offline.
* Replanificación avanzada.
* “WO por lote”.
* Customizaciones profundas al estándar de consumo/contabilidad.

---

# 2) Objetivos medibles

* **Cero digitación** en producción por fardo (salvo PIN).
* **Tiempo por fardo**: creación + registro + impresión en < 2 segundos en LAN típica.
* **0 duplicados** por doble-click (con lock).
* **Trazabilidad** completa por lote: MO/WO/Workcenter/Empleado/Fecha/Cantidad.

---

# 3) Reglas de negocio

## RB-01: Empleados permitidos

Un empleado puede operar un centro si:

* Está activo.
* Está incluido en el Many2many **Empleados permitidos** del workcenter.

## RB-02: Validación por PIN

El acceso al wizard y/o la acción “Crear lote” requiere PIN (configurable).

* El PIN se valida contra `hr.employee`.
* El PIN **no debe almacenarse** en logs ni en texto plano.

## RB-03: Validación de turno/horario (fase 1)

Si está activada, se permite operar solo si **ahora** cae dentro del turno/horario válido del empleado.

**Implementación fase 1 (mínima, estable):**

* Usar **calendario laboral** (`resource.calendar`) del empleado (o fallback al de compañía).
* Opcional (si existe hr_attendance): el empleado debe estar **checked in**.

> Planning (turnos dinámicos) se deja como fase 2, pero el diseño queda preparado.

## RB-04: MO activa por centro de trabajo

Se determina MO activa a partir de WO en el workcenter:

1. Si existe WO en estado **progress** para ese workcenter ⇒ esa es la activa.
2. Si no, buscar WO en estado **ready** (o “queued/ready” según configuración) ordenando por:

   * prioridad desc, luego
   * fecha planificada asc (o secuencia del planning), luego
   * id asc como desempate.

Si hay múltiples candidatas con el mismo score ⇒ se muestra selector en tablet.

## RB-05: Producción por lote (sin cerrar MO)

El botón **Crear lote** solo registra **producción parcial** del fardo y mantiene MO/WO en ejecución.

* Si `restante >= X` ⇒ produce X
* Si `restante < X` ⇒ propone producir `restante` (confirmación simple, sin digitación)

---

# 4) Diseño funcional (UX tablet)

## Pantalla A — Identificación (PIN)

**Campos:**

* PIN (numérico, teclado grande)
  **Botón:**
* “Entrar”

**Validaciones:**

* PIN válido ⇒ empleado encontrado
* empleado permitido en workcenter
* turno válido (si aplica)

**Salida:**

* “Sesión de operador” en wizard por tiempo corto (ej. 10 min) o hasta salir.

---

## Pantalla B — Producción

**Header:**

* Centro de trabajo (máquina)
* Empleado autenticado

**Card MO activa:**

* MO referencia
* Producto terminado
* Planificado / Producido / Restante
* Operación/WO actual

**Botón principal (grande):**

* “Crear lote (X uds)”
* Si restante < X: “Crear lote (Restante: Y)”

**Acciones secundarias:**

* Paro
* Falla
* Historial (últimos 20 lotes) + reimprimir

---

## Pantalla C — Paro / Falla (modal)

**Paro:**

* Tipo de paro (catálogo)
* Iniciar / Finalizar
  **Falla:**
* Tipo de falla (catálogo)
* Observación corta (opcional)
* Registrar

> En fase 1: modelo simple propio, con enlace a workcenter+WO/MO.
> Fase 2: integrar a mantenimiento/calidad si el cliente lo usa.

---

# 5) Datos y modelos (técnico)

## 5.1 Extensión de `mrp.workcenter`

Campos nuevos:

* `allowed_employee_ids = fields.Many2many('hr.employee', string="Empleados permitidos")`
* `require_pin = fields.Boolean(default=True)`
* `enforce_shift = fields.Boolean(default=True)`
* `tablet_batch_qty_source = fields.Selection([...], default='product')` (opcional)
* `tablet_default_batch_qty = fields.Float()` (opcional)
* `tablet_printer_id` (opcional, si manejan impresora por centro)

---

## 5.2 Extensión de `hr.employee`

Campos:

* `user_id` (si no existe en su DB, agregar)
* `pin_hash` (recomendado) o `pin` (mínimo viable)

**Recomendación de seguridad:**

* `pin_hash` usando un hash fuerte (bcrypt/argon2 si viable en stack).
* Comparación segura (constant-time).

---

## 5.3 Nuevo modelo: `mrp.batch_ticket` (historial y auditoría)

Propuesto (recomendado):

* `name` (secuencia)
* `production_id` (mrp.production)
* `workorder_id` (mrp.workorder)
* `workcenter_id` (mrp.workcenter)
* `product_id` (product.product)
* `lot_id` (stock.lot)
* `qty` (float)
* `employee_id` (hr.employee)
* `user_id` (res.users)
* `state` (draft/done/cancel) — opcional
* `printed_at` (datetime)
* `print_count` (int)
* `company_id`

Índices recomendados:

* `(production_id, create_date desc)`
* `(workcenter_id, create_date desc)`
* `(lot_id)`

---

## 5.4 Nuevo wizard: `mrp.tablet.wizard`

Campos típicos:

* `workcenter_id`
* `employee_id` (sesión)
* `production_id`
* `workorder_id`
* `batch_qty` (computed: X)
* `last_ticket_ids` (computed o domain a `mrp.batch_ticket`)

---

# 6) Servicios / Métodos (técnico)

## 6.1 Resolver workcenter

Fuentes (seleccionar una, mínimo fricción):

**Opción 1 (simple):** workcenter fijo por usuario

* campo `res.users.workcenter_id`

**Opción 2 (robusta):** workcenter por dispositivo

* `tablet_device_code` en workcenter
* la tablet accede con una URL que incluye código

---

## 6.2 Validación PIN

**Firma propuesta:**

* `validate_pin(workcenter_id, pin) -> hr.employee`

**Reglas:**

1. buscar empleado por pin (o verificar hash)
2. validar empleado activo
3. validar allowed_employee_ids
4. si enforce_shift:

   * validar horario (fase 1)
   * validar asistencia si aplica

**Errores controlados:**

* `PIN inválido`
* `Empleado no autorizado para este centro`
* `Fuera de turno`

---

## 6.3 Validación turno (Fase 1)

**Método:**

* `is_employee_in_working_time(employee, dt)`:

  * Usa calendario del recurso asociado al employee.
  * Si no hay calendar en employee: fallback company calendar.
  * Retorna bool.

**Opcional si `hr_attendance` instalado:**

* `employee_has_open_attendance(employee)`:

  * bool: tiene “check in” activo.

---

## 6.4 Determinar MO/WO activa

**Firma propuesta:**

* `get_active_wo(workcenter_id) -> mrp.workorder | None`
* `get_active_mo(workcenter_id) -> mrp.production | None`

**Orden de decisión:**

* `state == 'progress'` primero
* luego `state in ('ready', ...)`

---

## 6.5 Acción “Crear lote”

**Firma:**

* `action_create_batch_lot(workcenter_id, production_id, workorder_id, employee_id, qty=None)`

**Pasos:**

1. **Revalidación** (server-side): empleado permitido + turno válido si aplica.
2. Determinar `qty_to_produce`:

   * si `qty` viene informado: validar > 0 y <= restante
   * si no: usar X (batch_qty) y aplicar min(restante)
3. **Lock anti duplicado**:

   * `SELECT ... FOR UPDATE` sobre workorder (o production) antes de producir
4. Crear `stock.lot`:

   * nombre desde secuencia
   * producto = finished product
5. Registrar producción parcial con lote:

   * Usar métodos estándar MRP/WO (sin tocar quants manualmente)
6. Crear `mrp.batch_ticket`
7. Disparar impresión (ir.actions.report)
8. Retornar ticket + datos para actualizar UI

---

# 7) Impresión de viñeta

## Reporte

* QWeb (o ZPL si usan térmicas)
* `mrp.batch_ticket` como documento principal (recomendado), porque ya tiene todo.

## Configuración

* Por producto (label_report_id) o por workcenter (tablet_printer_id + report_id)
* Reimpresión incrementa `print_count` y setea `printed_at`.

---

# 8) Seguridad y control

* Validaciones críticas en **servidor**.
* Logs sin PIN.
* Control de sesiones:

  * El wizard puede mantener `employee_id` “validado” por N minutos.
  * Cada “Crear lote” revalida que employee sigue autorizado.
* ACL:

  * Operador: create/read en `mrp.batch_ticket`; ejecución wizard.
  * Supervisores: administrar allowed_employee_ids y configuración.

---

# 9) Criterios de aceptación (QA)

## CA-01 Autorización

* Un empleado fuera de `allowed_employee_ids` no puede entrar ni producir.
* PIN inválido no revela si el empleado existe.

## CA-02 Turno

* Con `enforce_shift=True`, producir fuera del horario da bloqueo.
* Con `enforce_shift=False`, producir siempre que sea permitido.

## CA-03 Producción parcial

* Crear 10 lotes de X en MO grande incrementa producido sin cerrar MO.
* No se generan órdenes parciales/backorders por cada fardo.

## CA-04 Anti duplicado

* Doble click en “Crear lote” no duplica lotes ni movimientos.

## CA-05 Trazabilidad

* Cada lote queda asociado a MO/WO/workcenter/empleado/fecha/cantidad.

## CA-06 Impresión

* Se imprime etiqueta al crear.
* Reimpresión aumenta contador y fecha.

---

# 10) Plan de implementación (sprints sugeridos)

## Sprint 1 — Control de acceso

* Campos workcenter + vista “Empleados permitidos”
* PIN en employee + validación
* Wizard pantalla PIN + pantalla producción (sin producir aún)

## Sprint 2 — Crear lote + registrar parcial + historial

* Implementar `action_create_batch_lot`
* Modelo `mrp.batch_ticket`
* Historial + reimpresión

## Sprint 3 — Turnos y paros/fallas

* Validación por calendario y/o asistencia
* Paro/falla minimal

---

# 11) Lineamientos para desarrollar con Cursor (operativos, listos para usar)

## 11.1 Reglas de oro

* Cambios mínimos, extensiones limpias (inherit).
* Reusar métodos MRP existentes (no quants manuales).
* PRs chicos: **1 tema por PR**.

## 11.2 Prompts concretos para Cursor (copiar/pegar)

### Prompt 1 — Campos y vista workcenter

“En nuestro módulo, hereda `mrp.workcenter` y agrega `allowed_employee_ids` (M2M a hr.employee), `require_pin` y `enforce_shift`. Luego hereda la vista formulario de workcenter y agrega una sección ‘Operaciones’ con ‘Empleados permitidos’ (many2many_tags).”

### Prompt 2 — PIN seguro

“Agrega en `hr.employee` un campo `pin_hash` y un método `check_pin(pin_plain)` que compare de forma segura. Incluye utilidad para setear el hash. No guardes PIN plano.”

*(Si necesitas MVP rápido: “usa pin en claro” pero recomiendo hash.)*

### Prompt 3 — Validación turno mínimo

“Implementa `is_employee_in_working_time(employee, dt)` usando resource.calendar del recurso asociado al employee. Si no existe, usar calendario de compañía. Devuelve bool.”

### Prompt 4 — Resolver MO/WO activa

“Implementa método `get_active_workorder(workcenter)` que prioriza WOs en progress y luego ready, ordenadas por prioridad y fecha planificada. Devuelve wo y su production.”

### Prompt 5 — Acción crear lote (con lock)

“Implementa `action_create_batch_lot` que: revalida employee contra allowed list y horario (si aplica), bloquea wo con FOR UPDATE, crea stock.lot con secuencia, registra producción parcial con lote usando APIs estándar de MRP/WO, crea mrp.batch_ticket y dispara impresión.”

### Prompt 6 — Tests

“Agrega tests que verifiquen: PIN y autorización, bloqueo fuera de turno, creación de lote único por click, incremento de qty producido sin cerrar MO, y prevención de duplicidad con doble ejecución.”

---

# 12) Decisiones pendientes (registradas, no bloqueantes)

Para cerrar 100% “turno asignado”, define cuál aplica en tu cliente:

1. **Planning** (turnos por schedule) — fase 2
2. **Asistencias** (check in/out)
3. **Calendario laboral** (resource.calendar) ✅ recomendado fase 1

**Fase 1 recomendada:** calendario + (si existe) asistencia.

---

## Siguiente paso inmediato (para que tu equipo codifique sin ambigüedad)

Confírmame solo esto (rápido, sin debate):

* ¿Tienen instalado **hr_attendance** (asistencias) sí/no?
* ¿El “turno asignado” hoy está en **Planning** sí/no?

Con eso te cierro la regla exacta de validación de turno (fase 1) y te dejo el pseudocódigo final para implementar directamente.

Perfecto: **sí tienen `hr_attendance` y sí usan Planning** ✅. Con eso, la validación de turno queda sólida (Planning como fuente de verdad + asistencia como “confirmación” operacional).

Ahora tu duda clave:

# ¿Cómo se manejará el consumo de materiales usando este wizard?

La respuesta corta: **si el wizard registra producción parcial “correctamente” (vía APIs estándar de MRP/WO), Odoo consumirá materiales de forma estándar, proporcional a la cantidad producida**, según la configuración de consumo de la BOM/operación.

Abajo te lo dejo bien aterrizado por escenarios para que el diseño quede sin sorpresas.

---

## 1) Tu BOM está definida por “cantidad por lote” (ej. 44 unidades)

Eso encaja perfecto con lo que quieres.

En Odoo, la **cantidad de la BOM** es el “lote base” (lo que en tu tooltip dice *“cantidad más pequeña que se puede producir”*). Cuando produces una cantidad distinta, Odoo **escala** automáticamente las cantidades de componentes:

* Si BOM = 44 uds de producto terminado
* Componente A = 2 kg para 44 uds
* Si produces 1 lote = 44 ⇒ consume 2 kg
* Si produces 2 lotes = 88 ⇒ consume 4 kg
* Si produces 22 ⇒ consume 1 kg (si la UoM/redondeo lo permite)

✅ En tu caso, como el wizard siempre producirá **exactamente X = 44** (o el “restante”), el consumo queda **muy limpio**.

---

## 2) Qué determina *cuándo* consume Odoo

En fabricación de Odoo, el consumo depende de cómo esté configurado:

### A) **Consumo automático (backflush) al registrar producción**

* Al registrar que produjiste X, Odoo descuenta automáticamente componentes en proporción a X.
* Es el comportamiento ideal para tu wizard: **1 click = produce + consume**.

**Recomendación para tablet:** usar este modo, porque evita digitación.

### B) **Consumo manual**

* El usuario tendría que confirmar/ajustar cantidades consumidas (más lento).
* No lo recomiendo para tu caso, salvo que el proceso requiera registrar mermas/variaciones con precisión.

### C) Consumo “por operación” (si tienen operaciones/workorders)

* Similar a backflush, pero ligado al progreso de operaciones.
* Para tu wizard, igual funciona si tú registras la producción en la WO correcta.

---

## 3) ¿Qué pasa si el producto terminado se produce por lotes (stock.lot)?

Tu wizard hará:

1. crear `lot_id` nuevo para el fardo
2. producir X unidades asignadas a ese `lot_id`
3. Odoo generará el movimiento del terminado con ese lote
4. Odoo consumirá componentes según configuración (backflush/manual)

### ¿Los componentes también requieren lote/serie?

Si algún componente tiene trazabilidad por lote/serie:

* Odoo **puede exigir** que especifiques lotes consumidos.
* Eso puede romper el “1 click sin digitación”.

✅ Para mantenerlo sin digitación, hay 3 opciones:

1. **Componentes sin trazabilidad** (ideal)
2. **Asignación automática por FIFO/FEFO** (si tu operación lo permite y hay reglas claras)
3. En wizard: “si componente rastreable → abrir sub-wizard de escaneo” (solo cuando aplique)

---

## 4) Qué debe hacer el wizard para que el consumo sea “estándar”

El lineamiento técnico es:

### ✅ No manipular `stock.quant` ni crear `stock.move.line` a mano “porque sí”

Lo correcto es invocar el flujo estándar de registro de producción (a nivel MO/WO) y dejar que Odoo:

* cree/actualice movimientos del terminado
* calcule consumo esperado
* ejecute consumo real según configuración (backflush o manual)

**En práctica**, tu wizard debe “hacer lo mismo” que haría un operario al:

* registrar producción en la WO (o en la MO) con lote
* confirmar

Así, el consumo queda idéntico al estándar.

---

## 5) Casos borde a validar (para no tener sustos en planta)

### 5.1 Redondeos / UoM

Si algún componente tiene UoM con redondeo (ej. piezas enteras), y el consumo escalado no da entero:

* Odoo redondea según reglas de UoM.
  ✅ Como tu lote base es fijo (44), minimizas esto.

### 5.2 Sustituciones / alternativos

Si usan componentes alternativos, el consumo puede variar.

* El wizard debe respetar la selección estándar (o dejarlo al planeamiento).

### 5.3 Escasez de componentes

Si no hay materiales disponibles:

* Odoo puede bloquear consumo o lanzar advertencias.
  **Recomendación UX:** antes de producir, el wizard debe:
* mostrar semáforo “materiales ok / faltantes”
* y si faltan, **bloquear** o permitir con rol supervisor.

---

## 6) Recomendación final para tu caso (rápida y segura)

Para tu flujo “1 botón” y BOM por lote (44):

1. Configuren BOM con **cantidad base = tamaño del fardo** (ya lo tienen).
2. Mantener consumo en modo **automático/backflush** (si el proceso lo permite).
3. En wizard:

   * producir X con lote
   * dejar que Odoo consuma estándar
4. Si hay componentes rastreables:

   * definir política: “escaneo obligatorio” o “asignación automática” (no hay magia sin decisión operativa).

---

## Lo que necesito que tu equipo defina (sin frenar el desarrollo)

Para cerrar completamente el diseño de consumo:

1. ¿Los **componentes** (resinas, bolsas, etc.) tienen **lote/serie**?
2. ¿Quieren consumo **automático** (backflush) o deben ajustar consumo real por variación/merma?
3. ¿Registran **scrap/merma**? (si sí, ¿por lote o por MO?)

Con eso te dejo el flujo final de consumo “sin digitación” pero compatible con trazabilidad y mermas.


Perfecto. Con lo que describes, tu flujo es **muy estándar y muy compatible** con el wizard 😄:

* **Resina con lote** ✅
* **Bolsas/viñeta sin lote** ✅
* **Ubicación local de consumo por máquina** + **reabastecimiento automático desde bodega MP** ✅
* **PEPS (FIFO)** en esas ubicaciones ✅
* **Consumo automático (backflush)** ✅
* **Scrap por MO** ✅

Ahora, la pregunta se reduce a: **cómo asegurar que, al crear cada fardo (lote de PT), el consumo automático tome la resina desde la ubicación local del workcenter y asigne el lote PEPS sin pedir digitación**.

---

## 1) Consumo automático con resina loteada: cómo debe funcionar

### Lo que quieres lograr

En cada click “Crear lote (44)”:

* Se produce PT (con su lote de PT)
* Se consume automáticamente:

  * **Bolsas/viñeta**: cantidades fijas por BOM (sin lote)
  * **Resina**: cantidad proporcional por BOM **con asignación de lote automática**, tomada desde:

    * la **ubicación local del workcenter** (no desde bodega MP)
    * aplicando **PEPS/FIFO** para elegir lote

### Condición clave

Para que Odoo asigne lotes automáticamente, se requieren 2 cosas:

1. **Stock disponible** en la ubicación fuente (la local del workcenter)
2. Que el movimiento de consumo esté configurado para **tomar de esa ubicación** (source location del consumo)

Tu estrategia de reabastecimiento ya asegura (1). Hay que asegurar (2).

---

## 2) Cómo amarrar la ubicación de consumo por workcenter (sin hackear)

### En Odoo, el consumo de componentes sale de una “Source Location”

En MRP normalmente es:

* `production_location_id` / “ubicación de componentes” del almacén de producción (según configuración de rutas/almacén)
* o la ubicación configurada en el picking type/warehouse del proceso de fabricación

✅ En tu caso, quieres que sea **dinámica por workcenter**:
`source_location = workcenter.local_consumption_location_id`

**Recomendación limpia:** agregar al `mrp.workcenter` un campo:

* `component_location_id` (Many2one a `stock.location`)
  “Ubicación local de consumo”

Y usar ese campo para que, cuando el wizard registre producción parcial, los **moves de consumo** usen esa ubicación como origen.

---

## 3) Asignación automática del lote de resina (PEPS/FIFO)

Como esas ubicaciones locales tienen **PEPS/FIFO**, Odoo debería reservar los lotes en orden.

**Pero ojo:** para productos con tracking por lotes, Odoo a veces requiere `move_line` con lote explícito. En escenarios bien configurados, la reserva/assign puede crear líneas con lotes automáticamente si:

* el producto es loteado,
* la estrategia de salida está definida,
* y se ejecuta `action_assign`/reserva antes del consumo.

### Regla de implementación para el wizard (muy importante)

Antes de “consumir por backflush”, el wizard debe asegurar:

1. Los `move_raw_ids` estén apuntando a la **ubicación local**
2. Ejecutar la **reserva** de componentes (`action_assign`) para que Odoo elija lotes FIFO
3. Registrar producción parcial

✅ Con esto, normalmente la resina se asigna sola por FIFO en esa ubicación.

---

## 4) Flujo propuesto exacto del wizard (servidor)

### `action_create_batch_lot()`

1. Validar empleado: PIN + allowed + planning + attendance
2. Resolver MO/WO activa
3. Lock (FOR UPDATE) sobre WO/MO
4. Calcular qty = X (44) o restante
5. Crear `stock.lot` para PT
6. **Preparar consumo desde ubicación local**

   * asegurar que los moves de componentes (`move_raw_ids`) tengan `location_id = workcenter.component_location_id`
   * si ya existen moves creados desde otra ubicación, actualizar con criterio (ver nota abajo)
7. `action_assign` en moves de consumo para reservar FIFO
8. Registrar producción parcial con el lote del PT
9. Crear `mrp.batch_ticket` (historial)
10. Imprimir etiqueta

### Nota importante sobre actualizar ubicación en `move_raw_ids`

* Si la MO ya estaba creada con otra ubicación origen, hay dos opciones:

  * **Opción A (recomendada):** al **iniciar** la MO en ese workcenter, ajustar la ubicación una sola vez.
  * **Opción B:** ajustar en cada “Crear lote”.
    (Funciona, pero es menos elegante y puede generar inconsistencias si ya hubo consumo previo.)

Yo recomiendo A: “cuando una MO queda activa en una máquina, fijar su ubicación de consumo a la local”.

---

## 5) Scrap por MO (no por lote): cómo mantenerlo coherente

Como scrap lo manejan **por MO**, no necesitas nada especial por fardo.

Recomendación:

* En el wizard, agregar un botón “Registrar scrap” (solo supervisor o permitido), que:

  * registre scrap contra la MO
  * opcionalmente pida motivo y cantidad
* El scrap no interfiere con el lote de PT.

---

## 6) Reglas de negocio que deben quedar explícitas (para evitar errores)

1. **Una MO activa por workcenter** (o al menos una WO en progress/ready)
2. La ubicación local de consumo debe tener:

   * estrategia de salida **FIFO**
   * stock suficiente (reabastecimiento ya lo garantiza)
3. Para resina loteada:

   * si no hay stock en ubicación local ⇒ bloquear “Crear lote” con mensaje “Resina insuficiente en ubicación local”
4. Si la reserva FIFO no puede asignar lote ⇒ abrir sub-wizard de excepción (solo supervisor) o bloquear.

---

## 7) Entregables técnicos (lo que le pediría a Cursor)

### Prompt 1 — Campo ubicación local por workcenter

“Agrega a `mrp.workcenter` el campo `component_location_id` (Many2one stock.location). Muéstralo en el formulario.”

### Prompt 2 — Ajuste de moves de consumo + reserva FIFO

“En `action_create_batch_lot`, antes de registrar la producción parcial, ajusta `location_id` de `production.move_raw_ids` a `workcenter.component_location_id` si aplica, y ejecuta reserva (`action_assign`) para que se asignen lotes FIFO para componentes con tracking. Si no se logra reservar, lanza UserError con detalle del faltante.”

### Prompt 3 — Validación planning + attendance

“Implementa validación combinada: el empleado debe tener turno actual en Planning y además tener asistencia abierta (checked-in). Si una de las dos falla, bloquear.”

---

## 8) Pregunta final (no bloqueante) para cerrar implementación sin retrabajo

Cuando dices “ubicación de consumo por máquina”:

* ¿Cada workcenter tiene **1 única ubicación** (ej. `MP/E01 DIA`) donde están resinas y consumibles?
  Si sí: perfecto, `component_location_id` es suficiente.

Si por algún motivo tienen dos (resina vs empaques), ya sería `component_location_ids` por categoría, pero no lo recomiendo para fase 1.

---

Si me confirmas que es **una ubicación local por workcenter**, te dejo el **pseudocódigo exacto** (tipo blueprint) para implementar `action_create_batch_lot()` con:

* actualización de ubicación de consumo
* reserva FIFO de lotes de resina
* manejo de excepciones
* producción parcial con lote de PT
* todo con locks y auditoría.

Excelente — si **ya existe 1 ubicación local por workcenter** y **esa ubicación ya está seteada en la misma MO** (campo **`mrp.production.location_src_id`** = “Ubicación de los componentes”), entonces quedas en el escenario más limpio: **no hay que “re-escribir” moves para cambiar ubicación**, solo **verificar consistencia** y luego ejecutar el flujo estándar de **reserva + backflush** ✅

Abajo te dejo el **blueprint/pseudocódigo** definitivo para implementar `action_create_batch_lot()` con:

* **Validación PIN + allowed + Planning + Attendance**
* **Validación de ubicación local de consumo** (MO vs workcenter)
* **Reserva FIFO/PEPS** en ubicación local
* **Auto-asignación de lote de resina** (sin digitación) con fallback controlado
* **Producción parcial con lote de PT**
* **Scrap por MO** (separado)
* **Locks anti doble click**

---

# 1) Supuestos confirmados (tu escenario)

* `mrp.production.location_src_id` = **ubicación local** del workcenter (consumo)
* Esa ubicación tiene **FIFO/PEPS** (strategy salida)
* Resina tiene **tracking por lote**
* Bolsas/viñeta **no tracking**
* Consumo = **automático (backflush)**
* Turnos = **Planning**
* Presencia = **hr_attendance**
* Scrap = **por MO** (no por lote)

---

# 2) Reglas de validación (servidor) antes de producir

### Validación operador (PIN → employee)

Condición para permitir “Crear lote”:

1. `employee` encontrado por PIN
2. `employee ∈ workcenter.allowed_employee_ids`
3. **Planning**: existe turno activo ahora para ese empleado (y opcionalmente asociado al workcenter/rol)
4. **Attendance**: empleado está **checked-in** (open attendance)

> Si falla cualquiera: `UserError` con mensaje claro.

---

# 3) Validación de consistencia ubicación local (MO ↔ Workcenter)

Como ya setean la ubicación local en la MO, el wizard **solo valida** que sea la correcta para esa máquina:

* `production.location_src_id == workcenter.component_location_id`

Si no coincide:

* Bloquear con mensaje:
  “La MO está configurada para consumir desde <X> pero este centro usa <Y>. Reasigne la MO o corrija la ubicación de componentes.”

✅ Esto evita consumos “accidentales” desde bodega MP.

---

# 4) Blueprint técnico — `action_create_batch_lot()`

> Nota: los nombres de métodos internos pueden variar; el objetivo es que Cursor busque los métodos estándar en Odoo 18 y se enganche a ellos. Lo importante es el orden y los puntos de control.

## 4.1 Pseudocódigo (alto nivel)

```python
def action_create_batch_lot(self):
    # 0) Resolver contexto
    workcenter = self.workcenter_id
    pin = self.pin_input

    # 1) Validar operador (PIN + allowed + planning + attendance)
    employee = validate_employee(pin, workcenter)

    # 2) Determinar WO/MO activa
    wo = get_active_workorder(workcenter)
    if not wo:
        raise UserError("No hay orden activa para este centro.")
    mo = wo.production_id

    # 3) Validar consistencia ubicación consumo
    if mo.location_src_id != workcenter.component_location_id:
        raise UserError("La ubicación de componentes de la MO no coincide con la ubicación local del centro.")

    # 4) Calcular qty a producir (X por BOM/producto)
    qty = compute_batch_qty(mo, workcenter)        # típicamente 44 (BOM base)
    remaining = mo.product_qty - mo.qty_produced   # o método estándar para restante
    qty_to_produce = min(qty, remaining)
    if qty_to_produce <= 0:
        raise UserError("La MO ya está completa o no hay cantidad por producir.")

    # 5) Lock anti doble click
    lock_record(wo)  # SELECT FOR UPDATE / write-flag transaccional

    # 6) Asegurar disponibilidad y reserva FIFO de componentes
    ensure_components_reserved_fifo(mo, workcenter, qty_to_produce)

    # 7) Crear lote del producto terminado (PT)
    lot_pt = create_finished_lot(mo.product_id)

    # 8) Registrar producción parcial (sin cerrar MO)
    record_partial_production(wo, mo, qty_to_produce, lot_pt)

    # 9) Historial + impresión
    ticket = create_batch_ticket(mo, wo, workcenter, employee, lot_pt, qty_to_produce)
    print_label(ticket)

    # 10) Respuesta UI
    return success_payload(ticket, mo)
```

---

# 5) Punto crítico: reserva FIFO + auto-lote de resina (sin digitación)

Aquí es donde usualmente se rompe el “1 click”, así que lo dejo blindado.

## 5.1 Objetivo

Antes de registrar producción parcial, el sistema debe tener **los componentes reservados** desde `mo.location_src_id` y, para resina, **con lote asignado**.

## 5.2 Implementación recomendada (dos capas)

### Capa A — Reserva estándar

1. Identificar los `move_raw_ids` correspondientes al qty a producir (proporcional).
2. Ejecutar `action_assign` / `_action_assign` en esos moves para que Odoo reserve desde la ubicación local.
3. Validar que `reserved_availability` (o equivalente) cubre la demanda.

✅ Esto respeta FIFO (por tu estrategia de salida en la ubicación).

### Capa B — Fallback solo para productos con tracking=lote

Si, después de reservar, hay consumo pendiente **sin lote** para resina (casos donde Odoo reserva cantidad pero no fija lot en move_lines), hacer:

* Consultar quants disponibles en `mo.location_src_id` ordenados FIFO (por `in_date`/fecha de entrada)
* Crear/ajustar `stock.move.line` de consumo asignando `lot_id` y qty hasta cubrir lo requerido.

> Este fallback se activa **solo** en componentes con tracking por lote y **solo** si quedó sin lot asignado.

---

## 5.3 Pseudocódigo del módulo de reserva

```python
def ensure_components_reserved_fifo(mo, workcenter, qty_to_produce):
    # 1) Ajustar demanda de moves proporcionalmente (si aplica)
    # (Odoo normalmente calcula consumo esperado; en backflush se basa en qty producido.)

    # 2) Reserva estándar
    raw_moves = mo.move_raw_ids.filtered(lambda m: m.state not in ('done','cancel'))
    raw_moves._action_assign()  # o action_assign()

    # 3) Validar disponibilidad (bloquear si faltantes)
    missing = compute_missing_components(raw_moves, qty_to_produce)
    if missing:
        raise UserError(format_missing(missing))

    # 4) Fallback: forzar lot en tracking 'lot'
    tracked_moves = raw_moves.filtered(lambda m: m.product_id.tracking == 'lot')
    for move in tracked_moves:
        required = compute_required_qty_for_this_batch(move, qty_to_produce)
        allocated = sum(move.move_line_ids.mapped('qty_done')) or sum_reserved(move)
        if allocated < required:
            allocate_fifo_lots_to_move_lines(move, required - allocated, mo.location_src_id)
```

### Función FIFO (conceptual)

```python
def allocate_fifo_lots_to_move_lines(move, qty_needed, location):
    quants = get_quants_fifo(move.product_id, location)  # ordenados por in_date asc
    for q in quants:
        take = min(q.available_qty, qty_needed)
        if take <= 0: 
            continue
        create_or_update_move_line(move, lot=q.lot_id, qty=take, location=location)
        qty_needed -= take
        if qty_needed <= 0:
            break
    if qty_needed > 0:
        raise UserError("Resina insuficiente por lote en ubicación local (FIFO).")
```

**Resultado:** la resina queda consumible sin pedir escaneo, y el lote se asigna PEPS.

---

# 6) Registrar producción parcial “sin cerrar MO”

## Reglas

* Debe crear el movimiento del PT con `lot_pt`
* Debe ejecutar backflush (consumo automático) para el qty producido
* Debe mantener MO/WO en progreso si no llegó al total

**Lineamiento para Cursor:**
“Haz que el wizard llame la misma ruta que usa el Shop Floor para ‘Registrar producción’ en una WO, pero en modo parcial y con lote de PT.”

Esto evita que tú inventes lógica de consumo.

---

# 7) Scrap por MO (separado, compatible)

Como scrap es por MO:

* Agrega acción: `action_register_scrap(mo_id, product_id, qty, reason)`
* No lo amarras al lote de PT.
* En auditoría: `scrap.production_id = mo`

---

# 8) Validación de Planning + Attendance (regla exacta)

Con lo que confirmaste (**sí Planning y sí Attendance**), la regla queda así:

✅ **Permitir operar solo si:**

1. Existe un “slot” actual en Planning para el employee en `now()`
2. Existe una asistencia abierta (checked in) para el employee

**Mensaje de bloqueo:**

* “No tiene turno activo en este horario.” (Planning)
* “Debe registrar entrada (asistencia) antes de producir.” (Attendance)

> Si quieren tolerancia (ej. 5 min antes), se añade luego como parámetro.

---

# 9) Qué cambia en tu configuración actual (casi nada)

Como ya pones la ubicación local en la MO:

* No necesitas alterar `location_src_id` desde el wizard
* Solo agregar:

  * `workcenter.component_location_id` (para comparar)
  * `allowed_employee_ids`
  * flujo PIN+planning+attendance
  * reserva+fallback lot resina
  * ticket+impresión

---

# 10) Checklist de implementación (para que Cursor no se vaya por las ramas)

* [ ] `mrp.workcenter.allowed_employee_ids` (M2M hr.employee)
* [ ] `mrp.workcenter.component_location_id` (M2O stock.location)
* [ ] Validación PIN → employee
* [ ] Validación Planning slot activo
* [ ] Validación Attendance abierta
* [ ] Resolver WO activa
* [ ] Validar `mo.location_src_id == workcenter.component_location_id`
* [ ] Lock transaccional
* [ ] `_action_assign` para reserva FIFO
* [ ] Fallback lot resina si quedó sin lot
* [ ] Crear lote PT
* [ ] Registrar producción parcial sin cerrar MO
* [ ] Crear `mrp.batch_ticket`
* [ ] Imprimir etiqueta

---

## Si quieres, lo siguiente que puedo hacer (y es lo más útil para tu equipo)

Te armo el **set de prompts para Cursor en orden**, con entregables por PR:

1. PR1: campos y vistas workcenter + employee PIN hash
2. PR2: validación PIN+planning+attendance + sesión
3. PR3: MO/WO activa + lock
4. PR4: reserva FIFO + fallback lot resina
5. PR5: producción parcial + ticket + impresión
6. PR6: tests (con casos de resina loteada y FIFO)

Dime si tu equipo maneja el módulo como `addons_custom` y el nombre deseado del módulo (ej. `mrp_tablet_batch_wizard`) y te lo dejo listo para copiar/pegar.
