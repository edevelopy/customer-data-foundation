# Evidencia de Fase 2 — Incremento 4: cadena de suministro

Fecha: 18 de julio de 2026.

## Alcance aprobado

- Publicacion privada en GHCR despues de los controles de calidad.
- Etiqueta trazable al commit y consumo contractual por digest.
- Imagen `linux/amd64` y `linux/arm64`.
- Escaneo bloqueante de vulnerabilidades corregibles altas y criticas.
- SBOM SPDX JSON, provenance y attestations firmadas mediante OIDC.
- Verificacion desde un cliente limpio sin reconstruir la imagen.

## Evidencia pendiente de ejecucion

Este documento se completa con el digest, pipeline, artifacts y prueba de consumo observados
despues de publicar el primer commit del incremento. El contrato implementado no se declara
cerrado solamente por existir como YAML.

## Limites

Este incremento entrega un artefacto verificable; no despliega la API en una plataforma cloud ni
cambia la visibilidad privada predeterminada de GHCR. Tampoco constituye la evaluacion final de la
Fase 2.
