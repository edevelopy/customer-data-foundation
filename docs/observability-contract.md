# Contrato de observabilidad

## Evento de importacion

Cada ejecucion de `fde-import` y cada solicitud procesada por la API emite exactamente un
objeto JSON por `stdout`. Un reintento HTTP reconocido usa `status=idempotent_replay` en el
evento, sin cambiar el estado persistido de la operacion original.

| Campo | Tipo | Uso |
|---|---|---|
| `operation_id` | UUID | Correlacionar reporte, ejecucion y soporte |
| `status` | Texto | Clasificar el resultado operacional |
| `duration_ms` | Entero | Medir latencia del flujo completo |
| `total_rows` | Entero | Tamano validado del lote |
| `inserted_rows` | Entero | Clientes creados en esta ejecucion |
| `existing_rows` | Entero | Clientes identicos o lote ya procesado |
| `error_codes` | Lista | Diagnostico agregable sin copiar mensajes ni valores |

## Estados

| Estado | Codigo de salida | Significado |
|---|---:|---|
| `imported` | 0 | Transaccion confirmada |
| `already_imported` | 0 | Mismo archivo procesado anteriormente |
| `validation_failed` | 1 | Contrato CSV incumplido; no hubo conexion |
| `conflict` | 1 | Cliente existente diferente; hubo rollback |
| `configuration_error` | 2 | Falta configuracion local |
| `migration_required` | 2 | Esquema ausente o desactualizado |
| `database_error` | 2 | PostgreSQL no permitio completar la operacion |

## Datos deliberadamente excluidos

No se permiten nombres, emails, telefonos, ruta o nombre del archivo, contenido recibido,
hash del archivo, usuario de PostgreSQL, contrasena, host ni URL de conexion. El reporte
detallado conserva fila, campo, codigo y correccion, pero tampoco copia valores recibidos.

## Metricas derivadas

- Tasa de exito: `imported` y `already_imported` dividido por ejecuciones totales.
- Latencia: percentiles de `duration_ms` por `status`.
- Calidad de entrada: frecuencia de `validation_failed` y sus `error_codes`.
- Conflictos: frecuencia de `customer_conflict`.
- Volumen: suma de `total_rows`, `inserted_rows` y `existing_rows`.
