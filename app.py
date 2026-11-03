"""Capa HTTP de Nova Digital Tracking (Flask). Solo traduce HTTP <-> servicio."""
from flask import Flask, jsonify, request

from nova.errores import ErrorNova
from nova.servicios import ServicioEnvios


def create_app(servicio=None):
    app = Flask(__name__)
    app.json.ensure_ascii = False  # tildes legibles en las respuestas JSON
    servicio = servicio or ServicioEnvios()

    def cuerpo():
        datos = request.get_json(silent=True)
        return datos if isinstance(datos, dict) else {}

    @app.errorhandler(ErrorNova)
    def manejar_error(error):
        return jsonify({"error": error.mensaje}), error.codigo_http

    @app.get("/salud")
    def salud():
        return jsonify({"servicio": "Nova Digital Tracking", "estado": "ok"})

    @app.post("/envios")
    def reservar():
        return jsonify(servicio.reservar(cuerpo()).a_dict()), 201

    @app.get("/envios")
    def listar():
        envios = servicio.listar(request.args.get("estado"), request.args.get("tipo"))
        return jsonify([e.a_dict() for e in envios])

    @app.get("/envios/<envio_id>")
    def seguimiento(envio_id):
        return jsonify(servicio.repo.obtener(envio_id).a_dict())

    @app.post("/envios/<envio_id>/pago")
    def pagar(envio_id):
        return jsonify(servicio.pagar(envio_id, cuerpo()).a_dict())

    @app.patch("/envios/<envio_id>/estado")
    def cambiar_estado(envio_id):
        return jsonify(servicio.cambiar_estado(envio_id, cuerpo()).a_dict())

    @app.post("/envios/<envio_id>/ubicacion")
    def ubicacion(envio_id):
        return jsonify(servicio.reportar_ubicacion(envio_id, cuerpo()).a_dict())

    @app.post("/envios/<envio_id>/calificacion")
    def calificar(envio_id):
        return jsonify(servicio.calificar(envio_id, cuerpo()).a_dict()), 201

    @app.get("/indicadores")
    def indicadores():
        return jsonify(servicio.indicadores())

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
