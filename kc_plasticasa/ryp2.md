Preguntas nuevas (para no asumir mal)
GTIN exacto
¿Usáis siempre 14 dígitos (GTIN-14 / AI 01) o EAN-13 embebido en regla (01) con padding? 
Te dare ejemplos "VINA24oz-V-ANI-35-100P", "FRISTY1/2G-55-NF-88E", "FRUTOS-SILVESTRES1.7L-55.5-88E" de los defualt_code que se manejan y tu sugiereme cual es mas optimo

¿El product.barcode en Odoo ya está cargado como ese valor o hay que mapear desde referencia interna (default_code)?
Seria buscar primero en product.barcode y si no usar default_code mapeado

Peso en el QR (regla kg / AI 40x)
¿El QR de todas las etiquetas debe incluir siempre el tramo de peso, o solo para productos que facturan/pesan en kg? (Afecta a una sola plantilla vs condicional en QWeb.)
Si todas, aqui solo usaran etiquetas lotes de Materia Prima y Producto Terminado

Bloqueo “baja calidad”
¿Aplica solo en albaranes salientes hacia clientes, o también en recepciones / internos al escanear el mismo lote?
Solo Albaranes salientes.

Tolerancia al escanear
La cantidad a comparar contra el tope: ¿la del acumulado escaneado en ese albarán por línea de pedido (como en validación: pedido vs entregado + este albarán), o solo lo incrementado en la sesión de barcode antes de guardar?
pedido vs entregado + este albarán

Impresión Zebra ZD421
¿Imprimís con PDF desde el navegador a la Zebra, con ZPL generado por Odoo, o con middleware (p. ej. servicio en PC/servidor que reciba ZPL por IP)? Esto define si el informe es HTML/PDF o plantilla ZPL.
Tendremos alrededor de 5 impresoras disponebles en red. 
se pueden configurar de alguna manera que se asigne por centro de produccion (mas adelante), asi como por usuario para imprimir directo por ip?

Punto de menú en recepción
¿Preferís botón “Imprimir etiqueta lote” en cada línea detallada del albarán entrante, una sola vez al validar, o ambos?
Botono propio a nivel de documento que se habilite una vez vallidado el documento, imprime todos los lotes del documento.

Idioma de la etiqueta
Texto fijo (“Baja calidad”, títulos): ¿siempre español o según idioma del usuario/empresa?
Segun empresa.