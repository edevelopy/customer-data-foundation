# FDE Customer Data Foundation

Repositorio plantilla de la **Fase 0** de la ruta Forward Deployed Engineer. Prepara un
entorno Python reproducible para el futuro importador confiable de datos de clientes.

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
uv run fde-import examples/customers-valid.csv --report validation-report.json
```

Repetir el ultimo comando devuelve `status=already_imported` sin crear duplicados. Un
cliente existente con datos diferentes genera `status=conflict` y revierte todo el lote.
El modelo y el limite transaccional estan documentados en
[`docs/database-design.md`](docs/database-design.md).

Existe un lote reproducible para demostrar el conflicto:

```bash
uv run fde-import examples/customers-conflict.csv --report validation-report.json
```

Para detener PostgreSQL sin borrar los datos:

```bash
docker compose down
```

## Calidad y pruebas

```bash
uv run ruff format --check .
uv run ruff check .
TEST_DATABASE_URL="$DATABASE_URL" uv run pytest
```

GitHub Actions ejecuta esas mismas comprobaciones en cada `push` y pull request.

## Estructura

```text
.
├── .github/workflows/ci.yml   # Integracion continua
├── docs/problem-brief.md      # Problema, usuario y metrica
├── examples/                  # CSV validos e invalidos
├── src/fde_foundation/        # Codigo Python instalable
├── tests/                     # Pruebas automatizadas
├── compose.yaml               # PostgreSQL local reproducible
├── .env.example               # Contrato de configuracion sin secretos
├── .gitignore                 # Proteccion de archivos locales
├── pyproject.toml             # Proyecto, dependencias y herramientas
└── uv.lock                    # Versiones exactas, generado por uv
```

## Arquitectura de esta fase

El ejecutable `fde-diagnose` llama comprobaciones independientes y produce una salida
humana o JSON. No lee ni muestra el contenido de `.env`; solo verifica que Git lo ignore.
La validacion ocurre antes de conectar con PostgreSQL. La reserva del hash del archivo,
la deteccion de conflictos y las inserciones comparten una unica transaccion.

## Modelo de trabajo AI-native

La persona responsable actua como FDE: define el problema, toma decisiones de alcance,
aprueba cambios externos y evalua evidencia. El agente ejecuta los comandos y propone o
implementa cambios. Ningun resultado se acepta sin pruebas observadas, riesgos visibles y
un artefacto que otra persona pueda inspeccionar.

## Limitaciones conocidas

- La creacion de tablas es un esquema inicial; todavia no existe una herramienta formal de migraciones.
- El email sigue siendo una clave natural provisional para el piloto.
- El chequeo DNS utiliza `example.com` y puede advertir si se trabaja sin conexion.
