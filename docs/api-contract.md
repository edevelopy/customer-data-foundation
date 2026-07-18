# Contrato HTTP — Customer Import API

## Resultado de negocio

La API permite que un sistema autorizado entregue un CSV y reciba un resultado verificable
sin acceso directo a PostgreSQL. La primera version es sincrona: la conexion espera hasta que
la validacion y la transaccion terminan. Esto reduce complejidad para el piloto; no es adecuado
todavia para archivos que excedan los limites aprobados o procesos de larga duracion.

Base path versionado: `/v1`. Formato de respuestas: JSON. Carga: `multipart/form-data`.

## Autenticacion y roles

Todos los endpoints `/v1` requieren `Authorization: Bearer <JWT>`. El servicio valida firma,
algoritmo fijo `HS256`, expiracion, emisor, audiencia, sujeto y roles.

| Rol | Enviar importacion | Leer propia | Leer cualquiera |
|---|---:|---:|---:|
| `operator` | Si | Si | No |
| `auditor` | No | No aplica | Si |

Cuando un operador consulta una operacion ajena, recibe `404`; asi no se revela si existe.
El secreto compartido y `fde-dev-token` son exclusivamente para el piloto local. Un entorno
compartido requiere TLS y un proveedor de identidad externo con claves asimetricas rotables.

## `POST /v1/imports`

Requiere rol `operator`, una parte `file` y el header `Idempotency-Key`.

- `file`: CSV UTF-8, maximo 10 MiB y 10,000 filas; contrato en `data-contract.md`.
- `Idempotency-Key`: entre 8 y 200 caracteres imprimibles, creada por el sistema llamador.
- La API no conserva el nombre original del archivo.
- El sujeto y la clave de idempotencia se persisten como HMAC-SHA256 con una clave dedicada,
  separada de la firma JWT; no se guardan como texto original.

La combinacion `(operador, Idempotency-Key)` identifica una solicitud. Repetir la misma clave
con el mismo contenido devuelve exactamente la operacion original. Reutilizarla con contenido
diferente devuelve `409 idempotency_key_reused`.

Respuesta operacional:

```json
{
  "operation_id": "579fda43-f6e4-4f62-bb98-24af7ebf0fee",
  "accepted": true,
  "status": "imported",
  "total_rows": 3,
  "inserted_rows": 3,
  "existing_rows": 0,
  "duration_ms": 42,
  "error_codes": [],
  "issues": []
}
```

Los problemas de validacion pueden indicar fila, campo, codigo y correccion, pero nunca copian
el valor recibido.

## `GET /v1/imports/{operation_id}`

Devuelve el mismo contrato operacional. Un operador solo puede leer sus propias operaciones;
un auditor puede leer cualquiera. No existe endpoint para listar clientes ni operaciones.

## Salud

- `GET /health/live`: confirma que el proceso HTTP responde; no consulta dependencias.
- `GET /health/ready`: confirma PostgreSQL, la revision de migracion y una consulta minima.

Estos endpoints no requieren JWT y no exponen configuracion ni diagnosticos internos.

## Codigos HTTP

| HTTP | Codigo o estado | Significado |
|---:|---|---|
| 200 | `imported`, `already_imported` | Operacion terminada y aceptada |
| 202 | `processing` | La misma solicitud ya esta en curso |
| 400 | `invalid_idempotency_key` | Header ausente o invalido |
| 401 | `invalid_token` | Credencial ausente, invalida o vencida |
| 403 | `forbidden` | Identidad valida sin el rol requerido |
| 404 | `not_found` | Operacion inexistente o no visible |
| 409 | `conflict`, `idempotency_key_reused` | Conflicto de cliente o uso incorrecto de clave |
| 413 | `file_too_large` | Carga superior a 10 MiB |
| 422 | `validation_failed`, `invalid_request` | CSV o estructura HTTP invalida |
| 503 | error operacional | Base, migracion o configuracion no disponible |

## Datos deliberadamente excluidos

Las respuestas y logs operacionales no contienen nombres, emails, telefonos, contenido o
nombre del archivo, token, clave de idempotencia, URL de PostgreSQL ni hashes internos. No se
debe colocar ninguno de esos valores en tickets de soporte.

## Fuera de alcance de este incremento

- Emision de credenciales o login para usuarios reales.
- Procesamiento asincrono, colas y cancelacion.
- Rate limiting, gateway, WAF, TLS y despliegue compartido.
- Recuperacion automatica de una operacion interrumpida mientras estaba `processing`.
- Listado o modificacion de clientes.
