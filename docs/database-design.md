# Diseno de PostgreSQL e importacion

Estado: aprobado para el segundo incremento de la Fase 1.

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

## Limite transaccional

La reserva del hash, la comprobacion de conflictos, la insercion de clientes y la
actualizacion de contadores ocurren dentro de la misma transaccion. Cualquier conflicto o
error de PostgreSQL produce rollback; no existe un estado parcialmente importado.

## Migraciones

Alembic administra la revision `0001_customer_imports`. El importador comprueba que la
base se encuentre exactamente en esa revision y devuelve `migration_required` sin escribir
si falta. Las migraciones se ejecutan como una operacion separada antes de importar.

## Seguridad local

- PostgreSQL solo publica el puerto en `127.0.0.1`.
- La contrasena del contenedor vive en `.env`, excluido de Git.
- Los valores incluidos en `.env.example` son exclusivamente de desarrollo local.
- CI utiliza credenciales efimeras sin acceso a ningun ambiente externo.
