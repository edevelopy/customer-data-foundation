# FDE Customer Data Foundation

Proyecto progresivo de la ruta **Forward Deployed Engineer**. La Fase 0 preparo el entorno,
la Fase 1 entrego el importador transaccional, la Fase 2 lo expuso como una API autenticada e
integrada, y la Fase 3 entrega release, rollback, metricas, backups y automatizacion reproducible.
La Fase 4 entrega un asistente empresarial cuya recuperacion, respuestas y acciones se pueden medir.
Incluye una frontera LLM estructurada, conocimiento con permisos y pgvector, RAG con citas, 38 casos
de evaluacion y una accion simulada que exige aprobacion humana separada.

El problema, el usuario y la metrica inicial estan documentados en
[`docs/problem-brief.md`](docs/problem-brief.md).

## Requisitos

- Git.
- Python 3.12 o superior.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- Docker es opcional durante la Fase 0 y sera necesario al introducir PostgreSQL.

## Instalacion desde cero

```bash
git clone https://github.com/edevelopy/customer-data-foundation.git
cd customer-data-foundation
uv sync --locked
cp .env.example .env
```

No escribas secretos en `.env.example` ni confirmes el archivo `.env` en Git.

## Ejecutar el diagnostico

```bash
uv run fde-diagnose
```

Para integrar el resultado con otra herramienta:

```bash
uv run fde-diagnose --json
```

El comando devuelve codigo `0` cuando las comprobaciones obligatorias pasan y codigo `1`
cuando existe un fallo obligatorio. Docker, DNS, TLS y el puerto local 8000 se reportan
de forma informativa y no bloquean el trabajo local.

## Validar un CSV de clientes

El contrato completo esta en [`docs/data-contract.md`](docs/data-contract.md). El modo
estricto rechaza el lote completo si encuentra al menos un error.

```bash
uv run fde-validate examples/customers-valid.csv --report validation-report.json
uv run fde-validate examples/customers-invalid.csv --report validation-report.json
```

El primer comando devuelve codigo `0`. El segundo devuelve codigo `1` y escribe un reporte
sin copiar emails, telefonos ni otros valores recibidos.

## Importar en PostgreSQL

PostgreSQL se ejecuta localmente mediante Docker Compose y solo publica su puerto en
`127.0.0.1`.

```bash
cp .env.example .env
docker compose up -d --wait database
set -a
source .env
set +a
uv run alembic upgrade head
uv run fde-import examples/customers-valid.csv --report validation-report.json
```

Repetir el ultimo comando devuelve `status=already_imported` sin crear duplicados. Un
cliente existente con datos diferentes genera `status=conflict` y revierte todo el lote.
El modelo y el limite transaccional estan documentados en
[`docs/database-design.md`](docs/database-design.md).

Cada importacion emite una sola linea JSON con identificador de operacion, estado,
duracion, conteos y codigos de error. No incluye nombres, emails, telefonos, rutas,
contenido del archivo ni configuracion de la base de datos.

Existe un lote reproducible para demostrar el conflicto:

```bash
uv run fde-import examples/customers-conflict.csv --report validation-report.json
```

Para detener PostgreSQL sin borrar los datos:

```bash
docker compose down
```

## Ejecutar la API local

El contrato narrado esta en [`docs/api-contract.md`](docs/api-contract.md) y la especificacion
maquina-legible versionada en [`docs/openapi.json`](docs/openapi.json). Despues de cargar `.env`,
iniciar PostgreSQL y aplicar migraciones:

```bash
uv run fde-api
```

La documentacion interactiva local queda en `http://127.0.0.1:8000/docs`. Para una demo se
puede generar un JWT de 15 minutos; el comando se bloquea fuera de `APP_ENV=development`:

```bash
uv run fde-dev-token --subject operator-demo --role operator
```

No guardes ni copies el token a logs, documentos o Git. Este ayudante no es un login ni debe
usarse en un entorno compartido. El guion reproducible esta en
[`docs/api-demo-script.md`](docs/api-demo-script.md).

## Planificar una consulta con IA

El primer incremento de la Fase 4 añade `POST /v1/assistant/query-plans`. El endpoint no responde la
pregunta: la clasifica de forma estructurada antes de permitir acceso a documentos. Requiere JWT y,
solo al invocarlo, una clave de OpenAI mediante `OPENAI_API_KEY` o `OPENAI_API_KEY_FILE`.

La llamada al proveedor desactiva almacenamiento, separa instrucciones de contenido no confiable y
registra modelo, version de prompt, latencia y tokens sin copiar la pregunta a la traza. El contrato,
fallos seguros y limites estan en [`docs/ai-contract.md`](docs/ai-contract.md).

## Ingerir y recuperar conocimiento autorizado

El segundo incremento añade `POST /v1/knowledge/documents` para operadores y
`POST /v1/knowledge/retrieval` para usuarios autenticados. PostgreSQL aplica permisos por sujeto
antes de devolver resultados y permite busqueda `lexical`, `semantic` o `hybrid`.

Desarrollo y pruebas pueden usar embeddings deterministas para repetir resultados sin costo; ese
adaptador no es IA. Produccion requiere OpenAI. El modelo de datos, seguridad y limites estan en el
[`contrato de recuperacion`](docs/knowledge-retrieval-contract.md), y la validacion observada en la
[`evidencia del Incremento 2`](docs/phase-4-increment-2-evidence.md).

## Responder con evidencia

`POST /v1/assistant/answers` recupera solo fragmentos permitidos, aplica un umbral de evidencia y
verifica que todas las citas generadas pertenezcan a esos fragmentos. Sin soporte devuelve
`status=refused`; una cita inventada nunca se publica.

En desarrollo existe un extractor determinista para probar el flujo sin costo; no es IA. Produccion
usa el adaptador Responses API y requiere OpenAI. Consulta el [`contrato RAG`](docs/rag-contract.md)
y la [`evidencia del Incremento 3`](docs/phase-4-increment-3-evidence.md).

## Evaluar el asistente

`fde-rag-eval` ejecuta 38 casos versionados contra una linea base lexical y el flujo RAG completo.
Mide recall, precision, exactitud, groundedness, rechazo, permisos, latencia, tokens y costo; falla si
una puerta no se cumple.

```bash
APP_ENV=test uv run fde-rag-eval \
  --json-output docs/evals/phase4-results.json \
  --markdown-output docs/evals/phase4-results.md
```

El [`contrato de evaluacion`](docs/evaluation-contract.md) define las formulas y limites. El
[`resultado versionado`](docs/evals/phase4-results.md) usa un adaptador local que no es IA; no
representa calidad ni costo vivo de OpenAI.

## Proponer una accion con aprobacion humana

El ultimo incremento permite que un operador proponga `send_customer_followup`, pero la solicitud
queda `pending`. Un auditor diferente debe aprobar los argumentos exactos antes de que un operador
pueda ejecutar la simulacion. No existe un conector real de correo o CRM.

Los endpoints de propuesta, aprobacion, ejecucion y lectura estan en OpenAPI. El
[`contrato del agente`](docs/controlled-agent-contract.md) explica roles, auditoria, rate limit,
presupuesto, cache y degradacion; la [`evidencia del Incremento 5`](docs/phase-4-increment-5-evidence.md)
registra las pruebas observadas.

La [`evaluacion final de la Fase 4`](docs/phase-4-final-evaluation.md) separa lo demostrado de lo que
todavia requiere un piloto real. El [`guion de demo`](docs/phase-4-demo-script.md) presenta el flujo a
un cliente no tecnico sin ocultar sus limites.

## Ejecutar el stack Docker

La imagen endurecida, la migracion de una sola ejecucion y la API se coordinan con Compose:

```bash
docker compose --profile api up --build -d --wait api
```

El arranque se detiene si PostgreSQL no esta saludable o `alembic upgrade head` falla. La API
se ejecuta sin root, con filesystem de solo lectura, `/tmp` efimero, capacidades eliminadas y
recursos limitados. El contrato esta en
[`docs/container-contract.md`](docs/container-contract.md).

Para detener la API ordenadamente sin borrar PostgreSQL:

```bash
docker compose stop -t 15 api
```

El [guion de demo contenerizada](docs/container-demo-script.md) evita exponer tokens o variables
del contenedor.

## Ejecutar la integracion empresarial

La API confirma la importacion y crea una notificacion durable. Un worker separado la firma y la
entrega a una segunda API simulada sin bloquear al operador:

```bash
docker compose --profile api --profile integration up --build -d --wait \
  api partner_api integration_worker
```

El piloto configura un `503` inicial por evento para probar la recuperacion. El descubrimiento del
problema esta en [`docs/integration-discovery.md`](docs/integration-discovery.md), el contrato en
[`docs/integration-contract.md`](docs/integration-contract.md), la arquitectura y decisiones en
[`docs/integration-architecture.md`](docs/integration-architecture.md), y la demostracion completa
en [`docs/integration-demo-script.md`](docs/integration-demo-script.md).

## Consumir la imagen verificable

Los cambios de imagen aprobados en `main` publican una imagen publica multi-plataforma en GHCR.
Los despliegues deben fijar
`ghcr.io/edevelopy/customer-data-foundation-api@sha256:<digest>`; `:main` solo sirve para descubrir
la entrega mas reciente. El pipeline bloquea vulnerabilidades altas o criticas con correccion,
genera un SBOM SPDX y firma attestations de provenance y SBOM.

El contrato esta en [`docs/supply-chain-contract.md`](docs/supply-chain-contract.md) y los pasos
que ejecuta un cliente estan en [`docs/image-consumer-guide.md`](docs/image-consumer-guide.md).

## Desplegar una release inmutable

El ambiente de release usa una imagen por digest, archivos de secretos, preflight, migracion,
health y smoke antes de actualizar estado:

```bash
uv run fde-release deploy \
  --version v0.4.0 \
  --image-ref ghcr.io/edevelopy/customer-data-foundation-api@sha256:<digest> \
  --secrets-dir /ruta/absoluta/secrets \
  --state-file /ruta/absoluta/state/release.json
```

El contrato y la politica de rollback estan en
[`docs/release-contract.md`](docs/release-contract.md). `fde-release-fixture` existe solo para
simulacros con valores descartables; nunca genera credenciales de un cliente.

## Observar y recuperar el ambiente

La API publica metricas Prometheus autenticadas en `/metrics`; `fde-ops-check` evalua las mismas
señales y devuelve codigo no-cero ante leases vencidos, dead letter o atraso. Los contratos estan en
[`docs/operations-contract.md`](docs/operations-contract.md) y
[`deploy/prometheus-alerts.yml`](deploy/prometheus-alerts.yml).

Los backups se crean y prueban sin restaurar sobre la fuente:

```bash
uv run fde-backup create --project-name cdf-release --archive /ruta/privada/customer-data.dump
uv run fde-backup verify --project-name cdf-release --archive /ruta/privada/customer-data.dump
```

El dump contiene PII y debe cifrarse y almacenarse fuera de Git. Consulta el
[`runbook de backup y restauracion`](docs/backup-restore-runbook.md).

## Calidad y pruebas

```bash
set -a
source .env
set +a
docker compose --profile test up -d --wait database_test
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests scripts
uv run pytest --cov=fde_foundation --cov-branch --cov-report=term-missing
```

Usa la URL de pruebas, nunca `DATABASE_URL`, al ejecutar Pytest. La cobertura total debe permanecer
en 75% o mas. `database_test` utiliza almacenamiento efimero y no comparte volumen con la base de
desarrollo.

GitHub Actions ejecuta esas mismas comprobaciones en cada `push` y pull request.

Si cambia un endpoint o modelo HTTP, regenerar y validar el contrato antes de confirmar:

```bash
uv run python scripts/export_openapi.py
uv run pytest tests/test_openapi_contract.py
```

## Operacion y evaluacion

- [`docs/observability-contract.md`](docs/observability-contract.md): campos y metricas seguras.
- [`docs/runbook.md`](docs/runbook.md): diagnostico, recuperacion y rollback.
- [`docs/failure-drill-evidence.md`](docs/failure-drill-evidence.md): simulacros observados.
- [`docs/demo-script.md`](docs/demo-script.md): demo reproducible de cinco minutos.
- [`docs/phase-1-final-evaluation.md`](docs/phase-1-final-evaluation.md): rubrica y limites.
- [`docs/phase-2-api-evidence.md`](docs/phase-2-api-evidence.md): evidencia incremental del
  contrato HTTP y su recuperacion; no es aun la evaluacion final de la Fase 2.
- [`docs/phase-2-container-evidence.md`](docs/phase-2-container-evidence.md): evidencia de
  construccion, aislamiento, migracion, smoke test y apagado.
- [`docs/phase-2-supply-chain-evidence.md`](docs/phase-2-supply-chain-evidence.md): evidencia de
  publicacion por digest, SBOM, provenance, escaneo y consumo independiente.
- [`docs/phase-2-integration-evidence.md`](docs/phase-2-integration-evidence.md): evidencia de
  outbox, webhook firmado, reintentos, dead letter y fallo parcial recuperado.
- [`docs/phase-2-final-evaluation.md`](docs/phase-2-final-evaluation.md): rubrica, examen desde clon
  limpio, limites y decision formal de aprobacion de la Fase 2.
- [`docs/phase-3-equivalence-audit.md`](docs/phase-3-equivalence-audit.md): cobertura reutilizable y
  brechas reales de entrega y automatizacion.
- [`docs/phase-3-quality-evidence.md`](docs/phase-3-quality-evidence.md): type checking, cobertura
  bloqueante y artifacts de pruebas.
- [`docs/secrets-contract.md`](docs/secrets-contract.md): interfaz `_FILE`, fallo seguro y
  responsabilidades del gestor de secretos.
- [`docs/phase-3-secrets-evidence.md`](docs/phase-3-secrets-evidence.md): preflight, pruebas de
  archivos montados y limites de rotacion.
- [`docs/phase-3-release-evidence.md`](docs/phase-3-release-evidence.md): ambiente por digest,
  promocion SemVer, smoke y estado de deploy/rollback.
- [`docs/phase-3-operations-evidence.md`](docs/phase-3-operations-evidence.md): metricas, alerta
  provocada y restauracion real aislada.
- [`docs/phase-3-clean-clone-evidence.md`](docs/phase-3-clean-clone-evidence.md): instalacion,
  pruebas y deploy por digest desde otro clon.
- [`docs/phase-3-supply-chain-evidence.md`](docs/phase-3-supply-chain-evidence.md): SBOM,
  attestations, dependencia vulnerable y proteccion de `main`.
- [`docs/phase-3-delivery-script.md`](docs/phase-3-delivery-script.md): entrega de 15 minutos para
  una audiencia no tecnica.
- [`docs/phase-3-final-evaluation.md`](docs/phase-3-final-evaluation.md): rubrica, limites y decision
  formal de aprobacion de la Fase 3.
- [`docs/phase-4-plan.md`](docs/phase-4-plan.md): cinco incrementos y puertas de salida para un
  asistente RAG verificable.
- [`docs/ai-contract.md`](docs/ai-contract.md): frontera Responses API, configuracion, seguridad y
  contrato HTTP del planificador.
- [`docs/phase-4-increment-1-evidence.md`](docs/phase-4-increment-1-evidence.md): pruebas, limites y
  decision del primer incremento de IA.

## Estructura

```text
.
├── .github/workflows/ci.yml   # Integracion continua
├── docs/problem-brief.md      # Problema, usuario y metrica
├── examples/                  # CSV validos e invalidos
├── migrations/                # Cambios versionados de PostgreSQL
├── src/fde_foundation/        # Codigo Python instalable
├── tests/                     # Pruebas automatizadas
├── compose.yaml               # PostgreSQL local reproducible
├── Dockerfile                 # Imagen multi-stage no-root
├── .env.example               # Contrato de configuracion sin secretos
├── .gitignore                 # Proteccion de archivos locales
├── pyproject.toml             # Proyecto, dependencias y herramientas
└── uv.lock                    # Versiones exactas, generado por uv
```

## Arquitectura de esta fase

El ejecutable `fde-diagnose` llama comprobaciones independientes y produce una salida
humana o JSON. No lee ni muestra el contenido de `.env`; solo verifica que Git lo ignore.
La validacion ocurre antes de escribir clientes en PostgreSQL. Una migracion explicita prepara
el esquema; la reserva del hash, la deteccion de conflictos y las inserciones usan limites
transaccionales explicitos. La API conserva solo HMAC del actor y de la clave de idempotencia. Un
transactional outbox desacopla el resultado del socio; el worker entrega at-least-once y el receptor
deduplica por `event_id`.

## Modelo de trabajo AI-native

La persona responsable actua como FDE: define el problema, toma decisiones de alcance,
aprueba cambios externos y evalua evidencia. El agente ejecuta los comandos y propone o
implementa cambios. Ningun resultado se acepta sin pruebas observadas, riesgos visibles y
un artefacto que otra persona pueda inspeccionar.

## Limitaciones conocidas

- La primera migracion adopta tablas identicas creadas durante el piloto; cambios futuros deben validarlas explicitamente.
- El email sigue siendo una clave natural provisional para el piloto.
- El chequeo DNS utiliza `example.com` y puede advertir si se trabaja sin conexion.
- La API local usa un secreto compartido; un entorno real requiere identidad externa, TLS,
  rate limiting y reconciliacion en segundo plano cuando ningun llamador reintenta.
- El socio es simulado y comparte PostgreSQL solo durante el piloto; una integracion real necesita
  almacenamiento propio, gestor de secretos y aprobacion del contrato de datos.
- La imagen de portafolio es publica; un cliente que exija distribucion privada necesita otro
  nombre de paquete o su propio registry.
- Las metricas y reglas existen, pero falta un canal de alertas con propietario y SLO del cliente.
- Los backups se restauran localmente, pero faltan cifrado externo, retencion y RPO/RTO acordados.
