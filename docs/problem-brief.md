# Brief del problema

## Cliente simulado

Una pequena empresa que recibe periodicamente archivos CSV con datos de clientes
procedentes de proveedores y equipos internos.

## Usuario principal

La persona responsable de operaciones. Conoce el proceso de negocio, pero no debe
necesitar conocimientos de Python o SQL para ejecutar una importacion.

## Dolor actual

Los archivos contienen campos incompletos, formatos invalidos y clientes duplicados.
La persona responsable limpia cada archivo manualmente antes de cargarlo, un proceso
lento y propenso a errores silenciosos.

## Flujo actual

1. Recibir el CSV por correo o carpeta compartida.
2. Abrirlo en una hoja de calculo.
3. Buscar datos vacios y corregir formatos manualmente.
4. Intentar identificar duplicados por nombre o correo.
5. Cargar los datos y corregir problemas reportados posteriormente.

## Resultado deseado

Una herramienta reproducible valida el archivo, rechaza registros incorrectos con una
explicacion accionable y evita duplicados al repetir una importacion.

## Linea base y primera metrica de exito

- Linea base: aproximadamente 120 minutos de trabajo manual por archivo.
- Objetivo inicial: producir un resultado de validacion en menos de 5 minutos.
- Restriccion de calidad: 0 duplicados nuevos al importar dos veces el mismo archivo.

## Alcance de la Fase 0

Esta fase prepara el entorno profesional y demuestra que el proyecto puede instalarse,
diagnosticarse y probarse de forma reproducible. La importacion real de CSV y la base de
datos pertenecen al proyecto de la Fase 1.

## Supuestos por validar

- El correo electronico puede servir como identificador inicial de un cliente.
- Los archivos caben en memoria durante el piloto.
- El usuario prefiere corregir los errores antes de confirmar una importacion parcial.

