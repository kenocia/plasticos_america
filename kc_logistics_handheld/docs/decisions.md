# Decisiones — kc_logistics_handheld

Registro liviano de decisiones de arquitectura (ADR).

---

## 2025 — App unificada vs. módulos separados

**Decisión:** Consolidar operaciones handheld de logística en una sola aplicación Odoo (`kc_logistics_handheld`) que absorbe `kc_internal_lot_scanner`.

**Motivo:** Los operadores de almacén usan un solo dispositivo y un solo punto de entrada; reduce menús dispersos y simplifica permisos.

**Alternativas descartadas:**
- Mantener módulos independientes (scanner interno, despachos, físico) con menús separados.
- Integrar todo en `kc_plasticasa` sin capa handheld dedicada.

**Impacto:** Un menú «Logística», permisos centralizados en `res.users`, migración automática de metadatos XML del módulo absorbido.

---

## 2025 — Permisos por campos booleanos en usuario

**Decisión:** Controlar visibilidad de Despachos / Internos / Físico con tres booleanos en `res.users`, además del grupo de seguridad base.

**Motivo:** Un mismo perfil «operador almacén» puede necesitar solo uno o dos flujos; más flexible que tres grupos mutuamente excluyentes.

**Alternativas descartadas:**
- Un grupo por flujo (Operador Despachos, Operador Internos, etc.).
- Solo el grupo base sin granularidad (todos ven todo).

**Impacto:** Pestaña «Logística Handheld» en formulario de usuario; método `kc_logistics_handheld_permissions_for_uid()` como fuente de verdad en servidor.

---

## 2025 — Navegación `target=main` en Odoo 18

**Decisión:** Todas las acciones del launcher usan `target=main` para sustituir la pila de migas de pan.

**Motivo:** En handheld, el launcher transient no debe quedar «debajo» en el historial de navegación; experiencia similar a app nativa.

**Alternativas descartadas:**
- `target=current` (mezcla con backend de escritorio).
- `target=new` para flujos principales (abre modales encadenados).

**Impacto:** Helper `_handheld_nav_action()` en launcher; botón «Menú principal» en kanban de despachos vuelve al launcher.

---

## 2025 — Validación de stock en ubicación exacta (internos)

**Decisión:** Al escanear un lote interno, verificar disponibilidad solo en `location_id` del tipo de operación, sin incluir ubicaciones hijas.

**Motivo:** Los traslados internos configurados apuntan a ubicaciones operativas concretas; evita mover stock que físicamente está en otra zona aunque sea «debajo» en la jerarquía.

**Alternativas descartadas:**
- `child_of` en dominio de quants (más permisivo, riesgo de pickear stock de sububicación incorrecta).
- Sin validación previa (errores solo al validar picking).

**Impacto:** Mensajes explícitos si el lote existe pero en otra ubicación; operador debe corregir stock o tipo de operación antes de escanear.

---

## 2025 — Creación y validación automática del picking interno

**Decisión:** Un solo botón «Crear y Validar Transferencia» genera el `stock.picking`, confirma, asigna move_lines por lote y llama `button_validate` con auto-procesado de wizards intermedios.

**Motivo:** Handheld debe minimizar pasos; el operador no debe volver al backend de escritorio para confirmar.

**Alternativas descartadas:**
- Solo crear picking en borrador y validar manualmente después.
- Validar por línea en cada escaneo (demasiadas transacciones).

**Impacto:** Sesión pasa a `done`; logs a `transferred`; posible marca `low_quality` en lotes según tipo de operación.

---

## 2025 — Despachos y físico delegados a `kc_plasticasa`

**Decisión:** Este módulo no reimplementa wizards de despacho ni de toma física; reutiliza acciones y modelos de `kc_plasticasa`.

**Motivo:** Evitar duplicar parseo GS1, tolerancias de entrega y lógica de comparación física ya probada en plasticasa.

**Alternativas descartadas:**
- Copiar wizards a `kc_logistics_handheld` (doble mantenimiento).
- Dependencia opcional de plasticasa (rompería despachos y físico).

**Impacto:** `depends` obligatorio sobre `kc_plasticasa`; configuración de `kc_enable_gs1_dispatch_wizard` y ubicaciones físicas sigue en plasticasa/compañía.

---

## 2025 — Widget JS propio para escaneo interno

**Decisión:** Campo `kc_internal_gs1_barcode_scan` con auto-procesado, debounce, anti-duplicado 2.5s y foco vía `kc_focus_token`.

**Motivo:** Pistolas lectoras envían Enter/Tab y códigos concatenados; replicar comportamiento probado en `kc_plasticasa` sin acoplar assets entre módulos.

**Alternativas descartadas:**
- Botón manual «Procesar QR» únicamente (lento en piso).
- Reutilizar asset de plasticasa por herencia directa (acoplamiento de rutas estáticas).

**Impacto:** Dos archivos JS + CSS en `static/src/`; vista form con `js_class=kc_internal_gs1_scan_wizard`.
