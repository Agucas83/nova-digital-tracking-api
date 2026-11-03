"""Lógica de negocio.

Aquí conviven dos paradigmas:
  * POO: el servicio y el modelo `Envio` encapsulan reglas y estado.
  * Funcional: tarifas e indicadores se calculan con funciones puras
    y con map, filter y reduce (sin modificar los datos originales).
"""
from datetime import datetime
from functools import reduce
from math import ceil

from .errores import ErrorNegocio, ErrorValidacion
from .modelos import Envio, Estado, ahora
from .repositorio import RepositorioEnvios

# Tarifas de ejemplo (supuesto del proyecto, no datos reales de Nova).
TARIFA_BASE = {"documento": 7000, "paquete": 10000, "mercancia": 15000}
COSTO_KG_ADICIONAL = 1200
METODOS_PAGO = {"tarjeta", "pse", "billetera"}

# Metas tomadas de la sustentación (diapositiva de indicadores).
META_SATISFACCION = 4.2
META_ENTREGA_HORAS = 24


# --------------------------- Funciones puras ---------------------------
def calcular_tarifa(tipo, peso_kg):
    """Tarifa base por tipo + kilos adicionales (cada kg redondeado hacia arriba)."""
    kilos_extra = max(0, ceil(peso_kg) - 1)
    return TARIFA_BASE[tipo] + kilos_extra * COSTO_KG_ADICIONAL


def promedio(valores):
    valores = list(valores)
    return round(sum(valores) / len(valores), 2) if valores else None


def horas_entre(inicio_iso, fin_iso):
    delta = datetime.fromisoformat(fin_iso) - datetime.fromisoformat(inicio_iso)
    return delta.total_seconds() / 3600


def calcular_indicadores(envios):
    """Indicadores del servicio usando map, filter y reduce."""
    total = len(envios)

    # reduce: cuenta de envíos por estado.
    por_estado = reduce(
        lambda acc, e: {**acc, e.estado.value: acc.get(e.estado.value, 0) + 1},
        envios,
        {},
    )

    # filter + map + sum: ingresos de envíos ya pagados y no cancelados.
    con_pago = filter(
        lambda e: e.estado not in (Estado.RESERVADO, Estado.CANCELADO), envios
    )
    ingresos = sum(map(lambda e: e.tarifa, con_pago))

    entregados = list(filter(lambda e: e.estado == Estado.ENTREGADO, envios))
    activos = total - por_estado.get(Estado.CANCELADO.value, 0)
    tasa_entrega = round(len(entregados) / activos, 2) if activos else None

    tiempo_entrega = promedio(
        map(lambda e: horas_entre(e.creado_en, e.entregado_en), entregados)
    )
    puntajes = map(
        lambda e: e.calificacion["puntaje"],
        filter(lambda e: e.calificacion is not None, envios),
    )
    satisfaccion = promedio(puntajes)

    return {
        "total_envios": total,
        "por_estado": por_estado,
        "ingresos_cop": ingresos,
        "tasa_entrega": tasa_entrega,
        "metas": {
            "entrega_horas": {
                "meta": META_ENTREGA_HORAS,
                "valor": tiempo_entrega,
                "cumple": None if tiempo_entrega is None else tiempo_entrega <= META_ENTREGA_HORAS,
            },
            "satisfaccion": {
                "meta": META_SATISFACCION,
                "valor": satisfaccion,
                "cumple": None if satisfaccion is None else satisfaccion >= META_SATISFACCION,
            },
        },
    }


# --------------------------- Validaciones ---------------------------
def _texto(datos, campo):
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorValidacion(f"El campo '{campo}' es obligatorio y debe ser texto")
    return valor.strip()


def _numero(valor, campo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorValidacion(f"El campo '{campo}' debe ser numérico")
    return valor


# --------------------------- Servicio (POO) ---------------------------
class ServicioEnvios:
    def __init__(self, repositorio=None):
        self.repo = repositorio or RepositorioEnvios()

    def reservar(self, datos):
        """RF-03: reserva de envío."""
        tipo = _texto(datos, "tipo").lower()
        if tipo not in TARIFA_BASE:
            raise ErrorValidacion(f"'tipo' debe ser uno de: {sorted(TARIFA_BASE)}")
        peso = _numero(datos.get("peso_kg"), "peso_kg")
        if peso <= 0 or peso > 50:
            raise ErrorValidacion("'peso_kg' debe estar entre 0 y 50")
        envio = Envio(
            id=self.repo.siguiente_id(),
            remitente=_texto(datos, "remitente"),
            origen=_texto(datos, "origen"),
            destino=_texto(datos, "destino"),
            tipo=tipo,
            peso_kg=peso,
            tarifa=calcular_tarifa(tipo, peso),
        )
        return self.repo.guardar(envio)

    def pagar(self, envio_id, datos):
        """RF-04: pago electrónico (simulado; no se almacenan datos de tarjeta)."""
        envio = self.repo.obtener(envio_id)
        metodo = _texto(datos, "metodo").lower()
        if metodo not in METODOS_PAGO:
            raise ErrorValidacion(f"'metodo' debe ser uno de: {sorted(METODOS_PAGO)}")
        self._transicion(envio, Estado.PAGADO)
        envio.metodo_pago = metodo
        envio.registrar(f"Pago confirmado por {metodo}: ${envio.tarifa:,} COP")
        return envio

    def cambiar_estado(self, envio_id, datos):
        """RF-09 y RF-10: avanzar o cancelar el envío."""
        envio = self.repo.obtener(envio_id)
        try:
            nuevo = Estado(_texto(datos, "estado").lower())
        except ValueError:
            raise ErrorValidacion(f"'estado' debe ser uno de: {[e.value for e in Estado]}")
        if nuevo == Estado.PAGADO:
            raise ErrorNegocio("El pago se registra en /envios/<id>/pago")

        if nuevo == Estado.ASIGNADO:
            mensajero = _texto(datos, "mensajero")
            self._transicion(envio, nuevo)
            envio.mensajero = mensajero
            envio.registrar(f"Asignado al mensajero {mensajero}")
        elif nuevo == Estado.ENTREGADO:
            recibido_por = _texto(datos, "recibido_por")  # RF-08: evidencia
            self._transicion(envio, nuevo)
            envio.entregado_en = ahora()
            envio.evidencia = {"recibido_por": recibido_por, "momento": envio.entregado_en}
            envio.registrar(f"Entregado a {recibido_por}")
        else:
            self._transicion(envio, nuevo)
            envio.registrar(f"Estado actualizado a {nuevo.value}")
        return envio

    def reportar_ubicacion(self, envio_id, datos):
        """RF-05: seguimiento GPS (solo mientras el envío va en ruta)."""
        envio = self.repo.obtener(envio_id)
        if envio.estado != Estado.EN_RUTA:
            raise ErrorNegocio("Solo se reporta ubicación de envíos en ruta")
        lat = _numero(datos.get("lat"), "lat")
        lon = _numero(datos.get("lon"), "lon")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ErrorValidacion("Coordenadas fuera de rango")
        envio.ubicacion = {"lat": lat, "lon": lon, "momento": ahora()}
        envio.registrar(f"Ubicación actualizada ({lat}, {lon})")
        return envio

    def calificar(self, envio_id, datos):
        """Calificación del servicio (una sola vez, solo si fue entregado)."""
        envio = self.repo.obtener(envio_id)
        if envio.estado != Estado.ENTREGADO:
            raise ErrorNegocio("Solo se califican envíos entregados")
        if envio.calificacion is not None:
            raise ErrorNegocio("Este envío ya fue calificado")
        puntaje = _numero(datos.get("puntaje"), "puntaje")
        if puntaje != int(puntaje) or not 1 <= puntaje <= 5:
            raise ErrorValidacion("'puntaje' debe ser un entero entre 1 y 5")
        envio.calificacion = {
            "puntaje": int(puntaje),
            "comentario": str(datos.get("comentario", ""))[:200],
        }
        envio.registrar(f"Calificado con {int(puntaje)}/5")
        return envio

    def listar(self, estado=None, tipo=None):
        """Lista con filtros opcionales (filter funcional)."""
        envios = self.repo.todos()
        if estado:
            envios = list(filter(lambda e: e.estado.value == estado, envios))
        if tipo:
            envios = list(filter(lambda e: e.tipo == tipo, envios))
        return envios

    def indicadores(self):
        return calcular_indicadores(self.repo.todos())

    @staticmethod
    def _transicion(envio, nuevo):
        if not envio.puede_pasar_a(nuevo):
            raise ErrorNegocio(
                f"No se puede pasar de '{envio.estado.value}' a '{nuevo.value}'"
            )
        envio.estado = nuevo
