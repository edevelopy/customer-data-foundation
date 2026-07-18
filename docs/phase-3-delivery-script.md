# Guion de entrega para un cliente no tecnico

## Mensaje principal

“No estamos entregando una carpeta de codigo. Estamos entregando una version identificable,
probada y recuperable. Si algo falla, podemos saber que version corre, detener una entrega
defectuosa, recuperar los datos y volver a la version anterior sin improvisar.”

## Reunion de 15 minutos

### 1. Recordar el problema — 2 minutos

El operador carga un archivo de clientes una sola vez. El sistema valida todo antes de escribir,
evita duplicados y avisa a otro sistema aunque ese socio falle temporalmente. La demostracion usa
datos sinteticos; nunca datos reales del cliente.

### 2. Explicar que significa una release — 2 minutos

Mostrar la pagina de `v0.3.1` y su manifiesto. Explicar el digest como “la huella digital exacta” de
la entrega. La etiqueta ayuda a hablar de la version; el digest impide que el contenido cambie por
debajo. La release solo existe si pruebas, escaneo y evidencia de origen aprobaron.

### 3. Demostrar el flujo — 3 minutos

Ejecutar el despliegue acordado. Mostrar `health=ready`; importar el CSV sintetico; señalar que el
socio falla una vez, el sistema reintenta y el evento termina entregado. No abrir variables de
entorno, tokens, dumps ni logs crudos delante de la audiencia.

### 4. Demostrar operacion — 3 minutos

Mostrar solo los conteos de metricas: operaciones, pendientes, entregadas y dead letters. Explicar
que una alerta no contiene nombres ni emails. Después mostrar el resultado `status=verified` del
backup: se restauro en otra base y se comparo antes de eliminarla.

### 5. Demostrar recuperacion — 3 minutos

Explicar el rollback observado de `v0.3.1` a `v0.3.0`: se reutilizo el mismo volumen, el smoke volvio
a pasar y los registros permanecieron. Luego se hizo roll-forward para dejar `v0.3.1` activo. No se
uso downgrade de base ni se edito un tag existente.

### 6. Acordar responsabilidades — 2 minutos

El equipo tecnico mantiene pipeline, runbooks y artefactos. El cliente decide propietarios,
ventana de mantenimiento, canal de alertas, RPO/RTO, retencion, residencia de datos, proveedor de
identidad y aprobadores. Sin esas decisiones no se afirma produccion, alta disponibilidad ni SLA.

## Preguntas de aceptacion

- ¿El responsable puede identificar la version y el digest activos?
- ¿Quedo claro que health comprueba disponibilidad, no exactitud de negocio?
- ¿Quien recibe una alerta critica y en cuanto tiempo debe responder?
- ¿Que perdida maxima de datos y tiempo de recuperacion acepta el negocio?
- ¿Quien autoriza deploy, rollback y restauracion real?
- ¿Donde se almacenan secretos y backups cifrados?

## Cierre sugerido

“El piloto queda listo como entrega reproducible y defendible. Para convertirlo en produccion no
hay que reescribir la aplicacion: hay que conectar identidad, TLS, infraestructura administrada,
alertamiento y politicas del cliente al mismo contrato que acabamos de probar.”
