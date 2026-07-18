# Runbook de backup y restauracion PostgreSQL

## Politica

`fde-backup create` genera un archivo custom de `pg_dump` con modo `0600` y un manifiesto separado
que contiene SHA-256, revision de esquema y solo cinco conteos agregados. `fde-backup verify` valida
el hash, crea una base aleatoria aislada, restaura todo, compara revision/conteos y elimina la base
de verificacion. Nunca restaura encima de la base activa.

El dump contiene los datos completos, incluida PII. En un cliente debe cifrarse antes de salir del
host, enviarse a almacenamiento privado con versionado y retencion, y probarse periodicamente con
una identidad distinta. Git, CI artifacts, tickets y canales de chat estan prohibidos como destino.

## Crear y probar

```bash
umask 077
uv run fde-backup create \
  --project-name cdf-release \
  --archive /ruta/privada/customer-data.dump

uv run fde-backup verify \
  --project-name cdf-release \
  --archive /ruta/privada/customer-data.dump
```

Aceptacion: ambos archivos son `0600`; la verificacion devuelve `status=verified`; el SHA-256 y los
conteos restaurados coinciden; la revision es la esperada. Una falla de hash, `pg_restore`, esquema
o conteos devuelve codigo no-cero y no modifica la fuente.

## Recuperacion real

Ante perdida confirmada, no improvisar sobre el volumen original:

1. detener escritores y conservar el volumen para investigacion;
2. verificar el backup en una base aislada;
3. crear un volumen nuevo y restaurar con la misma version mayor de PostgreSQL;
4. ejecutar `alembic upgrade head` solo si el runbook de la release lo permite;
5. comprobar health, metricas y smoke antes de cambiar trafico;
6. registrar RPO, RTO, propietario, aprobacion y hash del backup.

Este piloto demuestra restaurabilidad, no define por si solo el RPO/RTO contractual ni una politica
legal de retencion. Esas decisiones pertenecen al cliente y deben quedar escritas antes de operar.
