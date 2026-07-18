# Evidencia de Fase 1 — Contrato y validacion estricta

Fecha de verificacion: 17 de julio de 2026.

## Decision aprobada

El lote opera en modo estricto: cualquier error rechaza todos los registros. El validador
no persiste datos; PostgreSQL se incorporara despues de estabilizar este contrato.

## Evidencia observada

| Escenario | Resultado |
|---|---|
| CSV valido de ejemplo | Aceptado, codigo de salida 0 |
| CSV con errores de fila | Rechazado, codigo de salida 1 |
| Columna inesperada | Rechazada antes de leer registros |
| Email repetido con distintas mayusculas | Lote rechazado |
| Campos y formatos invalidos | Errores asociados a fila y campo |
| Reporte JSON | No contiene emails ni telefonos recibidos |
| Limite de 10,000 registros | Aceptado en aproximadamente 0.07 segundos en el entorno local |
| Suite local | 10 pruebas aprobadas |
| Ruff | Formato y linting aprobados |

El tiempo local es evidencia de esta ejecucion, no una garantia universal. El criterio de
producto continua siendo menos de cinco minutos en el entorno del piloto.

## Riesgos pendientes

- El email es una clave natural provisional y puede no representar una persona unica.
- Todavia no se comprueba un duplicado contra una base de datos existente.
- El formato E.164 exige que el proveedor incluya codigo de pais.
- No existe todavia transaccion de base de datos ni recuperacion ante fallos de escritura.

## Incremento siguiente

La persistencia transaccional en PostgreSQL fue implementada en el incremento siguiente.
Consulta [`phase-1-database-evidence.md`](phase-1-database-evidence.md).

