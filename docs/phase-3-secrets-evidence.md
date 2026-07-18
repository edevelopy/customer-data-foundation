# Evidencia de Fase 3 — Incremento 2: configuracion y secretos

Fecha: 18 de julio de 2026.

## Problema y criterios de aceptacion

Las variables directas de `.env` son adecuadas para desarrollo, pero una plataforma compartida
debe montar valores desde su gestor de secretos. La imagen no debe cambiar entre ambientes ni
mostrar material sensible al validar configuracion.

El incremento se acepta cuando:

- API, worker y partner aceptan la convencion `<NAME>_FILE`.
- Configurar fuente directa y archivo a la vez falla antes de arrancar.
- Archivos ausentes, cortos, grandes, multilinea o no UTF-8 fallan sin revelar valor o ruta.
- Existe un preflight que valida componentes y solo emite codigos seguros.
- Git ignora el directorio reservado para material local de despliegue.

## Evidencia local observada

- `fde-config-check api worker partner` devolvio
  `{"status":"ready","targets":["api","worker","partner"]}`.
- Pruebas con archivos temporales confirmaron lectura con newline final y rechazo de fuente
  ambigua o multilinea.
- El preflight invalido devolvio solo `configuration_invalid`; el secreto de prueba no aparecio.
- Ruff, Mypy (31 archivos), Actionlint y Compose aprobaron.
- 59 pruebas aprobaron contra PostgreSQL efimero.
- Cobertura combinada: 76.59%, por encima del gate de 75%.

## Controles y limites

Los secretos reales no se crean en este repositorio. `deploy/secrets/README.md` es el unico archivo
permitido bajo esa ruta; los valores estan ignorados. Docker Compose local no cifra archivos en
disco, por lo que la prueba de despliegue usara archivos efimeros y una plataforma real debe usar
su servicio administrado.

La rotacion dual no esta implementada: se documenta una rotacion coordinada por release. El
ambiente reproducible que monta estos archivos y ejecuta el preflight pertenece al siguiente
incremento.
