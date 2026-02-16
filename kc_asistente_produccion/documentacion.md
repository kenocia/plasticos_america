Creá esta estructura en el repo (1 vez):
docs/
state_<modulo>.md   (uno por cada módulo que sí participe en el desarrollo; los nombres son ejemplos)
decisions.md
changelog.md
test_matrix.md

Qué va en cada archivo
docs/state_<modulo>.md (1 por módulo involucrado en este desarrollo)
Ejemplo: si el desarrollo toca MRP, HR y Stock, crear state_mrp.md, state_hr.md, state_stock.md (no hace falta state_sales ni state_project si no aplican).

Formato recomendado:
• Scope del módulo: qué cubre y qué NO.
• Modelos tocados: product.template, stock.move, etc.
• Campos añadidos: nombre, tipo, compute, store, dependencies.
• Vistas afectadas: qué vistas / menús.
• Reglas de negocio: bullets, sin novela.
• Integraciones/efectos colaterales: contabilidad, reportes, POS, etc.
• Riesgos conocidos: performance, permisos, multi-company.
• Pendientes: TODOs priorizados.• Estado actual: “listo / en progreso / bloqueado”.

docs/decisions.md
Registro de decisiones tipo ADR (Architecture Decision Record) pero liviano:
• Fecha
• Decisión
• Motivo
• Alternativas descartadas
• Impacto

docs/changelog.md
Lista de cambios por fecha y commit/branch si aplican.

docs/test_matrix.md
Tabla de pruebas manuales y casos clave (por módulo)