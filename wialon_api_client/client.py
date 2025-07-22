# wialon_api_client/client.py
"""
Módulo Python para interactuar con la API de Wialon.

Este módulo proporciona una clase `WialonClient` para gestionar la autenticación
y realizar operaciones comunes como obtener listas de unidades y su kilometraje.
Utiliza un gestor de contexto (`with`) para una gestión limpia de la sesión.

Requisitos:
    - requests: Para realizar llamadas HTTP a la API de Wialon.
    - python-dotenv: Para cargar variables de entorno desde un archivo .env.
    - logging (estándar de Python): Para registrar eventos.

Uso (como módulo con gestor de contexto):
    from wialon_api_client import WialonClient, WialonAPIError
    import os
    from dotenv import load_dotenv # Importar para cargar .env
    from pathlib import Path

    # Cargar variables del archivo .env
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

    try:
        token = os.getenv("WIALON_TOKEN")
        if not token:
            raise ValueError("La variable de entorno WIALON_TOKEN no está configurada. Asegúrate de tener un archivo .env o la variable exportada.")
        
        base_url_from_env = os.getenv("WIALON_BASE_URL") 

        with WialonClient(token, base_url=base_url_from_env) as client:
            unidades = client.get_unit_ids()
            for unidad in unidades:
                logger.info(f"Unidad: {unidad['nombre']} (ID: {unidad['id']})")
                kilometraje = client.get_unit_mileage(unidad['id'])
                if kilometraje is not None:
                    logger.info(f"  Kilometraje: {kilometraje} km")

    except WialonAPIError as e:
        logger.error(f"Error de la API de Wialon: {e}")
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
    except Exception as e:
        logger.error(f"Ocurrió un error inesperado: {e}")

Uso (desde línea de comandos):
    python -m wialon_api_client.client -m 4959MXM
    Si no se especifica la matrícula, se listan todas las unidades.

Notas:
    - El token de autenticación de Wialon debe configurarse mediante la variable de entorno 'WIALON_TOKEN', preferiblemente en un archivo .env.
    - La URL base de la API de Wialon puede configurarse como 'WIALON_BASE_URL' en .env.
    - El kilometraje se obtiene en la unidad que Wialon proporciona (puede ser en decímetros o kilómetros).
    - Este módulo es un ejemplo básico y puede necesitar ajustes según tu caso de uso específico.
    - Se recomienda implementar un sistema de logging más robusto para entornos de producción.
"""

import requests
import json
import argparse
import os
from dotenv import load_dotenv
from pathlib import Path
import logging

# --- Configuración básica del logging estándar ---
# Configura el logger para mostrar mensajes INFO y superiores en la consola.
# El formato incluye la hora, el nombre del logger, el nivel y el mensaje.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Cargar variables de entorno desde el archivo .env
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

# --- Clases de Excepción Personalizadas ---
class WialonAPIError(Exception):
    """Excepción base para errores específicos de la API de Wialon."""
    pass

class WialonAuthError(WialonAPIError):
    """Excepción para errores de autenticación con la API de Wialon."""
    pass

class WialonRequestError(WialonAPIError):
    """Excepción para errores de solicitud HTTP a la API de Wialon."""
    pass

class WialonDataError(WialonAPIError):
    """Excepción para errores relacionados con los datos devueltos por la API de Wialon."""
    pass

# --- Clase Cliente Wialon ---
class WialonClient:
    """
    Cliente para interactuar con la API de Wialon.
    Gestiona la sesión y las llamadas a la API.

    Implementa el protocolo de gestor de contexto (__enter__ y __exit__)
    para asegurar el login y el logout de la sesión de Wialon.
    """
    DEFAULT_BASE_URL = "https://hst-api.wialon.com/wialon/ajax.html"

    def __init__(self, token: str, base_url: str = None):
        if not token:
            logger.error("El token de Wialon no puede estar vacío al inicializar WialonClient.")
            raise ValueError("El token de Wialon no puede estar vacío.")
        self.token = token
        self._sid = None # Almacenará el Session ID
        self.base_url = base_url if base_url else self.DEFAULT_BASE_URL
        logger.info(f"WialonClient inicializado con BASE_URL: {self.base_url}")

    def __enter__(self):
        """Método de entrada del gestor de contexto. Realiza el login."""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Método de salida del gestor de contexto. Realiza el logout."""
        self.logout()
        # Si __exit__ devuelve True, suprime la excepción. Aquí no la suprimimos.

    def _call_api(self, service: str, params: dict) -> dict:
        """
        Método privado para realizar llamadas genéricas a la API de Wialon.
        Maneja la serialización JSON de los parámetros y el manejo básico de errores.
        """
        full_params = {
            "svc": service,
            "params": json.dumps(params)
        }
        if self._sid:
            full_params["sid"] = self._sid

        try:
            logger.debug(f"Realizando llamada a Wialon API: {service} con params: {params}")
            response = requests.get(self.base_url, params=full_params) # Usar self.base_url
            response.raise_for_status() # Lanza una excepción para errores HTTP (4xx o 5xx)
            data = response.json()

            if "error" in data:
                error_code = data.get('error', 'N/A')
                error_msg = f"API Error {error_code}: {service} - {data.get('reason', 'Unknown error')}"
                logger.error(error_msg)
                if service == "token/login":
                    raise WialonAuthError(error_msg)
                else:
                    raise WialonAPIError(error_msg)
            
            logger.debug(f"Respuesta exitosa de {service}: {data}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión al llamar a {service}: {e}")
            raise WialonRequestError(f"Error de conexión al llamar a {service}: {e}")
        except json.JSONDecodeError:
            logger.error(f"Error al decodificar la respuesta JSON de {service}: {response.text}")
            raise WialonDataError(f"Error al decodificar la respuesta JSON de {service}: {response.text}")

    def login(self) -> str:
        """
        Inicia sesión en la API de Wialon y obtiene un Session ID (sid).
        El sid se guarda en la instancia del cliente.
        """
        if self._sid:
            logger.info("Ya hay una sesión activa. Reutilizando SID.")
            return self._sid
        
        logger.info("Obteniendo SID...")
        data = self._call_api("token/login", {"token": self.token})
        
        if "eid" in data:
            self._sid = data["eid"]
            logger.info(f"SID obtenido exitosamente: {self._sid}")
            return self._sid
        else:
            logger.error("Respuesta inesperada al obtener SID: 'eid' no encontrado.")
            raise WialonAuthError("Respuesta inesperada al obtener SID: 'eid' no encontrado.")

    def logout(self):
        """
        Cierra la sesión actual de Wialon.
        """
        if self._sid:
            logger.info("Cerrando sesión de Wialon...")
            try:
                self._call_api("core/logout", {})
                self._sid = None
                logger.info("Sesión cerrada exitosamente.")
            except WialonAPIError as e:
                # Extraer el código de error para manejar el "API Error 0" específicamente
                error_code_str = str(e).split(':')[0].replace('API Error ', '')
                try:
                    error_code = int(error_code_str)
                except ValueError:
                    error_code = -1 # Código desconocido

                if error_code == 0: # API Error 0: Error genérico, a menudo benigno al cerrar sesión
                    logger.debug(f"Sesión ya invalidada o error genérico al cerrar sesión (código 0): {e}")
                else:
                    logger.warning(f"Advertencia al cerrar sesión: {e}")
            except Exception as e:
                logger.error(f"Error inesperado al intentar cerrar sesión: {e}")
        else:
            logger.debug("No hay sesión activa para cerrar.")

    def ensure_sid(self):
        """Asegura que hay un SID válido. Si no lo hay, intenta iniciar sesión."""
        if not self._sid:
            self.login()

    def get_unit_ids(self, unit_name_mask: str = "*") -> list[dict]:
        """
        Obtiene una lista de unidades (nombre e ID) de la API de Wialon.
        Puedes usar '*' para obtener todas o un patrón como '*4959MXM*' para filtrar.
        Retorna una lista de diccionarios con 'nombre' e 'id'.
        """
        self.ensure_sid() 
        logger.debug(f"Buscando unidades con máscara: '{unit_name_mask}'")

        params_search = {
            "spec": {
                "itemsType": "avl_unit",
                "propName": "sys_name",
                "propValueMask": unit_name_mask,
                "sortType": "sys_name"
            },
            "force": 1,
            "flags": 1, # Flag 1 para obtener propiedades básicas (nombre, id)
            "from": 0,
            "to": 0
        }
        data = self._call_api("core/search_items", params_search)

        if "items" in data:
            unidades = [{"nombre": item["nm"], "id": item["id"]} for item in data["items"]]
            logger.debug(f"Se encontraron {len(unidades)} unidades.")
            return unidades
        else:
            logger.error("Respuesta inesperada al buscar unidades: 'items' no encontrado.")
            raise WialonDataError("Respuesta inesperada al buscar unidades: 'items' no encontrado.")

    def get_unit_mileage(self, item_id: int) -> float | None:
        """
        Obtiene el kilometraje (cnm_km) de una unidad específica.
        Retorna el kilometraje como un número flotante o None si no está disponible.
        """
        self.ensure_sid() 
        logger.debug(f"Obteniendo kilometraje para ID: {item_id}")

        params_get_item = {
            "id": item_id,
            "flags": 8192 # Flag 8192 para obtener contadores (incluye cnm_km)
        }
        data = self._call_api("core/search_item", params_get_item)

        if "item" in data and "cnm_km" in data["item"]:
            kilometraje_api = data["item"]["cnm_km"]
            logger.debug(f"  Kilometraje obtenido: {kilometraje_api} km")
            return float(kilometraje_api)
        else:
            logger.warning(f"  No se encontró 'cnm_km' para el ID {item_id}. Respuesta: {data.get('item', 'N/A')}")
            return None # Retorna None si el kilometraje no está en la respuesta


# --- Lógica principal para ejecutar desde línea de comandos ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Obtiene el kilometraje de unidades de Wialon.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '-m', '--mat', 
        type=str, 
        help='Matrícula de la unidad a buscar (ej: 4959MXM). Si no se especifica, se listan todas las unidades.'
    )

    args = parser.parse_args()

    wialon_token = os.getenv("WIALON_TOKEN")
    wialon_base_url = os.getenv("WIALON_BASE_URL")

    if not wialon_token:
        logger.error("Error: La variable de entorno 'WIALON_TOKEN' no está configurada.")
        logger.error("Asegúrate de tener un archivo '.env' en el directorio raíz del proyecto con el formato:")
        logger.error("  WIALON_TOKEN='TU_TOKEN_DE_AUTENTICACION_AQUI'")
        logger.error("O exporta la variable en tu terminal: export WIALON_TOKEN='TU_TOKEN_AQUI'")
        exit(1)

    try:
        with WialonClient(token=wialon_token, base_url=wialon_base_url) as client:
            nombre_unidad_mask = f"*{args.mat}*" if args.mat else "*"
            
            todas_mis_unidades = client.get_unit_ids(nombre_unidad_mask)

            if not todas_mis_unidades:
                logger.warning("No se encontraron unidades o hubo un error al obtenerlas.")
                # No salir aquí, porque si no hay unidades, no es un error fatal para el programa,
                # simplemente no hay nada que procesar.
                # exit(1) # Eliminado para permitir que el programa termine normalmente

            logger.info("\n--- Obteniendo kilometraje de cada unidad ---")

            # Solo intentar procesar si se encontraron unidades
            if todas_mis_unidades:
                for unidad in todas_mis_unidades:
                    logger.info(f"\nProcesando unidad: {unidad['nombre']} (ID: {unidad['id']})")
                    kilometraje = client.get_unit_mileage(unidad['id'])

                    if kilometraje is not None:
                        logger.info(f"  Kilometraje actual: {kilometraje} km")
                    else:
                        logger.warning(f"  No se pudo obtener el kilometraje para esta unidad.")
            else:
                logger.info("No hay unidades para procesar.") # Mensaje si no se encontraron unidades

    except WialonAuthError as e:
        logger.error(f"Error de autenticación con Wialon: {e}")
        exit(1)
    except WialonRequestError as e:
        logger.error(f"Error de conexión a la API de Wialon: {e}")
        exit(1)
    except WialonDataError as e:
        logger.error(f"Error de datos de la API de Wialon: {e}")
        exit(1)
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        exit(1)
    except Exception as e:
        logger.critical(f"Ocurrió un error inesperado y crítico: {e}", exc_info=True) # exc_info=True para traceback
        exit(1)