# Proceso de uso: Asistente tablet

## Acceso para el empleado (sin Configuración)

1. **Menú**  
   **Manufactura** → **Asistente tablet**.

2. **Elegir centro**  
   Se muestra una lista solo con los centros de trabajo. El empleado pulsa **Abrir asistente** en la fila de su centro.

3. **Identificación**  
   Se abre el asistente en modo “Identificación”:
   - Introducir **PIN** del empleado.
   - Pulsar el botón de validar (o siguiente).

4. **Validaciones**  
   - El PIN debe ser correcto y el empleado activo.
   - Si en el centro está configurado “Empleados permitidos” (módulo Órdenes de trabajo), el empleado debe estar en esa lista.
   - Debe existir al menos una **orden de trabajo** en estado *En progreso* o *Disponible* para ese centro.

5. **Pantalla de producción**  
   Tras validar el PIN se muestra:
   - Orden de fabricación y cantidad por lote (según BOM).
   - Botón para **Crear lote (fardo)**.

6. **Registrar un lote**  
   Al pulsar **Crear lote (fardo)**:
   - Se crea un lote de producto terminado.
   - Se registra la producción parcial (cantidad del lote).
   - Se genera un **ticket de lote** (viñeta) y se lanza la impresión.
   - El asistente sigue abierto para registrar más lotes si hace falta.

7. **Historial y reimpresión**  
   **Manufactura** → **Tickets de lote**: se listan todos los tickets; desde cada uno se puede **Reimprimir** la viñeta.

---

## Configuración (administrador)

- **Centros de trabajo**  
  En **Manufactura** → **Configuración** → **Centros de trabajo**, en cada centro:
  - **Tablet / Operaciones**: “Exigir PIN”, “Exigir turno y asistencia”.
  - El botón **Asistente tablet** en el formulario del centro también abre el wizard (mismo flujo).

- **Empleados permitidos**  
  Si se usa el módulo de órdenes de trabajo, en cada centro se puede restringir qué empleados pueden operar (y por tanto usar el asistente).

- **Permisos**  
  Para que el empleado **solo** tenga el menú “Asistente tablet” y no Configuración:
  - Asignar un grupo que tenga acceso a la acción **Asistente tablet** (y a `mrp.workcenter` en lectura para la lista).
  - No dar acceso a “Configuración” de Manufactura ni a la acción de “Centros de trabajo” de configuración.

---

## Resumen del flujo

| Paso | Dónde | Acción |
|------|--------|--------|
| 1 | Manufactura → Asistente tablet | Abrir menú |
| 2 | Lista de centros | Pulsar **Abrir asistente** en su centro |
| 3 | Wizard (PIN) | Introducir PIN y validar |
| 4 | Wizard (producción) | Pulsar **Crear lote (fardo)** |
| 5 | (Opcional) Tickets de lote | Reimprimir viñetas |
