# Secretos de despliegue

Este directorio solo contiene instrucciones. Los archivos reales estan ignorados por Git.

El entorno de despliegue montara secretos como archivos de solo lectura y configurara:

- `JWT_SECRET_FILE`;
- `IDENTIFIER_HASH_KEY_FILE`;
- `PARTNER_WEBHOOK_SECRET_FILE`.

Cada archivo contiene un unico valor de al menos 32 caracteres y puede terminar con una nueva
linea. No debe contener lineas adicionales. En una plataforma compartida, el archivo lo materializa
el gestor de secretos; no se crea ni distribuye manualmente junto al repositorio.
