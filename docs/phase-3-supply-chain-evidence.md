# Evidencia de Fase 3 — Seguridad y cadena de suministro

Fecha: 18 de julio de 2026.

## Artefacto aprobado

- Commit: `78475a8c9b34ae8ba1ef5b4c85edb1ddcc6beb62`.
- CI: [run 29640444907](https://github.com/edevelopy/customer-data-foundation/actions/runs/29640444907), aprobada.
- Release: [v0.3.1](https://github.com/edevelopy/customer-data-foundation/releases/tag/v0.3.1).
- Digest: `sha256:e4facaf18a44214aa7ab9f8ad81976ad56198ca2ed5b0a440695ac666a7a2b53`.
- SBOM SPDX SHA-256: `73ef5bc10c2c615dfd3466c93e4cc77d926caefc0eafca2272747e579ee309fa`.
- El pipeline escaneo el digest publicado y verifico provenance SLSA y attestation SPDX.
- Una verificacion posterior del consumidor encontro una attestation SLSA valida y una SPDX valida
  para el mismo digest y workflow firmante.

## Simulacro de dependencia vulnerable

Fuera del repositorio se creo un `requirements.txt` temporal con `urllib3==1.24.1` y
`jinja2==2.10`. Trivy `0.72.0`, ejecutado desde la imagen fijada
`sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f`, detecto siete
vulnerabilidades HIGH corregibles y devolvio codigo `1`, exactamente el comportamiento bloqueante
del pipeline. El fixture no se confirmo ni se incorporo al lock.

## Proteccion del repositorio

GitHub tiene secret scanning y push protection activos. `main` exige pull request, historial lineal,
conversaciones resueltas y checks estrictos `quality` y `container`, incluso para administradores;
force-push y borrado estan deshabilitados.

La [PR #1](https://github.com/edevelopy/customer-data-foundation/pull/1) introdujo un error de tipos
deliberado en una rama temporal. `quality` fallo, `container` aprobo, `publish` se omitio y GitHub
reporto `mergeStateStatus=BLOCKED`. La PR se cerro sin merge y la rama remota se elimino.

## Limites

Dependabot security updates permanece deshabilitado; el control actual descubre vulnerabilidades
en cada cambio de imagen, pero no crea automaticamente una PR entre cambios. Un cliente debe definir
cadencia de actualizacion, SLA de remediacion y excepciones documentadas. La imagen es publica; un
cliente que requiera distribucion privada debe usar su registry y permisos.
