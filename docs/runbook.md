# Runbook del importador de clientes

## Objetivo

Diagnosticar y recuperar el importador sin inspeccionar datos personales ni modificar
manualmente tablas. Este runbook asume datos sinteticos o autorizados y una copia del
reporte JSON asociado al `operation_id`.

## Comprobacion inicial

1. Identificar `operation_id`, `status`, `duration_ms` y `error_codes` en el evento JSON.
2. Confirmar que el repositorio esta en la revision desplegada y que CI estaba verde.
3. Ejecutar `fde-diagnose` para separar un fallo del entorno de uno del archivo.
4. No pedir al usuario que envie emails, telefonos, contrasenas ni el archivo por logs.

## Matriz de respuesta

### `validation_failed`

- Causa probable: encabezado, campo requerido, formato, duplicado o limite del archivo.
- Accion: entregar el reporte al propietario del archivo y corregir las filas indicadas.
- Verificacion: ejecutar primero `fde-validate`; no consultar PostgreSQL.
- Recuperacion: reenviar el lote corregido. El intento invalido no modifico la base.

### `conflict`

- Causa probable: el email ya existe con nombre, telefono u origen diferente.
- Accion: el propietario de negocio decide si el registro existente o el nuevo es correcto.
- Verificacion: usar numero de fila y codigo; consultar datos solo mediante un canal autorizado.
- Recuperacion: corregir el CSV. No actualizar directamente la tabla durante el incidente.

### `already_imported`

- No es un incidente. Confirma que la proteccion de idempotencia funciono.
- No volver a insertar ni borrar el historial para forzar otra ejecucion.

### `configuration_error`

- Causa probable: `DATABASE_URL` no esta disponible para el proceso.
- Accion: comprobar que `.env` existe localmente y que se cargo en el entorno.
- Seguridad: nunca imprimir ni copiar la URL completa en tickets o logs.

### `migration_required`

- Causa probable: base nueva o revision de esquema diferente a la aplicacion.
- Accion: revisar el historial de migraciones y ejecutar `alembic upgrade head`.
- Verificacion: confirmar la revision antes de reintentar el lote.
- Prohibido: crear columnas manualmente o marcar una revision sin ejecutar su cambio.

### `database_error`

- Causa probable: contenedor detenido, puerto incorrecto, credenciales locales desalineadas,
  red interrumpida o restriccion de PostgreSQL.
- Accion: comprobar salud del servicio y revisar logs del contenedor buscando codigos y
  tiempos, sin copiar parametros SQL.
- Recuperacion: restaurar PostgreSQL y repetir el mismo archivo. La transaccion fallida no
  debe dejar un lote parcial.
- Escalamiento: si se repite tras recuperar salud, conservar `operation_id`, estado del
  servicio, revision y hora; no adjuntar datos del cliente.

### Puerto local ocupado

- Identificar el proceso o contenedor propietario del puerto.
- No detener un proyecto ajeno. Elegir un puerto libre y mantener sincronizados
  `POSTGRES_PORT` y `DATABASE_URL`.
- Confirmar que el puerto solo se publique en `127.0.0.1`.

## Rollback

- Importacion: PostgreSQL revierte automaticamente ante conflicto o error. Repetir el mismo
  archivo es la primera accion segura despues de recuperar el servicio.
- Migracion en desarrollo desechable: `alembic downgrade base` elimina el esquema completo.
- Migracion con datos que deban conservarse: no ejecutar downgrade destructivo. Crear una
  migracion correctiva, respaldar y ensayar la recuperacion en una copia.

## Simulacro de incidente

1. Ejecutar una importacion valida y conservar solo su evento seguro.
2. Repetirla y comprobar `already_imported`.
3. Ejecutar `customers-conflict.csv` y comprobar `conflict`.
4. Confirmar que el cliente nuevo del lote conflictivo no existe.
5. Intentar una conexion a un puerto cerrado y comprobar `database_error` sin secretos.
6. En una base desechable, ejecutar downgrade, observar `migration_required`, aplicar
   upgrade y repetir la importacion con exito.

## Cierre del incidente

Registrar causa, impacto, deteccion, recuperacion, evidencia y accion preventiva. Cerrar
solo cuando la importacion o reimportacion sea idempotente y las pruebas vuelvan a pasar.

