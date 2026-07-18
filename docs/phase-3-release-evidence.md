# Evidencia de Fase 3 — Incremento 3: despliegue y release

Fecha: 18 de julio de 2026.

## Problema y criterios de aceptacion

Una etiqueta mutable y un comando Compose manual no son una release. El ambiente necesita una
identidad inmutable, orden de migracion, secretos montados, smoke posterior y estado que solo avance
cuando la nueva version este saludable.

El incremento se acepta cuando:

- el stack de release usa solo imagenes por digest y ninguna construccion local;
- preflight y migracion terminan antes de API, partner y worker;
- seis valores sensibles se montan como archivos privados;
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

## Estado pendiente antes del cierre

La implementacion aun debe publicarse, obtener su digest, crear `v0.3.0` y ejecutar el comando de
release contra el artefacto remoto. El rollback real requiere una segunda release compatible y se
cerrara junto al simulacro operativo; las pruebas unitarias no se presentan como sustituto.
