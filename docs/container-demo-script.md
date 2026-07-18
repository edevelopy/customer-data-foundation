# Guion de demo — API completamente contenerizada

Duracion objetivo: cinco minutos. Audiencia: cliente operativo y responsable tecnico.

## 1. Mensaje para cliente

> La aplicacion, la preparacion de la base y la prueba de integracion viajan como unidades
> reproducibles. Si la preparacion de datos falla, el servicio no se abre al trafico.

## 2. Arranque controlado

```bash
docker compose --profile api up --build -d --wait api
```

Mostrar que `database` esta healthy, `api_migrate` termino con codigo 0 y `api` esta healthy.

## 3. Aislamiento observado

Mostrar solamente los resultados aprobados: UID `10001`, root filesystem de solo lectura,
`cap_drop=[ALL]` y health `healthy`. No mostrar el entorno del contenedor.

## 4. Cliente dentro de Docker

Generar un token local de 15 minutos sin imprimirlo y ejecutar `api_smoke`. La salida debe
mostrar aceptacion, estado, intento, conteo e identificador; nunca el token ni el CSV.

## 5. Apagado

Enviar `SIGTERM`, esperar hasta 15 segundos y mostrar `exit_code=0` y `OOMKilled=false`.

## 6. Limites honestos

La imagen esta endurecida y probada localmente, pero todavia no esta publicada en un registry
ni desplegada con TLS, identidad externa, secretos administrados o observabilidad cloud.
