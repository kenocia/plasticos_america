# Changelog — kc_logistics_handheld

Cambios por versión del módulo. Fechas aproximadas según historial de desarrollo.

---

## 18.0.1.2.1

- Versión actual en manifiesto.
- Ajustes de navegación handheld (`target=main`) y botón «Menú principal» en kanban de despachos.
- Widget de escaneo interno con auto-procesado, notificaciones y anti-duplicado.

---

## 18.0.1.1.0

- Migración script `post-move_internal_lot_scanner.py`: reasigna `ir.model.data` de `kc_internal_lot_scanner` a `kc_logistics_handheld`.
- Marca módulo antiguo `kc_internal_lot_scanner` como `to remove` si estaba instalado.
- Post-init hook activa `kc_enable_internal_lot_scanner` en todos los tipos de operación interna existentes.

---

## 18.0.1.0.0 (release inicial)

- App «Logística» con launcher transient (`kc.logistics.handheld.launcher`).
- Tres flujos: Despachos (kanban), Operaciones internas GS1 (wizard), Toma física previo (acceso a `kc_plasticasa`).
- Modelos nuevos: `kc.internal.lot.scan.session`, `.session.line`, `.log`.
- Wizard `kc.internal.lot.transfer.wizard` con parseo GS1, validación de stock y creación/validación de picking.
- Extensión `stock.picking` (etiquetas handheld, kanban).
- Extensión `stock.picking.type` (`kc_enable_internal_lot_scanner`, `kc_mark_low_quality`).
- Permisos en `res.users` y grupo `Operador Logística Handheld`.
- Secuencias `GS1INT/` y `GS1LOG/`.
- Vistas móvil: CSS handheld, kanban despachos, formulario wizard interno.
- Menú «Historial escaneos GS1 internos» para responsables de inventario.
- Dependencia declarada: `kc_plasticasa`.

---

## Módulo absorbido: kc_internal_lot_scanner

Funcionalidad migrada a este módulo:

- Escaneo GS1 en transferencias internas por lote.
- Sesiones y logs de auditoría.
- Configuración en tipo de operación interna.

**Acción requerida en actualización:** desinstalar `kc_internal_lot_scanner` tras instalar/actualizar `kc_logistics_handheld` (el hook lo marca automáticamente para remover).
