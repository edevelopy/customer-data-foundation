# Contrato de configuracion y secretos

## Objetivo

La misma imagen acepta secretos inyectados por el entorno sin incorporarlos a Git, variables de
build, capas OCI ni argumentos visibles. Desarrollo local conserva variables directas; un ambiente
administrado usa archivos montados por su gestor de secretos.

## Interfaz

| Secreto | Desarrollo local | Ambiente administrado |
|---|---|---|
| Firma JWT | `JWT_SECRET` | `JWT_SECRET_FILE` |
| HMAC de identificadores | `IDENTIFIER_HASH_KEY` | `IDENTIFIER_HASH_KEY_FILE` |
| Webhook socio | `PARTNER_WEBHOOK_SECRET` | `PARTNER_WEBHOOK_SECRET_FILE` |

Para cada secreto se configura exactamente una fuente. Si existen la variable directa y `_FILE`,
el proceso falla antes de abrir el servicio. Los archivos deben:

- ser legibles por UID `10001`;
- contener UTF-8, maximo 8 KiB y un unico valor de al menos 32 caracteres;
- permitir solo un salto de linea final, nunca lineas embebidas;
- montarse read-only fuera de la imagen.

`fde-config-check api worker partner` valida todas las configuraciones y devuelve solamente estado,
codigo seguro y nombres de componentes. Nunca imprime valores, rutas, URLs ni longitudes.

## Responsabilidades del entorno

- Crear, cifrar, auditar y montar los secretos mediante el servicio administrado de la plataforma.
- Conceder lectura solo a la identidad del componente que la necesita.
- No colocar secretos en Compose versionado, artifacts, tickets, logs o comandos compartidos.
- Rotar creando una nueva version, desplegarla, ejecutar health/smoke y retirar la version anterior
  despues de confirmar el nuevo release.

El piloto no acepta simultaneamente dos claves JWT/HMAC. Una rotacion exige despliegue coordinado;
rotacion dual sin interrupcion queda fuera de este incremento.

## Fallo seguro

Fuente ausente, corta, ilegible, demasiado grande, no UTF-8, multilinea o ambigua produce
`configuration_invalid` en preflight y evita el arranque. El error no incluye el secreto ni la
ruta. La configuracion no secreta —URLs, issuer, audience, puertos y limites— permanece en variables
de entorno versionables por ambiente.
