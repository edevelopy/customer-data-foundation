# Contrato de despliegue, release y rollback

## Unidad de entrega

Una release es la combinacion inmutable de:

- version SemVer `vMAJOR.MINOR.PATCH`;
- imagen GHCR fijada por `sha256`, nunca `main`;
- revision de esquema esperada;
- evidencia de CI, SBOM, provenance y escaneo;
- estado de despliegue sin secretos.

El tag Git `vMAJOR.MINOR.PATCH` activa `release.yml`. El workflow exige que el tag corresponda a la
version de `pyproject.toml`, que el commit pertenezca a `main` y que sus checks `quality` y
`container` hayan aprobado. No reconstruye: promueve el tag `sha-<commit>` ya probado al tag SemVer,
verifica las attestations existentes y publica `release-manifest.json` como asset de GitHub Release.

`deploy/compose.release.yaml` no contiene `build:` ni tags mutables. PostgreSQL tambien esta fijado
por digest. La unica entrada publica del piloto es la API en `127.0.0.1`; la red de backend es
interna y conserva un volumen nombrado.

## Orden y comando

Con secretos ya materializados por el entorno, una release se ejecuta con un comando:

```bash
uv run fde-release deploy \
  --version v0.3.0 \
  --image-ref ghcr.io/edevelopy/customer-data-foundation-api@sha256:<digest> \
  --secrets-dir /ruta/absoluta/secrets \
  --state-file /ruta/absoluta/state/release.json
```

El controlador valida identidad, permisos de archivos y Compose; descarga el digest; ejecuta
preflight, PostgreSQL, migracion, API, partner y worker; espera health; y corre un smoke externo con
fallo parcial. Solo entonces reemplaza atomicamente el estado.

Para un simulacro local se pueden crear valores descartables con `fde-release-fixture`. Ese comando
no es un gestor de secretos y esta prohibido para credenciales de cliente.

## Rollback

```bash
uv run fde-release rollback \
  --secrets-dir /ruta/absoluta/secrets \
  --state-file /ruta/absoluta/state/release.json
```

Rollback usa la imagen previa por digest, repite preflight, migracion compatible, health y smoke, y
solo entonces actualiza el estado. Se rechaza automaticamente cuando las revisiones de esquema
difieren. Las migraciones deben seguir expand/contract; nunca se ejecuta `alembic downgrade` sobre
datos del ambiente para recuperar codigo.

## Fallo seguro

Un pull, preflight, migracion, health o smoke fallido conserva el ultimo estado aprobado. Los
contenedores fallidos permanecen disponibles para logs hasta una accion operacional controlada,
pero no se afirma que el release este activo. El estado no contiene tokens, passwords, URLs ni
rutas de secretos.

## Limites

Este ambiente Docker prueba el procedimiento y el artefacto sin afirmar alta disponibilidad ni
cloud. Un despliegue compartido debe trasladar el mismo contrato a un servicio administrado,
mantener backups externos y controlar concurrencia para que solo un release opere por ambiente.
