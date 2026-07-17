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
git clone <URL_DEL_REPOSITORIO>
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
cuando existe un fallo obligatorio. Docker y la resolucion DNS se reportan de forma
informativa y no bloquean el trabajo local.

## Calidad y pruebas

```bash
uv run ruff check .
uv run pytest
```

GitHub Actions ejecuta esas mismas comprobaciones en cada `push` y pull request.

## Estructura

```text
.
├── .github/workflows/ci.yml   # Integracion continua
├── docs/problem-brief.md      # Problema, usuario y metrica
├── src/fde_foundation/        # Codigo Python instalable
├── tests/                     # Pruebas automatizadas
├── .env.example               # Contrato de configuracion sin secretos
├── .gitignore                 # Proteccion de archivos locales
├── pyproject.toml             # Proyecto, dependencias y herramientas
└── uv.lock                    # Versiones exactas, generado por uv
```

## Arquitectura de esta fase

El ejecutable `fde-diagnose` llama comprobaciones independientes y produce una salida
humana o JSON. No lee ni muestra el contenido de `.env`; solo verifica que Git lo ignore.
La aplicacion de importacion y PostgreSQL se incorporaran en fases posteriores.

## Limitaciones conocidas

- Todavia no se procesan archivos CSV.
- Todavia no existe una base de datos.
- El chequeo DNS utiliza `example.com` y puede advertir si se trabaja sin conexion.
- La URL real del repositorio se agregara al publicarlo en GitHub.

