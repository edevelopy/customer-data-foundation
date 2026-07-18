# Evidencia de Fase 2 — Incremento 4: cadena de suministro

Fecha: 18 de julio de 2026.

## Alcance aprobado

- Publicacion en GHCR despues de los controles de calidad.
- Etiqueta trazable al commit y consumo contractual por digest.
- Imagen `linux/amd64` y `linux/arm64`.
- Escaneo bloqueante de vulnerabilidades corregibles altas y criticas.
- SBOM SPDX JSON, provenance y attestations firmadas mediante OIDC.
- Verificacion desde un cliente limpio sin reconstruir la imagen.

## Primera ejecucion observada

- Commit: `7a20281b256316e74db124fc1a86e1bd2ef122d8`.
- Pipeline: <https://github.com/edevelopy/customer-data-foundation/actions/runs/29634151278>.
- Los jobs `quality`, `container` y `publish` aprobaron.
- Imagen: `ghcr.io/edevelopy/customer-data-foundation-api`.
- Digest: `sha256:dc24fa5273c3f3a1cdce048bf97fb959f32e63954ee6bc419aaa5fdb9a45515c`.
- Plataformas observadas: `linux/amd64` y `linux/arm64`.
- SBOM SPDX JSON: 137 paquetes; SHA-256
  `73bc0a43fbd0fa1386b4c236b1e7973db3574ca40e06c5f601aa630ae47e6d5e`.
- Trivy local y remoto: cero hallazgos bloqueantes `HIGH` o `CRITICAL` con correccion.
- Attestations verificadas: `https://slsa.dev/provenance/v1` y
  `https://spdx.dev/Document/v2.3`.
- Pull anonimo por digest desde configuracion Docker vacia: aprobado.
- Usuario de runtime despues del pull: `10001:10001`.

La prueba anonima tambien confirmo que el paquete heredo visibilidad publica del repositorio. La
politica y la guia de consumo registran esa realidad y el requisito de usar otro nombre o registry
para una entrega privada.

## Limites

Este incremento entrega un artefacto verificable; no despliega la API en una plataforma cloud.
Tampoco constituye la evaluacion final de la Fase 2.
