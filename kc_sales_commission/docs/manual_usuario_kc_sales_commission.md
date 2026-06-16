# Manual de Usuario - KC Comisiones de Ventas

## 1. Objetivo

Este manual explica como configurar y operar el modulo `kc_sales_commission` para calcular, confirmar, pagar y reportar comisiones de ventas por empleado.

## 2. Alcance y roles

Este proceso aplica para usuarios con acceso al menu **Comisiones**.

- Rol **Comisiones de ventas / Usuario**: puede operar calculos, revisar detalle, registrar pagos y generar reportes.
- Rol **Comisiones de ventas / Responsable**: incluye permisos ampliados de administracion.

> Nota: si un usuario no ve el menu **Comisiones**, primero validar sus grupos de seguridad.

## 3. Prerrequisitos

Antes de generar una comision, validar:

1. El empleado tiene configurado `Tipo de comision` y `Valor comision`.
2. Los clientes tienen asignado `Empleado comisionista`.
3. Existen facturas o notas de credito de cliente en estado publicado dentro del rango de fechas.
4. Hay un diario de pago tipo banco o caja con metodo de pago de salida configurado (para registrar pagos).
5. Opcionalmente, productos o categorias pueden tener:
   - `Excluir de comision`
   - `Comision especifica` (tipo y valor propios)

## 4. Configuracion inicial

### 4.1 Configurar parametros en empleado

1. Ir a **Empleados**.
2. Abrir el empleado comisionista.
3. Entrar a la pestaña **Comisiones**.
4. Definir:
   - `Tipo de comision` (`Por unidad` o `Por porcentaje`)
   - `Valor comision`
5. Guardar.

### 4.2 Asignar comisionista a clientes

1. Ir a **Contactos**.
2. Abrir el cliente.
3. En la pestaña de ventas/compras, ubicar grupo **Comisiones**.
4. Seleccionar `Empleado comisionista`.
5. Guardar.

### 4.3 Configuracion opcional por producto o categoria

Si se necesita excepcion en el calculo:

1. Abrir **Producto** o **Categoria de producto**.
2. Configurar alguno de estos campos:
   - `Excluir de comision` para no comisionar ese item.
   - `Comision especifica` para sobreescribir regla general.
3. Guardar.

## 5. Flujo operativo (paso a paso)

### 5.1 Generar un calculo de comision

1. Ir a **Comisiones > Generar Comision**.
2. Completar:
   - `Compañia`
   - `Empleado`
   - `Fecha inicial`
   - `Fecha final`
3. Presionar **Generar**.
4. El sistema crea el calculo y carga automaticamente:
   - Clientes comisionados
   - Facturas/NC publicadas en el rango
   - Detalle por producto con total de comision

### 5.2 Revisar resultado del calculo

En el formulario de comision, validar:

- **Resumen**: total clientes, total facturas, total venta, total comision.
- Pestaña **Clientes**: clientes incluidos.
- Pestaña **Facturas**: documentos y montos.
- Pestaña **Detalle por producto**: unidades/venta/tasa y comision final.

Si algo no es correcto, usar **Recalcular** (solo disponible en estados permitidos y sin pagos asociados no cancelados).

### 5.3 Confirmar calculo

1. Cuando el resultado sea correcto, presionar **Confirmar**.
2. El estado cambia a **Confirmado**.
3. Desde este punto, el flujo continua a pagos.

## 6. Registro de pagos de comision

### 6.1 Crear pago

1. Con la comision en estado **Confirmado** (o estados de pago), presionar **Pagar**.
2. En el asistente completar/revisar:
   - `Beneficiario`
   - `Importe`
   - `Fecha de pago`
   - `Diario de pago`
   - `Referencia / memo`
3. Presionar **Crear pago**.
4. El sistema abre el pago contable relacionado.

### 6.2 Revisar pagos vinculados

- Usar boton **Ver pagos** o el indicador de pagos en la parte superior.
- Cada pago queda ligado al calculo mediante el campo `Comision de ventas`.

### 6.3 Interpretacion del saldo

En la seccion **Liquidacion de pagos**:

- `Importe en pagos`: suma de pagos registrados (excepto cancelados/rechazados).
- `Pagado (confirmado)`: pagos ya pagados.
- `Saldo pendiente`: total comision menos pagos registrados.
- Si hay pago parcial, aparece una cinta **Pago parcial**.

## 7. Estados del calculo y comportamiento

- `Borrador`: etapa inicial editable.
- `Calculado`: lineas generadas; puede confirmarse.
- `Confirmado`: habilita registro de pagos.
- `Pago en borrador`: hay pagos no completados.
- `Pago confirmado`: pagos en estado pagado.
- `Bloqueado`: pagos conciliados; no permite recalculo/pagos/cancelacion.
- `Cancelado`: calculo anulado; puede volver a borrador.

## 8. Reportes

Desde el formulario del calculo:

- **Imprimir PDF**: reporte de autorizacion/liquidacion.
- **Exportar Excel**: archivo detallado para analisis y control.

## 9. Errores frecuentes y solucion

### 9.1 "El empleado no tiene clientes asignados como comisionista"

Causa: no hay clientes vinculados al empleado.  
Solucion: asignar `Empleado comisionista` en contactos.

### 9.2 "No hay facturas o notas de credito en el rango"

Causa: no existen documentos de cliente publicados para esas fechas/clientes.  
Solucion: validar fechas, estado de facturas y cliente comisionado.

### 9.3 "No hay lineas de comision generadas"

Causa: productos excluidos o lineas de factura sin producto valido.  
Solucion: revisar configuracion de productos/categorias y lineas facturadas.

### 9.4 "Confirme el calculo antes de registrar pagos"

Causa: intento de pago en estado no permitido.  
Solucion: confirmar el calculo primero.

### 9.5 "No hay saldo pendiente de comision por pagar"

Causa: ya se cubrio el total de la comision.  
Solucion: verificar pagos existentes antes de crear uno nuevo.

### 9.6 "El diario no tiene metodo de pago de salida"

Causa: diario contable incompleto.  
Solucion: configurar metodo de pago de salida en el diario (banco/caja).

## 10. Checklist de cierre operativo

Antes de cerrar periodo, validar:

- [ ] Todos los calculos requeridos fueron generados por empleado y rango.
- [ ] Cada calculo fue revisado (clientes, facturas, detalle y total).
- [ ] Los calculos correctos estan en estado confirmado/pagado.
- [ ] Los pagos fueron registrados y conciliados cuando corresponda.
- [ ] Se emitio respaldo en PDF y/o Excel.

## 11. Recomendaciones de uso

1. Definir calendario fijo de generacion (semanal/quincenal/mensual).
2. Bloquear cambios de configuracion durante el corte de comisiones.
3. Guardar Excel/PDF en carpeta compartida por periodo.
4. Usar filtros por estado y empleado para auditoria rapida.

