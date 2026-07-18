# Guion de demo — Importador confiable

Duracion objetivo: cinco minutos. Audiencia: responsable de operaciones y responsable tecnico.

## 1. Problema y resultado — 45 segundos

- La limpieza manual tarda aproximadamente 120 minutos por archivo.
- El piloto valida hasta 10,000 registros en menos de cinco minutos.
- Ningun error produce datos parciales ni duplica una importacion.

## 2. Archivo valido — 60 segundos

- Mostrar unicamente los encabezados y datos sinteticos del ejemplo.
- Ejecutar la importacion y leer estado, duracion y conteos del evento JSON.
- Mostrar el reporte sin datos personales.

## 3. Reintento seguro — 45 segundos

- Repetir el mismo archivo.
- Explicar `already_imported`, cero insertados y conteo estable en PostgreSQL.

## 4. Conflicto y rollback — 75 segundos

- Ejecutar el ejemplo conflictivo.
- Mostrar el codigo de fila y `customer_conflict`, sin mostrar el email en el reporte.
- Confirmar que el cliente nuevo incluido en ese lote tampoco fue insertado.

## 5. Operacion — 45 segundos

- Mostrar la migracion actual y el estado saludable de PostgreSQL.
- Recorrer brevemente el runbook por `status`.
- Explicar que `operation_id` permite correlacionar soporte sin registrar PII.

## 6. Limites y siguiente paso — 30 segundos

- El email es una identidad provisional.
- Falta validar el flujo con un usuario real y definir actualizaciones autorizadas.
- La base local usa datos sinteticos y no representa una configuracion productiva.

