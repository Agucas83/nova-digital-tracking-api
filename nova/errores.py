"""Errores de dominio. La capa HTTP los convierte en respuestas JSON."""


class ErrorNova(Exception):
    """Base de los errores controlados de la API."""
    codigo_http = 400

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


class ErrorValidacion(ErrorNova):
    """Los datos enviados por el cliente no son válidos."""
    codigo_http = 422


class NoEncontrado(ErrorNova):
    """El envío solicitado no existe."""
    codigo_http = 404


class ErrorNegocio(ErrorNova):
    """La operación no está permitida en el estado actual del envío."""
    codigo_http = 409
