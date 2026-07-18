# Contrato operacional del contenedor

## Objetivo

Ejecutar la API y sus migraciones con el mismo artefacto reproducible, sin otorgar a la API la
responsabilidad de modificar el esquema durante su arranque normal.

## Imagen

- Python `3.12.13-slim-bookworm` y uv `0.11.29` estan fijados por tag y digest SHA-256.
- `uv sync --locked --no-editable` instala solo dependencias de ejecucion desde `uv.lock`.
- La etapa final no contiene uv, el repositorio completo, pruebas, ejemplos ni `.env`.
- El proceso y sus archivos pertenecen a `10001:10001`; `USER 10001:10001` es el valor por
  defecto de la imagen.
- El health check consulta `/health/ready`, no una respuesta HTTP superficial.
- `STOPSIGNAL SIGTERM` permite a Uvicorn terminar solicitudes y conexiones ordenadamente.

Actualizar una imagen base o uv requiere cambiar explicitamente el digest, reconstruir, correr
la suite y repetir el smoke test.

## Orden de arranque

```text
PostgreSQL healthy -> api_migrate exit 0 -> API + partner healthy -> worker healthy -> smoke
```

`api_migrate` ejecuta `alembic upgrade head` como trabajo de una sola vez. Si termina con un
codigo distinto de cero, Compose crea pero no inicia la API. La API valida nuevamente la
revision mediante readiness y antes de cualquier operacion.

Desarrollo usa la misma cuenta local para aplicacion y migracion. Un entorno compartido debe
proporcionar credenciales distintas: el migrador puede cambiar esquema; la API solo debe leer
y escribir las tablas autorizadas.

## Endurecimiento de ejecucion

Los servicios API, migracion, partner, worker y smoke client usan:

- filesystem raiz de solo lectura;
- `/tmp` en memoria, con tamano limitado y sin ejecucion de binarios;
- todas las capacidades Linux eliminadas;
- `no-new-privileges`;
- limites de procesos, memoria y CPU para todos los procesos persistentes y clientes smoke;
- puerto HTTP publicado solamente en `127.0.0.1` durante el piloto.

La API y el worker reciben 15 segundos para cerrar despues de `SIGTERM`. El worker anuncia
readiness mediante una marca efimera en `/tmp` despues de validar su configuracion; no abre un
puerto solo para salud.

## Configuracion y secretos

`.dockerignore` excluye `.env`, Git, entornos virtuales, reportes y artefactos locales. Ningun
secreto se acepta como argumento de construccion ni se incorpora a la imagen.

Compose inyecta configuracion durante la ejecucion para el piloto local. Los administradores
del host pueden inspeccionar variables de un contenedor; por eso un entorno compartido debe
usar el gestor de secretos e identidad de su plataforma. Los tokens y claves nunca se imprimen
en el smoke test ni en logs.

## Verificacion requerida

- Docker build check sin advertencias.
- Imagen ejecutada con UID/GID `10001`.
- Root filesystem de solo lectura y `cap_drop=[ALL]` observados mediante inspect.
- Migracion correcta antes de readiness.
- Migracion fallida bloquea el arranque.
- Importacion real desde otro contenedor, sin PII en la respuesta.
- Fallo `503` del partner, backoff y entrega en el segundo intento desde otro contenedor.
- `SIGTERM` termina con codigo `0` dentro del periodo de gracia.
- Suite Python, clon limpio y los dos jobs de CI en verde.

## Integridad de la entrega

La publicacion, el digest, el SBOM, las attestations y el escaneo continuo se definen en
[`supply-chain-contract.md`](supply-chain-contract.md). Este contrato continua siendo responsable
de la construccion y ejecucion del contenedor; el contrato de cadena de suministro gobierna su
identidad y entrega.

## Fuera de alcance

- TLS, gateway, rate limiting y despliegue en una plataforma cloud.
- Backups, restauracion y alta disponibilidad de PostgreSQL.
