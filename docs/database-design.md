# Diseno de PostgreSQL e importacion

Estado: actualizado hasta el Incremento 5 de la Fase 2.

## Semantica

- Un archivo invalido no abre una conexion ni escribe en PostgreSQL.
- Un archivo valido se procesa en una unica transaccion.
- Repetir exactamente el mismo archivo devuelve `already_imported` y no escribe filas.
- Un email existente con los mismos datos se considera idempotente.
- Un email existente con datos diferentes genera `customer_conflict` y revierte el lote.
- Los errores y reportes no incluyen emails, telefonos ni la URL de conexion.

## Modelo

### `import_batches`

Registra unicamente lotes completados. `file_sha256` es unico y evita procesar dos veces
los mismos bytes, incluso ante dos procesos concurrentes.

| Columna | Proposito |
|---|---|
| `id` | UUID generado por la aplicacion |
| `file_sha256` | Huella unica del archivo |
| `row_count` | Registros validados |
| `inserted_count` | Clientes nuevos |
| `existing_count` | Clientes identicos ya presentes |
| `created_at` | Momento confirmado por PostgreSQL |

### `customers`

Mantiene el cliente normalizado y referencia el lote que lo creo. `email` tiene una
restriccion unica y comprobaciones de formato y longitud proporcionales al contrato.

### `api_operations`

Conserva el estado tecnico de cada solicitud HTTP, su propietario seudonimizado y el resultado
idempotente. Una finalizacion aceptada crea el evento de integracion dentro de la misma
transaccion; por eso no puede existir un resultado confirmado sin su notificacion durable.

### `integration_outbox`

Registra un evento tecnico por `operation_id`. El payload contiene identificadores, estado y
conteos, pero no perfiles de clientes. `available_at`, `lease_expires_at` y `attempt_count`
permiten que varios workers reclamen trabajo con `FOR UPDATE SKIP LOCKED`, recuperen leases
vencidos y descarten confirmaciones de intentos obsoletos.

### `partner_delivery_attempts` y `partner_receipts`

Pertenecen exclusivamente al simulador local del socio. La primera tabla hace reproducibles los
fallos transitorios; la segunda deduplica cada `event_id` y detecta si se intenta reutilizar con
otro cuerpo. Un socio real debe mantener estas tablas —o un mecanismo equivalente— en su propio
almacenamiento.

## Limite transaccional

La reserva del hash, la comprobacion de conflictos, la insercion de clientes y la
actualizacion de contadores ocurren dentro de la misma transaccion. Cualquier conflicto o
error de PostgreSQL produce rollback; no existe un estado parcialmente importado.

## Migraciones

Alembic administra una cadena cuyo estado actual es `0004_integration_outbox`. La aplicacion
comprueba que la base se encuentre exactamente en la revision vigente y devuelve
`migration_required` sin escribir si falta. Las migraciones se ejecutan como una operacion
separada antes de iniciar API, worker o socio simulado.

## Seguridad local

- PostgreSQL solo publica el puerto en `127.0.0.1`.
- La contrasena del contenedor vive en `.env`, excluido de Git.
- Los valores incluidos en `.env.example` son exclusivamente de desarrollo local.
- CI utiliza credenciales efimeras sin acceso a ningun ambiente externo.
