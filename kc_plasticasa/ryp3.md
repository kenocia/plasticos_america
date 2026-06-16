Preguntas que siguen haciendo falta
Valor del peso en el QR (AI 40x)
¿De dónde sale el número? Por ejemplo: gramaje teórico del producto, peso del quant al imprimir, peso del movimiento validado, o redondeo entero en kg para la etiqueta. (Afecta si es “informativo” en etiqueta vs dato que debe cuadrar con inventario.)
Cabe aclarar que en los lotes de PT todo es en unidades, pero la Materia prima es en kg, se debe configurar tanto para peso como unidades, en la nomenclatura GS1?

Resolución producto sin barcode numérico
¿Confirmáis que aceptáis AI 240 (o similar) + búsqueda por default_code en desarrollo, o preferís exigir que todo MP/PT tenga barcode numérico cargado antes de imprimir?
AI 240 (o similar) + búsqueda por default_code en desarrollo por ahorita, si se definen codigos numericos para MP/PT hacemos el cambio.

Botón masivo en recepción
El albarán entrante validado: el informe debe generar una etiqueta por cada combinación (producto, lote) presente en los movimientos hechos de ese albarán, ¿incluyendo cantidad = suma de quants de ese lote en ese momento, o cantidad movida en ese albarán por línea? (Para MP/PT a veces difiere del stock global del lote.)
si cantidad + suma quants

Impresión directa por IP (fase 1 vs 2)
Para la primera entrega, ¿os vale PDF estándar de Odoo (usuario elige impresora Zebra) o queréis ya ZPL enviado a IP:9100 desde el servidor? (Seguridad de red y permisos cambian mucho.) hagamolo ahorita pdf, despues implementamos algo por ip.


Ambigüedad: “cantidad + suma quants”
En la línea 12 indicáis «si cantidad + suma quants». Para no implementar mal, confirmad cuál es la intención:

A) En la etiqueta van dos datos: (1) cantidad movida en ese albarán (lo recibido en el documento) y (2) existencia total del lote (suma de quants en ese momento).
B) Un solo número que sea solo la suma de quants.
C) Un solo número que sea solo la cantidad del movimiento.
La opción A encaja con “cantidad + suma quants” literal y con lo que ya comentasteis antes sobre existencia.

R: La opcion A pero es la suma de la cantidad movida + la existencia todal del lote, en un solo dato en la etiqueta.

Micro-pregunta: PT y tramo de peso en el QR
En ryp2 dijisteis que el QR lleva peso en todas las etiquetas. Para PT (solo unidades), 
¿se mantiene igualmente un tramo 40x (p. ej. peso 0 o peso teórico), o en PT omitís el AI de kg y dejáis solo (01)/(240) + (10) + (30)?
se busca un solo datos: existencia + unidad de medidad, si lo de kg no ayuda se quita, estamos en etapa de desarrollo

