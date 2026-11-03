"""Pruebas del MVP. Ejecutar con: python -m unittest -v"""
import unittest

from app import create_app
from nova.servicios import calcular_tarifa

ENVIO = {
    "remitente": "Camila Rodríguez",
    "origen": "Chapinero, Bogotá",
    "destino": "Suba, Bogotá",
    "tipo": "paquete",
    "peso_kg": 2.5,
}


class TestTarifa(unittest.TestCase):
    def test_documento_un_kilo(self):
        self.assertEqual(calcular_tarifa("documento", 1), 7000)

    def test_kilos_adicionales_se_redondean_hacia_arriba(self):
        # 2.5 kg -> 3 kg -> 2 kg adicionales: 10000 + 2 * 1200
        self.assertEqual(calcular_tarifa("paquete", 2.5), 12400)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.c = create_app().test_client()

    def crear(self):
        return self.c.post("/envios", json=ENVIO).get_json()

    def avanzar_hasta_en_ruta(self, envio_id):
        self.c.post(f"/envios/{envio_id}/pago", json={"metodo": "pse"})
        self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "asignado", "mensajero": "Carlos"})
        self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "en_ruta"})

    def test_salud(self):
        self.assertEqual(self.c.get("/salud").get_json()["estado"], "ok")

    def test_reserva_calcula_tarifa_y_estado_inicial(self):
        r = self.c.post("/envios", json=ENVIO)
        self.assertEqual(r.status_code, 201)
        datos = r.get_json()
        self.assertEqual(datos["id"], "NDT-0001")
        self.assertEqual(datos["estado"], "reservado")
        self.assertEqual(datos["tarifa"], 12400)

    def test_reserva_invalida(self):
        r = self.c.post("/envios", json={**ENVIO, "tipo": "cohete"})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/envios", json={**ENVIO, "peso_kg": -3})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/envios", json={})
        self.assertEqual(r.status_code, 422)

    def test_flujo_completo(self):
        envio_id = self.crear()["id"]
        self.assertEqual(self.c.post(f"/envios/{envio_id}/pago", json={"metodo": "pse"}).status_code, 200)
        r = self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "asignado", "mensajero": "Carlos"})
        self.assertEqual(r.get_json()["mensajero"], "Carlos")
        self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "en_ruta"})
        r = self.c.post(f"/envios/{envio_id}/ubicacion", json={"lat": 4.65, "lon": -74.06})
        self.assertEqual(r.get_json()["ubicacion"]["lat"], 4.65)
        r = self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "entregado", "recibido_por": "Laura"})
        self.assertEqual(r.get_json()["evidencia"]["recibido_por"], "Laura")
        r = self.c.post(f"/envios/{envio_id}/calificacion", json={"puntaje": 5})
        self.assertEqual(r.status_code, 201)
        seguimiento = self.c.get(f"/envios/{envio_id}").get_json()
        self.assertEqual(seguimiento["estado"], "entregado")
        self.assertGreaterEqual(len(seguimiento["historial"]), 6)

    def test_no_se_paga_dos_veces(self):
        envio_id = self.crear()["id"]
        self.c.post(f"/envios/{envio_id}/pago", json={"metodo": "tarjeta"})
        r = self.c.post(f"/envios/{envio_id}/pago", json={"metodo": "tarjeta"})
        self.assertEqual(r.status_code, 409)

    def test_transicion_invalida(self):
        envio_id = self.crear()["id"]
        r = self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "entregado", "recibido_por": "X"})
        self.assertEqual(r.status_code, 409)

    def test_entrega_exige_evidencia(self):
        envio_id = self.crear()["id"]
        self.avanzar_hasta_en_ruta(envio_id)
        r = self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "entregado"})
        self.assertEqual(r.status_code, 422)

    def test_ubicacion_solo_en_ruta(self):
        envio_id = self.crear()["id"]
        r = self.c.post(f"/envios/{envio_id}/ubicacion", json={"lat": 4.6, "lon": -74.0})
        self.assertEqual(r.status_code, 409)

    def test_coordenadas_fuera_de_rango(self):
        envio_id = self.crear()["id"]
        self.avanzar_hasta_en_ruta(envio_id)
        r = self.c.post(f"/envios/{envio_id}/ubicacion", json={"lat": 200, "lon": 0})
        self.assertEqual(r.status_code, 422)

    def test_calificacion_una_sola_vez_y_solo_entregado(self):
        envio_id = self.crear()["id"]
        self.assertEqual(self.c.post(f"/envios/{envio_id}/calificacion", json={"puntaje": 4}).status_code, 409)
        self.avanzar_hasta_en_ruta(envio_id)
        self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "entregado", "recibido_por": "Laura"})
        self.assertEqual(self.c.post(f"/envios/{envio_id}/calificacion", json={"puntaje": 9}).status_code, 422)
        self.assertEqual(self.c.post(f"/envios/{envio_id}/calificacion", json={"puntaje": 4}).status_code, 201)
        self.assertEqual(self.c.post(f"/envios/{envio_id}/calificacion", json={"puntaje": 5}).status_code, 409)

    def test_cancelar_antes_de_ir_en_ruta(self):
        envio_id = self.crear()["id"]
        r = self.c.patch(f"/envios/{envio_id}/estado", json={"estado": "cancelado"})
        self.assertEqual(r.get_json()["estado"], "cancelado")

    def test_envio_inexistente(self):
        self.assertEqual(self.c.get("/envios/NDT-9999").status_code, 404)

    def test_listar_con_filtros(self):
        self.crear()
        otro = self.c.post("/envios", json={**ENVIO, "tipo": "documento", "peso_kg": 0.2}).get_json()
        self.c.post(f"/envios/{otro['id']}/pago", json={"metodo": "billetera"})
        self.assertEqual(len(self.c.get("/envios").get_json()), 2)
        self.assertEqual(len(self.c.get("/envios?estado=pagado").get_json()), 1)
        self.assertEqual(len(self.c.get("/envios?tipo=paquete").get_json()), 1)

    def test_indicadores(self):
        a = self.crear()["id"]
        self.avanzar_hasta_en_ruta(a)
        self.c.patch(f"/envios/{a}/estado", json={"estado": "entregado", "recibido_por": "Laura"})
        self.c.post(f"/envios/{a}/calificacion", json={"puntaje": 5})
        self.crear()  # segundo envío sin pagar
        ind = self.c.get("/indicadores").get_json()
        self.assertEqual(ind["total_envios"], 2)
        self.assertEqual(ind["por_estado"], {"entregado": 1, "reservado": 1})
        self.assertEqual(ind["ingresos_cop"], 12400)
        self.assertEqual(ind["tasa_entrega"], 0.5)
        self.assertTrue(ind["metas"]["satisfaccion"]["cumple"])
        self.assertTrue(ind["metas"]["entrega_horas"]["cumple"])

    def test_indicadores_sin_datos(self):
        ind = self.c.get("/indicadores").get_json()
        self.assertEqual(ind["total_envios"], 0)
        self.assertIsNone(ind["tasa_entrega"])


if __name__ == "__main__":
    unittest.main()
