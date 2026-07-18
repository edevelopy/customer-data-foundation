# Evidencia de Fase 3 — Incremento 4: observabilidad y recuperacion

Fecha: 18 de julio de 2026.

## Criterios de aceptacion

- metricas autenticadas y agregadas, sin PII ni secretos;
- reglas ejecutables para lease vencido, dead letter y atraso de entrega;
- alerta observable con codigo no-cero y regreso a estado saludable;
- backup privado con hash y manifiesto seguro;
- restauracion real aislada que no modifique la fuente;
- acceso host a la API sin publicar PostgreSQL ni los servicios internos.

## Evidencia observada

- Suite local: 74 pruebas aprobadas; Mypy aprobo 38 archivos; cobertura combinada 75.07%.
- Se introdujo un `dead_letter` tecnico en el ambiente `cdf-release-v030`.
  `fde-ops-check` devolvio `status=alert`, alerta `outbox_dead_letter`, valor `1.0` y codigo `1`.
  Tras restaurar el estado tecnico, devolvio `status=healthy`, sin alertas y codigo `0`.
- `fde-backup create` produjo un dump y manifiesto `0600` con SHA-256
  `c9848202da635f8c12f1f5895713c9eca34991796b0f4e20f82f2239a63a31a9`.
- `fde-backup verify` restauro en una base aislada y comparo revision
  `0004_integration_outbox` y conteos `1/1/1/1/1` de lotes, clientes, operaciones, outbox y recibos.
- La base aislada se elimino al terminar; la base de release permanecio operativa.

## Defecto encontrado y correccion

`v0.3.0` aprobo el smoke dentro de la red, pero Docker Desktop no activo el puerto host cuando la
API solo pertenecia a una red `internal`. `v0.3.1` separa `edge` para la API y conserva `backend`
interna para PostgreSQL, partner y worker. El cierre requiere publicar, desplegar y verificar esa
release; esta evidencia no presenta el cambio local como resultado remoto.

## Limites

El dump local no esta cifrado porque permanece en un directorio temporal privado del simulacro. Un
ambiente real debe usar cifrado, almacenamiento externo, retencion y objetivos RPO/RTO aprobados.
Las reglas no envian notificaciones a un proveedor externo hasta que el cliente elija propietario,
canal y presupuesto de guardia.

## Cierre remoto

`v0.3.1` publico las metricas y la red edge en el digest
`sha256:e4facaf18a44214aa7ab9f8ad81976ad56198ca2ed5b0a440695ac666a7a2b53`. En el ambiente vivo,
`/metrics` autenticado reporto dos importaciones y entregas, cero dead letters; despues de rollback y
roll-forward reporto cuatro/cuatro/cero. El puerto host y el backup verificado aprobaron despues del
despliegue remoto, por lo que el defecto de `v0.3.0` queda cerrado.
