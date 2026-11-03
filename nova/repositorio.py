"""Repositorio en memoria. Aísla el almacenamiento del resto del sistema,
de modo que luego puede cambiarse por SQLite o PostgreSQL sin tocar la lógica."""
from threading import Lock

from .errores import NoEncontrado


class RepositorioEnvios:
    def __init__(self):
        self._envios = {}
        self._contador = 0
        self._candado = Lock()  # evita ids repetidos con peticiones simultáneas

    def siguiente_id(self):
        with self._candado:
            self._contador += 1
            return f"NDT-{self._contador:04d}"

    def guardar(self, envio):
        self._envios[envio.id] = envio
        return envio

    def obtener(self, envio_id):
        try:
            return self._envios[envio_id]
        except KeyError:
            raise NoEncontrado(f"No existe el envío {envio_id}")

    def todos(self):
        return list(self._envios.values())
