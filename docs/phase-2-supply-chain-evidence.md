# Evidencia de Fase 2 — Incremento 4: cadena de suministro

Fecha: 18 de julio de 2026.

## Alcance aprobado

- Publicacion en GHCR despues de los controles de calidad.
- Etiqueta trazable al commit y consumo contractual por digest.
- Imagen `linux/amd64` y `linux/arm64`.
- Escaneo bloqueante de vulnerabilidades corregibles altas y criticas.
- SBOM SPDX JSON, provenance y attestations firmadas mediante OIDC.
- Verificacion desde un cliente limpio sin reconstruir la imagen.

## Ejecucion final observada

- Commit: `a4c20e6f0296603f1f59f3d4420567111358adc0`.
- Pipeline: <https://github.com/edevelopy/customer-data-foundation/actions/runs/29634438674>.
- Los jobs `image_changes`, `quality`, `container` y `publish` aprobaron.
- Imagen: `ghcr.io/edevelopy/customer-data-foundation-api`.
- Digest: `sha256:0da55830e7958c51fe9caf6a15681f9969fde263028eb9c55044bb03405d59e2`.
- Plataformas observadas: `linux/amd64` y `linux/arm64`.
- SBOM SPDX JSON: 137 paquetes; SHA-256
  `b6094cc7f76e332a35cf46dbd1be9c0ded602b327c6ca6bacfbdc713ecc0b43f`.
- Trivy local y remoto: cero hallazgos bloqueantes `HIGH` o `CRITICAL` con correccion.
- Attestations verificadas: `https://slsa.dev/provenance/v1` y
  `https://spdx.dev/Document/v2.3`.
- Pull anonimo por digest desde configuracion Docker vacia: aprobado.
- Usuario de runtime despues del pull: `10001:10001`.

La prueba anonima tambien confirmo que el paquete heredo visibilidad publica del repositorio. La
politica y la guia de consumo registran esa realidad y el requisito de usar otro nombre o registry
para una entrega privada.

La ejecucion final tambien aprobo dentro del propio job las verificaciones independientes del
workflow firmante y de cada tipo de predicado. El Incremento 4 queda cerrado con artefacto,
manifiesto, SBOM, attestations, escaneo local y remoto, y consumo externo observado.

## Limites

Este incremento entrega un artefacto verificable; no despliega la API en una plataforma cloud.
Tampoco constituye la evaluacion final de la Fase 2.
