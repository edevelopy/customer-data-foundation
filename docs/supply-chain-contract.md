# Contrato de cadena de suministro

## Objetivo empresarial

Entregar al cliente una imagen cuya procedencia, contenido y resultado de seguridad puedan
comprobarse sin confiar solamente en el nombre de una etiqueta. El artefacto contractual es el
digest `sha256`, no la etiqueta mutable `main`.

## Flujo autorizado

La publicacion ocurre solamente en un `push` a `main` y despues de que los jobs `quality` y
`container` aprueban. Un pull request construye, prueba y escanea, pero no obtiene permiso para
publicar paquetes ni attestations.

El destino es:

```text
ghcr.io/edevelopy/customer-data-foundation-api
```

Cada publicacion crea:

- `sha-<commit completo>`: etiqueta trazable al commit;
- `main`: conveniencia para descubrir la version mas reciente;
- `sha256:<digest>`: identidad inmutable que debe usarse en despliegues y entregas.

La primera publicacion en GHCR conserva la visibilidad privada predeterminada. Hacer el paquete
publico es una decision de distribucion separada, no un efecto secundario del pipeline.

## Construccion y evidencia

- Imagen multi-plataforma para `linux/amd64` y `linux/arm64`.
- Python, uv y todas las GitHub Actions fijadas por digest o commit completo.
- Etiquetas OCI enlazan el artefacto con este repositorio.
- BuildKit incorpora SBOM y provenance al indice OCI.
- Syft genera un SBOM descargable en formato SPDX JSON.
- GitHub firma attestations de provenance y SBOM mediante OIDC; no existe una clave privada de
  firma almacenada en el repositorio.
- El workflow verifica sus propias attestations antes de declararse correcto.

El artefacto de CI `supply-chain-<commit>` contiene `sbom.spdx.json` y
`supply-chain-manifest.json`. El manifiesto relaciona commit, imagen, digest y SHA-256 del SBOM.

## Politica de vulnerabilidades

Trivy examina paquetes del sistema y librerias de aplicacion en dos puntos:

1. la imagen local antes de ejecutar el stack;
2. el digest publicado en GHCR.

El pipeline se bloquea ante vulnerabilidades `HIGH` o `CRITICAL` que ya tienen correccion
disponible. Los hallazgos sin correccion no se ocultan: `ignore-unfixed` evita bloquear una
entrega que el equipo no puede remediar, pero deben revisarse al actualizar las bases.

Una excepcion futura exige un identificador de riesgo, propietario, justificacion, fecha de
expiracion y alcance exacto. No se acepta una lista de exclusiones indefinida.

## Permisos y limites de confianza

El workflow general solo tiene lectura. El job `publish` recibe de forma temporal:

- escritura de paquetes;
- emision OIDC;
- escritura de attestations y metadatos de artefactos.

El `GITHUB_TOKEN` pertenece a la ejecucion y no se guarda en la imagen, SBOM ni artifacts. Todas
las acciones externas estan fijadas a commits de 40 caracteres para evitar que una etiqueta
cambie el codigo ejecutado.

Este contrato prueba la identidad y procedencia del artefacto. No sustituye TLS, un gestor de
secretos, politicas de admision, backups ni controles propios de la plataforma de despliegue.

## Criterios de aceptacion

- Las pruebas, el contenedor y ambos escaneos aprueban.
- GHCR devuelve un digest multi-plataforma.
- La configuracion descargada por digest mantiene `USER 10001:10001`.
- Existen attestations verificables de provenance y SBOM para ese mismo digest.
- Un cliente limpio puede autenticarse, descargar por digest y verificar la procedencia sin
  reconstruir el repositorio.
