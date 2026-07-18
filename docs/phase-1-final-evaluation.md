# Evaluacion final de la Fase 1

Fecha: 18 de julio de 2026.

## Resultado

**Aprobada: 32/40 y ninguna dimension por debajo de 2.**

El entregable es una CLI que valida CSV, genera reportes seguros e importa clientes en
PostgreSQL con transacciones, idempotencia y deteccion de conflictos. La evaluacion no
convierte este piloto en un sistema productivo ni reemplaza validacion con usuarios reales.

## Rubrica

| Dimension | Puntuacion | Evidencia y limite |
|---|---:|---|
| Problema y valor | 3 | Usuario, flujo, linea base de 120 minutos y meta menor de 5; caso aun simulado |
| Funcionalidad | 4 | Valido, invalido, reintento, conflicto, concurrencia y fallos operativos |
| Calidad tecnica | 4 | Modulos separados, contratos, transacciones y migraciones versionadas |
| Datos e integraciones | 4 | Restricciones, idempotencia, rollback y concurrencia observada |
| Testing | 4 | 20 pruebas, PostgreSQL real, privacidad, limites y contratos |
| Seguridad | 2 | Sin PII en reportes/logs y puertos locales; usuario local aun tiene privilegios amplios |
| Operacion | 3 | Health checks, eventos JSON, metricas derivadas, runbook y rollback; sin alertas ni trazas |
| Comunicacion | 4 | README, contratos, decisiones, evidencias, runbook y guion de demo |
| Experiencia de usuario | 2 | CLI reproducible y errores accionables; no probada aun con un usuario real |
| Entrega y adopcion | 2 | Instalacion y demo documentadas; falta capacitacion y seguimiento real |
| **Total** | **32/40** | **Supera el minimo sugerido de 30/40** |

## Criterios finales

- CSV valido importado en una sola transaccion.
- Archivo invalido rechazado antes de conectar con PostgreSQL.
- Reimportacion exacta sin duplicados, incluso con dos procesos concurrentes.
- Cliente existente diferente produce rollback completo.
- Migracion ausente bloquea escrituras y ofrece recuperacion documentada.
- Base inalcanzable produce un evento seguro y codigo operacional.
- Logs contienen solo los siete campos aprobados.
- Base de pruebas separada y efimera; no trunca desarrollo.
- Instalacion, migracion, importacion y pruebas reproducibles desde README.

## Verificacion final observada

- Suite local aislada: 20 pruebas aprobadas.
- GitHub Actions: migracion y 20 pruebas aprobadas en PostgreSQL efimero.
- Clon nuevo: dependencias instaladas desde `uv.lock`, dos bases aisladas saludables,
  revision `0001_customer_imports`, 3 clientes importados y 20 pruebas aprobadas.
- Formato y linting aprobados tanto en el repositorio de trabajo como en el clon nuevo.

Pipeline observado:
<https://github.com/edevelopy/customer-data-foundation/actions/runs/29630716578>

## Retrospectiva

Funciono bien definir primero el contrato y separar validacion, persistencia y operacion.
Las pruebas descubrieron dos riesgos que una demo feliz no habria mostrado: un puerto ya
ocupado y la posibilidad de ejecutar pruebas destructivas contra la base de desarrollo.
Ambos se resolvieron sin alterar proyectos ajenos.

La creacion automatica de tablas fue util para el primer incremento, pero ocultaba la
revision del esquema. Reemplazarla con Alembic permitio probar downgrade, bloqueo y
recuperacion. El siguiente proyecto debe introducir privilegios minimos desde el principio.

## Limites conocidos

- El email es una identidad provisional.
- El usuario local de PostgreSQL tiene privilegios mayores que los deseables en produccion.
- No hay interfaz grafica, alertas, trazas, backups ni despliegue cloud.
- No se ha medido el ahorro de tiempo con un usuario real.
- Los datos del repositorio y las pruebas son sinteticos.

## Siguiente fase recomendada

La Fase 2 incorporara FastAPI y un contrato HTTP alrededor del dominio ya probado. Antes de
implementar endpoints se definiran autenticacion, roles, limites de peticion, idempotencia y
criterios de aceptacion de la API.
