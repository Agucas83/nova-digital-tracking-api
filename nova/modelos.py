"""Modelos del dominio (paradigma orientado a objetos)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def ahora():
    """Marca de tiempo UTC en formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class Estado(str, Enum):
    RESERVADO = "reservado"
    PAGADO = "pagado"
    ASIGNADO = "asignado"
    EN_RUTA = "en_ruta"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"


# Máquina de estados: qué cambios están permitidos desde cada estado.
TRANSICIONES = {
    Estado.RESERVADO: {Estado.PAGADO, Estado.CANCELADO},
    Estado.PAGADO: {Estado.ASIGNADO, Estado.CANCELADO},
    Estado.ASIGNADO: {Estado.EN_RUTA, Estado.CANCELADO},
    Estado.EN_RUTA: {Estado.ENTREGADO},
    Estado.ENTREGADO: set(),
    Estado.CANCELADO: set(),
}


@dataclass
class Envio:
    id: str
    remitente: str
    origen: str
    destino: str
    tipo: str
    peso_kg: float
    tarifa: int
    estado: Estado = Estado.RESERVADO
    creado_en: str = field(default_factory=ahora)
    entregado_en: str | None = None
    mensajero: str | None = None
    metodo_pago: str | None = None
    ubicacion: dict | None = None
    evidencia: dict | None = None
    calificacion: dict | None = None
    historial: list = field(default_factory=list)

    def __post_init__(self):
        if not self.historial:
            self.registrar("Envío reservado")

    def registrar(self, detalle):
        """Agrega un evento al historial (trazabilidad del envío)."""
        self.historial.append(
            {"momento": ahora(), "estado": self.estado.value, "detalle": detalle}
        )

    def puede_pasar_a(self, nuevo):
        return nuevo in TRANSICIONES[self.estado]

    def a_dict(self):
        return {
            "id": self.id,
            "remitente": self.remitente,
            "origen": self.origen,
            "destino": self.destino,
            "tipo": self.tipo,
            "peso_kg": self.peso_kg,
            "tarifa": self.tarifa,
            "estado": self.estado.value,
            "creado_en": self.creado_en,
            "entregado_en": self.entregado_en,
            "mensajero": self.mensajero,
            "metodo_pago": self.metodo_pago,
            "ubicacion": self.ubicacion,
            "evidencia": self.evidencia,
            "calificacion": self.calificacion,
            "historial": self.historial,
        }
