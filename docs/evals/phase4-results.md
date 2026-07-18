# Resultados reproducibles — Fase 4

Generado: 2026-07-18T12:03:39.261485+00:00.

Resultado: **APROBADO**.

## Metricas

| Metrica | Resultado |
|---|---:|
| `case_count` | 38 |
| `positive_case_count` | 32 |
| `negative_case_count` | 6 |
| `baseline_retrieval_recall` | 1.0 |
| `improved_retrieval_recall` | 1.0 |
| `improved_retrieval_precision` | 0.3333 |
| `answer_accuracy` | 1.0 |
| `groundedness` | 1.0 |
| `refusal_accuracy` | 1.0 |
| `permission_leakage_count` | 0 |
| `baseline_p95_latency_ms` | 37 |
| `improved_p95_latency_ms` | 109 |
| `input_tokens` | 0 |
| `output_tokens` | 0 |
| `estimated_cost_usd` | 0.0 |

## Puertas de aceptacion

- PASS — `at_least_30_cases`
- PASS — `retrieval_not_worse_than_baseline`
- PASS — `answer_accuracy_at_least_85_percent`
- PASS — `groundedness_at_least_95_percent`
- PASS — `refusal_accuracy_at_least_95_percent`
- PASS — `zero_permission_leakage`

## Integridad

- Dataset: `1.0.0`.
- SHA-256 documentos: `a3af7920cd4ade2fd1684e2f03d8f6c61a78f30b4c2014c483bb1fd50a02baf9`.
- SHA-256 casos: `081f9989bb1124b80e5618861f64637e3be153b563925f1d12cecfeaaea0fa02`.
- Proveedor: `deterministic_local` (no es IA).

## Limites

- The deterministic provider validates reproducibility and controls, not OpenAI quality.
- Live model token usage, cost, and answer quality remain unmeasured without a credential.
- Synthetic documents must be replaced or complemented with approved client cases.

## Que sigue

Incremento 5: tool calling controlado, aprobacion humana, auditoria, limites de uso, cache y degradacion segura.
