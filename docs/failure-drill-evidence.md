# Evidencia de simulacros operativos

Fecha de ejecucion: 18 de julio de 2026.

## Migracion y recuperacion

Se creo una base desechable independiente de desarrollo y pruebas.

1. `upgrade head` preparo la revision `0001_customer_imports`.
2. Una importacion inserto 3 registros y emitio `status=imported` en 48 ms.
3. `downgrade base` elimino el esquema de la base desechable.
4. El siguiente intento se detuvo con codigo 2, `migration_required`, 0 insertados y 29 ms.
5. Un nuevo `upgrade head` recupero el esquema.
6. La importacion posterior inserto 3 registros y emitio `status=imported` en 46 ms.
7. La base desechable fue eliminada al terminar.

Resultado: el importador no intenta improvisar tablas ni escribir cuando la revision falta.

## PostgreSQL inalcanzable

Se intento importar contra un puerto local cerrado.

- Codigo de salida: 2.
- Estado: `database_error`.
- Duracion observada: 4 ms.
- Insertados: 0.
- El evento no contenia usuario, contrasena, base ni URL de conexion.

## Conflicto transaccional

Un lote contenia un cliente nuevo y otro cliente existente con datos diferentes.

- Estado: `conflict`.
- Codigo de salida: 1.
- El reporte identifico fila y codigo sin copiar el email.
- El cliente nuevo tuvo conteo cero despues de la operacion.
- El lote conflictivo no fue registrado.

## Puerto ocupado

El puerto 55432 pertenecia a otro contenedor. Se identifico su propietario, no se detuvo y
el proyecto se configuro en 55433. La base de pruebas se aislo despues en 55434 con
almacenamiento efimero para impedir que Pytest trunque datos de desarrollo.

## Resultado

Los cuatro escenarios tienen deteccion, salida segura, recuperacion y evidencia. Los
tiempos pertenecen a estas ejecuciones locales y no constituyen un SLA.

