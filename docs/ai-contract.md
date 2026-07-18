# Contrato de IA — Incremento 1 de la Fase 4

## Explicacion para un cliente no tecnico

Antes de permitir que una IA lea documentos empresariales, colocamos una recepcion controlada. Esta
recepcion identifica que pregunta hizo la persona, si necesita buscar evidencia, si contiene datos
sensibles o si intenta alterar el comportamiento del sistema. Devuelve campos previsibles en vez de
texto libre y deja una ficha tecnica de consumo y tiempo.

Esto no garantiza todavia una respuesta correcta. Garantiza que el siguiente componente recibira una
solicitud limitada, observable y comprobable.

## Endpoint

`POST /v1/assistant/query-plans`

Requiere el mismo Bearer JWT valido del piloto. Acepta:

```json
{
  "question": "Cual es la politica de reembolso?"
}
```

La pregunta debe tener entre 3 y 2,000 caracteres. La respuesta contiene:

- `plan`: pregunta normalizada, idioma, intencion, necesidad de recuperar evidencia, sensibilidad y
  banderas de riesgo;
- `trace`: identificadores tecnicos, proveedor, modelo, prompt y version, latencia, tokens, costo
  estimado y confirmacion de que el almacenamiento del proveedor esta desactivado.

La traza no contiene pregunta, respuesta, JWT, clave del proveedor ni datos personales.

## Configuracion

| Variable | Secreta | Regla |
|---|---:|---|
| `OPENAI_API_KEY` o `OPENAI_API_KEY_FILE` | Si | Exactamente una fuente; solo necesaria al invocar IA |
| `OPENAI_MODEL` | No | Predeterminado `gpt-5.6-sol`; sin espacios |
| `OPENAI_TIMEOUT_SECONDS` | No | 1 a 120; predeterminado 30 |
| `OPENAI_MAX_RETRIES` | No | 0 a 5; predeterminado 2 |
| `OPENAI_MAX_OUTPUT_TOKENS` | No | 64 a 4,096; predeterminado 500 |
| `OPENAI_INPUT_COST_PER_MILLION_USD` | No | Decimal no negativo u omitido |
| `OPENAI_OUTPUT_COST_PER_MILLION_USD` | No | Decimal no negativo u omitido |

El costo solo se muestra cuando ambos precios estan configurados. Esta decision evita presentar como
vigente una tarifa antigua.

## Fallos seguros

| Situacion | HTTP | Codigo publico |
|---|---:|---|
| JWT ausente o invalido | 401 | `invalid_token` |
| Entrada invalida | 422 | `invalid_request` |
| Rechazo del modelo | 422 | `ai_refused` |
| Clave/configuracion ausente | 503 | `ai_not_configured` |
| Timeout, error o salida no parseable | 503 | `ai_provider_unavailable` |

Los errores publicos no incluyen detalles internos del SDK ni contenido privado.

## Uso de OpenAI

- `client.responses.parse(...)` usa la Responses API y deriva el esquema desde `QueryPlan` de
  Pydantic.
- `instructions` contiene reglas estables; `input` contiene exclusivamente la pregunta no confiable.
- `store=False` se envia en cada solicitud.
- `metadata` incluye un identificador de ejecucion y las versiones del prompt, no contenido del
  usuario.
- Una negativa del modelo se detecta como `refusal`; no se intenta forzar una salida.

Fuentes oficiales consultadas el 18 de julio de 2026:

- [Migrar a Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)
- [Salidas estructuradas](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Uso de herramientas](https://developers.openai.com/api/docs/guides/tools)
- [Guia de prompting GPT-5.6](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)

## Fuera de alcance de este incremento

- embeddings, `pgvector`, chunking y busqueda hibrida;
- autorizacion por documento;
- generacion de respuestas y citas;
- memoria conversacional;
- herramientas de accion y aprobacion humana;
- evaluacion de calidad con 30 casos.
