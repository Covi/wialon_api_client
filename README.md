# Wialon API Client

Un cliente Python modular y robusto para interactuar con la API de Wialon, diseñado siguiendo principios SOLID y buenas prácticas. Este módulo facilita la autenticación, la búsqueda de unidades y la obtención de datos clave como el kilometraje.

## Características

* **Autenticación Sencilla**: Inicia y cierra sesión de forma gestionada.
* **Búsqueda de Unidades**: Encuentra unidades por máscara de nombre o lista todas las disponibles.
* **Obtención de Kilometraje**: Recupera el kilometraje actual de las unidades.
* **Manejo de Errores Robusto**: Excepciones personalizadas para una gestión clara de errores de API y conexión.
* **Configuración Segura**: Utiliza variables de entorno para el token de Wialon, evitando su `hardcoding`.
* **Diseño Modular (SOLID)**: Implementado como una clase para una mejor encapsulación y reutilización.

## Requisitos

* Python 3.8 o superior
* `requests`

## Instalación

Puedes instalar este cliente directamente desde GitHub usando `pip`:

```bash
pip install git+[https://github.com/Covi/wialon_api_client.git@main](https://github.com/Covi/wialon_api_client.git@main)
```

## Para Desarrollo
Si estás desarrollando el módulo o quieres que los cambios locales se reflejen sin reinstalar:

```bash
cd /ruta/a/tu/repositorio/wialon_api_client
pip install -e .
```
