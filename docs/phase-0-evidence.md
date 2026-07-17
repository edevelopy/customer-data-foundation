# Evidencia de la Fase 0

Fecha de verificacion: 17 de julio de 2026.

## Resultado

El repositorio cumple el criterio de aprobacion de la Fase 0: una segunda copia se pudo
instalar y ejecutar siguiendo unicamente las instrucciones del README.

## Decisiones

- Caso: validacion confiable de archivos CSV de clientes para una pequena empresa.
- Linea base: 120 minutos de limpieza manual por archivo.
- Meta inicial: resultado de validacion en menos de 5 minutos y cero duplicados nuevos.
- Python minimo: 3.12, administrado mediante `uv` y un archivo de bloqueo.
- La Fase 0 no implementa todavia el importador ni PostgreSQL.
- Modelo AI-native: el FDE define resultados, limites y riesgos; el agente ejecuta; la
  aprobacion depende de evidencia observable.

## Verificacion observada

| Comprobacion | Resultado |
|---|---|
| `uv sync --locked` en el repositorio de trabajo | Aprobada |
| Ruff | Sin errores |
| Pytest | 3 pruebas aprobadas |
| Diagnostico local | 0 fallos obligatorios |
| Clon nuevo en una carpeta temporal | Instalacion y ejecucion aprobadas |
| GitHub Actions | Pipeline de calidad aprobado |

Historial de pipelines:
<https://github.com/edevelopy/customer-data-foundation/actions>

## Seguridad y operacion

- `.env` esta excluido de Git y el diagnostico no lee ni imprime su contenido.
- `.env.example` contiene solo configuracion de muestra, sin credenciales reales.
- El workflow de CI tiene permiso de solo lectura sobre el contenido.
- El diagnostico comprueba Python, Git, Docker, archivos requeridos, escritura temporal,
  DNS, TLS y disponibilidad del puerto local 8000.
- Las comprobaciones que dependen de red o herramientas futuras generan advertencias y no
  impiden trabajar sin conexion.

## Limitaciones y riesgos restantes

- No existe aun una entrada CSV ni validacion de registros.
- PostgreSQL y el endpoint HTTP pertenecen al siguiente incremento practico.
- La metrica de menos de 5 minutos no puede medirse hasta implementar el flujo de datos.
- Antes de usar datos reales se necesita una politica explicita de privacidad y retencion.

## Retrospectiva

Funciono bien separar el problema del cliente del entorno tecnico y exigir una prueba desde
un clon limpio. La primera ejecucion de CI paso, pero produjo una advertencia por acciones
basadas en Node.js 20; se actualizaron y se ejecuto nuevamente el pipeline. En la siguiente
fase conviene definir primero el contrato de datos y ejemplos validos e invalidos antes de
escribir el importador.
