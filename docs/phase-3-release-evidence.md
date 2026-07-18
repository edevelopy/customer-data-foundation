# Evidencia de Fase 3 — Incremento 3: despliegue y release

Fecha: 18 de julio de 2026.

## Problema y criterios de aceptacion

Una etiqueta mutable y un comando Compose manual no son una release. El ambiente necesita una
identidad inmutable, orden de migracion, secretos montados, smoke posterior y estado que solo avance
cuando la nueva version este saludable.

El incremento se acepta cuando:

- el stack de release usa solo imagenes por digest y ninguna construccion local;
- preflight y migracion terminan antes de API, partner y worker;
- siete valores sensibles se montan como archivos privados a partir de `v0.3.1`;
- un comando ejecuta pull, deploy, health y smoke de fallo parcial;
- el estado se escribe atomicamente solo despues del smoke;
- rollback solo acepta una release previa con la misma revision de esquema;
- un tag SemVer promueve el digest ya probado y publica un manifiesto, sin reconstruirlo.

## Evidencia automatizada local

- Version del proyecto elevada a `0.3.0` para la primera release formal.
- Compose de release validado con seis secretos efimeros modo `0600`.
- PostgreSQL y la imagen de aplicacion estan fijados por digest.
- 68 pruebas aprobaron; las pruebas del controlador observaron el orden
  `config -> pull -> up -> smoke -> estado`.
- Un smoke simulado fallido conservo exactamente el estado anterior.
- Ruff, Mypy (34 archivos), Actionlint y coverage 76.45% aprobaron.
- `docker build --check` no termino en esta repeticion por una espera de red al resolver el
  frontend ya fijado; se cancelo sin modificar imagen o estado. CI repetira el build en Linux.

## Evidencia remota y despliegue real

- Commit `122b1b7c495f27eeda46b86c92ed0b67c23c0692`: CI `29639781970` aprobada.
- Digest publicado: `sha256:cb20697d7e4f02c5f8f6c273176776c144200fb5f0fa0bfe5bb503dfd91574ed`.
- Release `v0.3.0`: workflow `29639890975` aprobado y manifiesto publicado como asset.
- El despliegue real creo PostgreSQL, preflight, migracion, API, partner y worker saludables. El
  smoke recibio un `503`, reintento y termino `delivered` con `attempt_count=2`.
- Los procesos se observaron como UID `10001:10001`, rootfs read-only, `cap_drop=ALL` y
  `no-new-privileges`; las variables sensibles solo contenian rutas `_FILE`.

El simulacro encontro que el puerto host no se activo en Docker Desktop con una unica red interna.
La correccion pertenece a `v0.3.1`; su release, despliegue y rollback real siguen siendo criterios de
cierre y no se sustituyen con la prueba unitaria.
