# wialon_client.py
"""
Módulo Python para interactuar con la API de Wialon.

Este módulo proporciona una clase `WialonClient` para gestionar la autenticación
y realizar operaciones comunes como obtener listas de unidades y su kilometraje.

Requisitos:
    - requests: Para realizar llamadas HTTP a la API de Wialon.

Uso (como módulo):
    from wialon_client import WialonClient, WialonAPIError
    import os

    try:
        token = os.getenv("WIALON_TOKEN")
        if not token:
            raise ValueError("La variable de entorno WIALON_TOKEN no está configurada.")

        client = WialonClient(token)
        
        # Ejemplo: Obtener todas las unidades
        unidades = client.get_unit_ids()
        for unidad in unidades:
            print(f"Unidad: {unidad['nombre']} (ID: {unidad['id']})")
            kilometraje = client.get_unit_mileage(unidad['id'])
            if kilometraje is not None:
                print(f"  Kilometraje: {kilometraje} km")

        # Ejemplo: Obtener una unidad específica por matrícula
        unidad_especifica = client.get_unit_ids("4959MXM")
        if unidad_especifica:
            print(f"\nUnidad 4959MXM: {unidad_especifica[0]['nombre']} (ID: {unidad_especifica[0]['id']})")
            kilometraje_mat = client.get_unit_mileage(unidad_especifica[0]['id'])
            if kilometraje_mat is not None:
                print(f"  Kilometraje: {kilometraje_mat} km")

    except WialonAPIError as e:
        print(f"Error de la API de Wialon: {e}")
    except ValueError as e:
        print(f"Error de configuración: {e}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

Uso (desde línea de comandos):
    python wialon_client.py -m 4959MXM
    Si no se especifica la matrícula, se listan todas las unidades.

Notas:
    - El token de autenticación de Wialon debe configurarse mediante la variable de entorno 'WIALON_TOKEN'.
    - El kilometraje se obtiene en la unidad que Wialon proporciona (puede ser en decímetros o kilómetros).
    - Este módulo es un ejemplo básico y puede necesitar ajustes según tu caso de uso específico.
    - Se recomienda implementar un sistema de logging más robusto para entornos de producción.
"""

import requests
import json
import argparse
import os

# --- Configuración global ---
# URL base para todas las llamadas a la API de Wialon
BASE_URL = "https://hst-api.wialon.com/wialon/ajax.html"

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
    """
    def __init__(self, token: str):
        if not token:
            raise ValueError("El token de Wialon no puede estar vacío.")
        self.token = token
        self._sid = None # Almacenará el Session ID

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
            response = requests.get(BASE_URL, params=full_params)
            response.raise_for_status() # Lanza una excepción para errores HTTP (4xx o 5xx)
            data = response.json()

            if "error" in data:
                error_code = data.get('error', 'N/A')
                error_msg = f"API Error {error_code}: {service} - {data.get('reason', 'Unknown error')}"
                if service == "token/login":
                    raise WialonAuthError(error_msg)
                else:
                    raise WialonAPIError(error_msg)
            
            return data
        except requests.exceptions.RequestException as e:
            raise WialonRequestError(f"Error de conexión al llamar a {service}: {e}")
        except json.JSONDecodeError:
            raise WialonDataError(f"Error al decodificar la respuesta JSON de {service}: {response.text}")

    def login(self) -> str:
        """
        Inicia sesión en la API de Wialon y obtiene un Session ID (sid).
        El sid se guarda en la instancia del cliente.
        """
        print("Obteniendo SID...")
        data = self._call_api("token/login", {"token": self.token})
        
        if "eid" in data:
            self._sid = data["eid"]
            print(f"SID obtenido exitosamente: {self._sid}")
            return self._sid
        else:
            raise WialonAuthError("Respuesta inesperada al obtener SID: 'eid' no encontrado.")

    def logout(self):
        """
        Cierra la sesión actual de Wialon.
        """
        if self._sid:
            print("Cerrando sesión de Wialon...")
            try:
                self._call_api("core/logout", {})
                self._sid = None
                print("Sesión cerrada exitosamente.")
            except WialonAPIError as e:
                print(f"Advertencia: No se pudo cerrar la sesión: {e}")
        else:
            print("No hay sesión activa para cerrar.")

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
        print(f"Buscando unidades con máscara: '{unit_name_mask}'")

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
            print(f"Se encontraron {len(unidades)} unidades.")
            return unidades
        else:
            raise WialonDataError("Respuesta inesperada al buscar unidades: 'items' no encontrado.")

    def get_unit_mileage(self, item_id: int) -> float | None:
        """
        Obtiene el kilometraje (cnm_km) de una unidad específica.
        Retorna el kilometraje como un número flotante o None si no está disponible.
        """
        self.ensure_sid()
        print(f"Obteniendo kilometraje para ID: {item_id}")

        params_get_item = {
            "id": item_id,
            "flags": 8192 # Flag 8192 para obtener contadores (incluye cnm_km)
        }
        data = self._call_api("core/search_item", params_get_item)

        if "item" in data and "cnm_km" in data["item"]:
            kilometraje_api = data["item"]["cnm_km"]
            # Aquí podrías añadir tu lógica de conversión específica si es necesaria.
            # Por ejemplo, si sabes que Wialon a veces devuelve decímetros:
            # return float(kilometraje_api) / 10 if some_condition else float(kilometraje_api)
            print(f"  Kilometraje obtenido: {kilometraje_api} km")
            return float(kilometraje_api)
        else:
            print(f"  No se encontró 'cnm_km' para el ID {item_id}. Respuesta: {data.get('item', 'N/A')}")
            return None # Retorna None si el kilometraje no está en la respuesta

    def __del__(self):
        """
        Método destructor para cerrar la sesión al eliminar el objeto WialonClient.
        """
        self.logout()


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

    # Obtener el token de las variables de entorno (ahora cargadas desde .env)
    wialon_token = os.getenv("WIALON_TOKEN")

    if not wialon_token:
        print("Error: La variable de entorno 'WIALON_TOKEN' no está configurada.")
        print("Por favor, establece tu token de Wialon así:")
        print("  En Linux/macOS: export WIALON_TOKEN='TU_TOKEN_AQUI'")
        print("  En Windows (CMD): set WIALON_TOKEN='TU_TOKEN_AQUI'")
        print("  En Windows (PowerShell): $env:WIALON_TOKEN='TU_TOKEN_AQUI'")
        exit(1)

    try:
        # Crear una instancia del cliente Wialon
        client = WialonClient(wialon_token)

        nombre_unidad_mask = f"*{args.mat}*" if args.mat else "*"
        
        # Obtener unidades
        todas_mis_unidades = client.get_unit_ids(nombre_unidad_mask)

        if not todas_mis_unidades:
            print("No se encontraron unidades o hubo un error al obtenerlas.")
            exit(1)

        print("\n--- Obteniendo kilometraje de cada unidad ---")

        for unidad in todas_mis_unidades:
            print(f"\nProcesando unidad: {unidad['nombre']} (ID: {unidad['id']})")
            kilometraje = client.get_unit_mileage(unidad['id'])
            
            if kilometraje is not None:
                print(f"  Kilometraje actual: {kilometraje} km")
                # Aquí integrarías la actualización a tu base de datos
                # Por ejemplo: guardar_en_db(unidad['id'], kilometraje)
            else:
                print(f"  No se pudo obtener el kilometraje para esta unidad.")

    except WialonAuthError as e:
        print(f"Error de autenticación con Wialon: {e}")
        exit(1)
    except WialonRequestError as e:
        print(f"Error de conexión a la API de Wialon: {e}")
        exit(1)
    except WialonDataError as e:
        print(f"Error de datos de la API de Wialon: {e}")
        exit(1)
    except ValueError as e:
        print(f"Error de configuración: {e}")
        exit(1)
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")
        exit(1)
    finally:
        # Asegurarse de que la sesión se cierra, incluso si hay errores
        if 'client' in locals() and client._sid:
            client.logout()