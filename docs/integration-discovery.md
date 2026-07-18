# Descubrimiento de la integracion empresarial

## Problema del cliente

Despues de aceptar una importacion, operaciones necesita avisar a un sistema socio. Hacer esa
llamada dentro de la solicitud HTTP mezcla dos disponibilidades: si el socio esta lento o caido,
el usuario podria recibir un error aunque PostgreSQL ya confirmo los clientes. Reintentar a ciegas
crearia resultados ambiguos y soporte no podria explicar que ocurrio.

## Personas y responsabilidades

- Operador: entrega el CSV y necesita saber si la importacion fue aceptada.
- Sistema socio: recibe una notificacion tecnica por cada operacion aceptada.
- Soporte: diagnostica con `operation_id`, `event_id`, estado e intento, nunca con PII.
- Seguridad: controla el secreto HMAC, la ventana de replay y los campos autorizados.
- Propietario de negocio: decide si una futura integracion puede compartir datos de clientes.

## Flujo actual y deseado

```text
Antes: operador -> API -> PostgreSQL

Ahora: operador -> API -> PostgreSQL + outbox
                              |
                           worker -> API socia
```

La respuesta de importacion depende solo de la validacion y PostgreSQL. La entrega externa ocurre
despues, conserva su propio presupuesto de reintentos y puede diagnosticarse por separado.

## Limite de datos aprobado

El evento contiene identificadores tecnicos, estado y conteos. No contiene nombres, emails,
telefonos, filas del CSV, JWT, clave de idempotencia ni configuracion. Sin un acuerdo de campos,
base legal, retencion y borrado, este incremento no replica PII al socio.

Esta es una decision deliberada de descubrimiento: primero se prueba la confiabilidad del canal;
el contrato de datos del cliente se aprueba antes de ampliar el payload.

## Resultado y metricas

- La importacion aceptada crea exactamente un evento durable en la misma transaccion que su
  resultado HTTP.
- Una indisponibilidad temporal del socio no cambia la importacion confirmada.
- El socio procesa el mismo `event_id` una sola vez aunque lo reciba varias veces.
- Un evento normal se entrega en menos de 30 segundos durante el piloto.
- Tras cinco intentos fallidos pasa a `dead_letter` y exige intervencion; no reintenta para siempre.
- Soporte puede distinguir `pending`, `delivering`, `delivered` y `dead_letter` sin consultar PII.

## Fuera de alcance

- Replicacion de perfiles de clientes o endpoint para leer PII.
- Broker administrado, despliegue multi-region o garantia de orden global.
- Portal para reprocesar dead letters; durante el piloto exige una accion operacional controlada.
- Rotacion con dos secretos simultaneos, mTLS, gateway y rate limiting del entorno compartido.
