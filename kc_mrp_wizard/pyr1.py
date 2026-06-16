1) Cómo “terminar” la MO si todo el reporte es por el asistente
En Odoo, cerrar la fabricación no es lo mismo que reportar cantidad producida:

Cantidad y stock de PT: se van sumando con cada “parcial” bien hecho 
(tu _tablet_create_batch_lot_impl hace _action_done del movimiento de terminado y de las materias, y sube wo.qty_produced; la MO actualiza qty_produced).
Cierre formal de la MO: cuando qty_produced alcanza lo planificado (salvo scrap/backorder), 
hace falta el paso estándar de validar/cerrar la orden (to_close → done según flujo de tu versión).
Recomendación de producto:

Regla en tablet: cuando restante <= 0 (o por redondeo), mostrar acción explícita “Cerrar orden de fabricación” que llame al método estándar de cierre 
(o abra un wizard mínimo si Odoo pide confirmación/scrap/backorder). Implementar en el wizard.

Regla en WO: cuando la MO está lista para cerrar, el operador (o el último centro) debe poder “Marcar operación como hecha” (action_finish ya delega al estándar); si hay varias WO en la misma MO, define si todas deben estar en done antes de permitir cerrar la MO.
Así no dependes de la pantalla clásica “Registrar producción” para seguir avanzando: el asistente es la única vía de reporte, pero el cierre sigue siendo un evento explícito (evita MOs colgadas en to_close).



2) Varios equipos por centro, conteo por operación y lotes solo al final
Aquí hay tres capas que conviene no mezclar:

Capa	Qué quieres medir	Herramienta típica en Odoo
Operación
Piezas buenas/rechazadas, vueltas de máquina, metros
Contador en orden de trabajo o modelo propio ligado a mrp.workorder
Inventario / trazabilidad PT
Unidad logística con etiqueta
stock.lot + movimiento de stock
WIP intermedio
“Bolsa grande” entre máquinas
Producto semi-elaborado con lote, o ubicación WIP sin lote (solo cantidad) según proceso
Sin lote en operaciones intermedias es coherente si no hay movimiento de stock de PT en esas etapas: solo avanzas tiempo/cantidad de proceso en la WO. El lote de PT se crea cuando haces el movimiento que da de alta el producto terminado (o el semi-acabado, si decidís trazarlo).

“Bolsón” / lote tipo bolsa:

Si el “bolsón” sale a inventario o debe rastrearse: suele ser otro producto (WIP) o el mismo PT con lote intermedio — es decisión de negocio y de auditoría.
Si es solo acumulado en máquina hasta empacar: puede ser campo numérico + historial (por turno/operador) sin stock.lot hasta el cierre del bolsón.
Parametrización por operación (alineada con lo que planteas): en la operación o en el workcenter (o en una extensión de mrp.routing.workcenter / línea de ruta):

tablet_track_qty_only — solo contadores, sin crear stock.lot.
tablet_create_finished_lot — esta operación dispara creación de lote + ticket.
tablet_batch_qty_source — fijo / desde BOM / manual.
Así una línea puede contar en extrusión y etiquetar solo en corte/empaque.

3) Wizard centrado en WO hoy vs varias WO por MO (tablet)
Estado actual: el tablero filtra por workcenter y la sesión lleva una WO; qty_pending en la WO usa production_id.product_qty - production_id.qty_produced (es pendiente de la MO, no “pendiente de esta operación”). Eso encaja con una operación que agota el PT, pero no con “cada operación tiene su propio remanente lógico”.

Escenarios de control (de más simple a más robusto):

Una WO activa por centro (lo que ya describe analisis.md): priorizar progress, luego ready; si hay empate, selector en tablet.
Varias WO del mismo MO en el mismo centro (poco habitual): obligatorio elegir WO antes de contar o crear lote.
Varias WO en secuencia en el MO (lo típico multi-máquina): la tablet del centro B solo muestra WO cuya operación anterior esté cumplida (o permitir “esperando” con mensaje claro).
Vista “por MO” (opcional): cabecera MO + lista de operaciones con semáforo; al pulsar una fila se abre el mismo kanban pero con workorder_id fijado.
Para control desde tablet, conviene definir:

Quién “posee” el conteo de buenas: solo la WO que declara PT, o cada WO suma a un acumulado propio.
Quién puede crear lote: solo la última operación o cualquiera con flag.
Cómo encajar lo que viene (paros, calidad, etc.)
Ya tenéis paros que pueden crear alerta y/o mantenimiento y bloqueo al iniciar si hay alertas abiertas por paro. El siguiente paso de análisis sería concretar:

Paros: duración (inicio/fin), motivo obligatorio, si pausan solo la WO o bloquean el centro.
Calidad: muestreo por lote vs por hora; NC vinculada a mrp.batch.ticket o solo a MO/WO.
Rendimiento: OEE opcional (tiempo productivo vs paros).
Resumen directo para tus tres dudas
Finalizar MO: seguid produciendo por el asistente hasta completar cantidad; luego acción explícita de cierre (estándar MRP) + marcar WO(s) hechas. No hace falta usar la pantalla antigua de “producir” si el asistente cubre el mismo efecto contable y de stock.
Conteo sin lote en operaciones: sí, usando WO / modelo de conteo; reservad stock.lot para cuando haya movimiento de PT (o parametrizad “lote en esta operación”).
1:1 WO vs N WO por MO: reforzad selección de WO activa, reglas de secuencia, y si hace falta pendiente por operación en lugar de solo pendiente de MO.
Cuando quieras pasar a requisitos de control (paros en detalle, calidad, mermas), podemos bajar esto a una matriz: evento → modelo Odoo → quién lo dispara en tablet → bloqueos. Si te parece, en el siguiente mensaje definimos solo dos cosas: ¿en qué operación se crea el primer stock.lot de PT? y ¿hay producto semi-acabado con stock entre máquinas o todo es WIP interno sin trazabilidad por lote? Con eso se cierra el diseño de lotes y contadores.