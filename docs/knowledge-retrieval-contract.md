# Contrato de recuperacion empresarial

## Resultado

La base de conocimiento acepta documentos versionados, los divide en fragmentos acotados y permite
recuperarlos mediante busqueda lexical, vectorial o hibrida. La autorizacion se aplica dentro de la
consulta SQL: un resultado no se recupera y luego se oculta; nunca sale de PostgreSQL si el sujeto no
tiene permiso explicito.

## Frontera HTTP

- `POST /v1/knowledge/documents`: requiere rol `operator`; crea una nueva version solo cuando cambia
  el contenido y reemplaza los permisos explicitos del documento.
- `POST /v1/knowledge/retrieval`: requiere JWT; combina el sujeto autenticado, un filtro opcional de
  metadata y el modo `lexical`, `semantic` o `hybrid`.
- El cliente no puede declarar otro sujeto para ampliar su acceso.
- Un documento sin permiso para el sujeto produce cero resultados, no un error que revele su
  existencia.

## Persistencia y busqueda

- PostgreSQL usa la extension `vector` de pgvector.
- Los embeddings tienen 256 dimensiones. Este valor esta fijado por migracion y configuracion para
  impedir mezclar vectores incompatibles silenciosamente.
- La recuperacion lexical usa `tsvector` con indice GIN.
- La recuperacion semantica usa distancia coseno e indice HNSW.
- La recuperacion hibrida combina ambos rankings con Reciprocal Rank Fusion (RRF), sin comparar
  directamente escalas incompatibles.
- Cada fragmento conserva URI, titulo, metadata, numero de version y hash del documento para poder
  construir citas verificables.

## Proveedores de embeddings

`deterministic_local` genera vectores reproducibles mediante hashing normalizado. Solo existe para
desarrollo, pruebas y evaluacion repetible; **no es inteligencia artificial ni demuestra calidad
semantica de OpenAI**.

`openai` usa `text-embedding-3-small`, solicita explicitamente 256 dimensiones y exige una clave
mediante `OPENAI_API_KEY` o `OPENAI_API_KEY_FILE`. Produccion rechaza el proveedor local y usa OpenAI
por defecto.

La reduccion de dimensiones esta soportada por los modelos `text-embedding-3`; la recuperacion usa
similitud coseno, de acuerdo con la documentacion oficial:

- <https://developers.openai.com/api/docs/guides/embeddings>
- <https://developers.openai.com/api/reference/resources/embeddings/methods/create>

## Seguridad y privacidad

- Los permisos se representan en una tabla dedicada y se unen por el hash irreversible del sujeto.
- Los documentos se consideran datos no confiables. Los indicadores de prompt injection se anotan
  como metadata para las defensas del RAG; no se ejecutan ni se interpretan durante la ingesta.
- La API no devuelve claves, configuracion de base de datos ni contenido de documentos no
  autorizados.
- La idempotencia se define por `external_id` y SHA-256 del contenido. Una edicion crea una version
  nueva y desactiva la anterior.

## Limites

- Los permisos son explicitos por sujeto; grupos y sincronizacion con un proveedor de identidad no
  pertenecen a este incremento.
- El proveedor determinista solo prueba contratos y aislamiento. Una evaluacion semantica real
  requiere embeddings de OpenAI y un conjunto representativo del cliente.
- Retencion, borrado legal y clasificacion automatica de documentos dependen de politicas del
  cliente y no se inventan en esta plantilla.
