# Guia de consumo de la imagen

## Lo que recibe el cliente

El proveedor entrega dos datos: el nombre de la imagen y su digest aprobado. El digest funciona
como una huella digital: si cambia un byte del artefacto, cambia su identidad.

```text
IMAGE=ghcr.io/edevelopy/customer-data-foundation-api
DIGEST=sha256:<digest entregado>
```

No despliegues solamente `:main`; esa etiqueta puede avanzar. Conserva `IMAGE@DIGEST` en la
configuracion y en el registro de cambios del cliente.

## Descarga publica

El paquete actual permite descarga anonima. No se necesita copiar un token al cliente:

```bash
docker pull --platform linux/amd64 "$IMAGE@$DIGEST"
```

Selecciona `linux/arm64` cuando ese sea el tipo de host. Un registry privado usaria credenciales
de corta duracion con permiso minimo `read:packages`; nunca se copian a `.env`, tickets, capturas
de pantalla o documentos de entrega.

## Verificacion de procedencia

Con GitHub CLI autenticado:

```bash
gh attestation verify "oci://$IMAGE@$DIGEST" \
  --repo edevelopy/customer-data-foundation
```

La verificacion debe identificar el repositorio y el workflow esperado. Un resultado correcto no
autoriza automaticamente el despliegue: tambien se comprueban el digest aprobado, el entorno y
las politicas internas del cliente.

## Inspeccion minima

```bash
docker buildx imagetools inspect "$IMAGE@$DIGEST"
docker image inspect "$IMAGE@$DIGEST" --format '{{.Config.User}}'
```

El segundo comando debe devolver `10001:10001`. Para operar la aplicacion se siguen las variables,
migraciones, health checks y restricciones de ejecucion de
[`container-contract.md`](container-contract.md); la imagen no incluye secretos ni configuracion
del cliente.

## Revocacion o reemplazo

Una etiqueta borrada no invalida una copia que el cliente ya descargo. Si un digest deja de ser
aprobado, el responsable comunica el digest afectado, publica uno nuevo, actualiza la referencia
de despliegue y conserva la trazabilidad del cambio.
