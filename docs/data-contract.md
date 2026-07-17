# Contrato de datos de clientes

Estado: aprobado para el piloto de la Fase 1.

## Formato de entrada

- Archivo CSV codificado como UTF-8.
- Primera fila con encabezados.
- Maximo 10 MiB y 10,000 registros por lote.
- Las cinco columnas son obligatorias; el orden puede variar.
- Las columnas inesperadas se rechazan para evitar almacenar datos no autorizados.

| Campo | Obligatorio | Regla | Normalizacion |
|---|---:|---|---|
| `email` | Si | Formato de email, maximo 254 caracteres | Espacios externos eliminados y minusculas |
| `first_name` | Si | Texto visible, 1 a 80 caracteres | Espacios repetidos colapsados |
| `last_name` | Si | Texto visible, 1 a 80 caracteres | Espacios repetidos colapsados |
| `phone` | No | E.164: `+` seguido por 8 a 15 digitos | Espacios externos eliminados |
| `source` | Si | Texto visible, 1 a 50 caracteres | Espacios colapsados y minusculas |

## Identidad e idempotencia

Durante el piloto, el email normalizado es la clave natural del cliente. Dos variantes que
solo cambian mayusculas o espacios se consideran el mismo cliente. Esta decision debe
revisarse si el negocio permite emails compartidos o si los proveedores entregan un
identificador externo estable.

## Semantica estricta aprobada

1. Se valida el lote completo antes de escribir datos.
2. Cualquier error rechaza el lote completo.
3. El reporte identifica fila, campo, codigo, explicacion y correccion.
4. El reporte no copia emails, telefonos ni otros valores recibidos.
5. Corregir y reenviar el mismo archivo no puede crear duplicados.

## Criterios de aceptacion del incremento

- Un archivo valido produce `accepted=true` y codigo de salida 0.
- Emails repetidos dentro del archivo rechazan el lote.
- Campos obligatorios vacios y formatos incorrectos se reportan por fila.
- Columnas inesperadas, archivos demasiado grandes y mas de 10,000 registros se rechazan.
- Ningun registro se persiste durante este incremento.
- Ruff, pruebas locales y CI deben pasar antes de aceptar el cambio.

