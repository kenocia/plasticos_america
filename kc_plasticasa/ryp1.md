¿Tenéis stock_barcode (Enterprise) instalado y lo vais a usar sí o sí en despachos? Sin eso, el alcance de “al escanear” cambia mucho (p. ej. solo vuestro asistente stock.picking.scan.lots.wizard).
Si, se tienen handheld para esa operacion.

QR / código: ¿el QR contendrá solo AI 10 + AI 30 (y eventualmente peso), o también GTIN / referencia interna (p. ej. AI 01 / código producto) para forzar el producto aunque el lote sea raro?
Es necesaria el GTIN, solo me indicas com oconfigurar en la Nomenclature GS1, Incluye en parte humana de la etiqueta de lote lod e Baja Calidad si tiene el true en lote

“Cantidad = existencia” en la etiqueta: ¿es la cantidad total del lote en stock (suma de quants con ese lote), la cantidad en una ubicación (¿cuál?), la cantidad del movimiento de entrada que imprimís, o un valor fijo al crear el lote? Esto define el método y el momento del cálculo al imprimir.
Se va evitar como politica de le empresa dividir el lote en varias ubicaciones, por eso se movera en cantidad completa, pero si se da el caso es mejor considerar la suma de quants

Baja calidad: si el cliente no tiene scan_lote_quality_low, ¿queréis bloquear el escaneo, avisar y permitir con pin/permiso, o solo aviso?
bloquear el escaneo

Tolerancia %: ¿queréis advertencia en pantalla al escanear cuando se supere el tope, o os basta con el error al validar que ya tenéis?
si se necesita adevertencia aparte de el error al validar, deberia no permitir escanear mas de la tolerancia

Nomenclatura “LOTES”: ¿el QR debe generarse exactamente con el mismo orden de elementos y separador FNC1 que en la tabla de reglas, o necesitáis varias plantillas (solo lote+cantidad vs lote+cantidad+peso)?
segun la tabla de reglas con el separador FNC1

Impresión: ¿solo desde el formulario de lote, o también desde recepción al confirmar cantidad / al validar el albarán entrante, o ambas con el mismo diseño?
Ambas con el mismo diseño se usaran impresoras en red Zebra ZD421