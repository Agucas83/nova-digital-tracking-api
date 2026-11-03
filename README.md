# Nova Digital Tracking API

API REST para **reservar, pagar y rastrear envíos** de Nova Mensajería Digital S.A.S.
Es el MVP técnico de la sustentación *Nova Digital Tracking* (Envía, paga, rastrea y confía).

- **Autor:** Elxin Hair Agudelo Castro
- **Curso:** Lenguajes de última generación
- **Stack:** Python 3.12 o superior + Flask (sin base de datos externa en el MVP)

## 1. Qué resuelve

La operación de Nova es manual: reservas, pagos y seguimiento se hacen por llamadas y mensajes.
Esta API digitaliza el recorrido principal del usuario de la sustentación
(solicitud, pago, confirmación, GPS, entrega, calificación).

| Requisito de la sustentación | Dónde está en la API |
|---|---|
| RF-03 Reserva de envío | `POST /envios` |
| RF-04 Pago electrónico (simulado) | `POST /envios/{id}/pago` |
| RF-05 Seguimiento GPS | `POST /envios/{id}/ubicacion`, `GET /envios/{id}` |
| RF-08 Evidencia de entrega | `PATCH /envios/{id}/estado` con `recibido_por` |
| RF-09 Modificar/cancelar | `PATCH /envios/{id}/estado` con `cancelado` |
| RF-10 Notificaciones | Historial de eventos de cada envío (base para notificar) |
| Indicadores (satisfacción ≥ 4,2 y entrega ≤ 24 h) | `GET /indicadores` |

**Fuera del alcance del MVP:** login y 2FA, pasarela de pago real, GPS real, optimización de rutas con IA y persistencia en base de datos.

## 2. Cómo ejecutarlo

```bash
git clone https://github.com/Agucas83/nova-digital-tracking-api.git
cd nova-digital-tracking-api
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # API en http://localhost:5000
```

Pruebas automáticas (17 pruebas):

```bash
python -m unittest -v
```

## 3. Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/salud` | Verifica que el servicio está activo |
| POST | `/envios` | Reserva un envío y calcula la tarifa |
| GET | `/envios` | Lista envíos (filtros opcionales `?estado=` y `?tipo=`) |
| GET | `/envios/{id}` | Seguimiento: estado, ubicación e historial |
| POST | `/envios/{id}/pago` | Registra el pago (`tarjeta`, `pse` o `billetera`) |
| PATCH | `/envios/{id}/estado` | Asigna mensajero, pone en ruta, entrega o cancela |
| POST | `/envios/{id}/ubicacion` | Reporta coordenadas (solo si está `en_ruta`) |
| POST | `/envios/{id}/calificacion` | Califica de 1 a 5 (solo si fue entregado) |
| GET | `/indicadores` | Total, envíos por estado, ingresos, tasa de entrega y metas |

### Ciclo de vida de un envío

```
reservado -> pagado -> asignado -> en_ruta -> entregado
    |           |          |
    +-----------+----------+--> cancelado
```

Los cambios fuera de este esquema devuelven `409`. Los datos inválidos devuelven `422`.

### Ejemplo de uso

```bash
# 1. Reservar
curl -X POST localhost:5000/envios -H "Content-Type: application/json" \
  -d '{"remitente":"Camila Rodríguez","origen":"Chapinero","destino":"Suba","tipo":"paquete","peso_kg":2.5}'

# 2. Pagar
curl -X POST localhost:5000/envios/NDT-0001/pago -H "Content-Type: application/json" \
  -d '{"metodo":"pse"}'

# 3. Asignar mensajero y poner en ruta
curl -X PATCH localhost:5000/envios/NDT-0001/estado -H "Content-Type: application/json" \
  -d '{"estado":"asignado","mensajero":"Carlos"}'
curl -X PATCH localhost:5000/envios/NDT-0001/estado -H "Content-Type: application/json" \
  -d '{"estado":"en_ruta"}'

# 4. Reportar ubicación y consultar seguimiento
curl -X POST localhost:5000/envios/NDT-0001/ubicacion -H "Content-Type: application/json" \
  -d '{"lat":4.65,"lon":-74.06}'
curl localhost:5000/envios/NDT-0001

# 5. Entregar, calificar y ver indicadores
curl -X PATCH localhost:5000/envios/NDT-0001/estado -H "Content-Type: application/json" \
  -d '{"estado":"entregado","recibido_por":"Laura"}'
curl -X POST localhost:5000/envios/NDT-0001/calificacion -H "Content-Type: application/json" \
  -d '{"puntaje":5}'
curl localhost:5000/indicadores
```

Tarifas de ejemplo (supuesto del proyecto, no datos reales de Nova):
documento $7.000, paquete $10.000, mercancía $15.000, más $1.200 por cada kg adicional (se redondea hacia arriba).

## 4. Estructura

```
app.py                  Capa HTTP (rutas y manejo de errores)
nova/
  modelos.py            Envio, Estado y máquina de estados (POO)
  servicios.py          Reglas de negocio, tarifas e indicadores
  repositorio.py        Almacenamiento en memoria (reemplazable)
  errores.py            Errores de dominio (404, 409, 422)
tests/test_api.py       17 pruebas automáticas
```

La separación en capas (HTTP, servicio, repositorio) permite cambiar el almacenamiento o el framework sin reescribir las reglas de negocio.

## 5. Paradigmas utilizados

**Programación orientada a objetos** (`nova/modelos.py`, `nova/servicios.py`):
la clase `Envio` encapsula su estado y su historial; `ServicioEnvios` encapsula las reglas;
`RepositorioEnvios` encapsula el almacenamiento. Se usan enumeraciones (`Estado`) y errores propios con herencia.

**Programación funcional** (`nova/servicios.py`):
- `calcular_tarifa`: función pura, sin efectos secundarios.
- `calcular_indicadores`: usa `reduce` (conteo por estado), `filter` (selección de envíos pagados, entregados o calificados) y `map` (extraer tarifas, tiempos y puntajes). No modifica los datos originales.
- `listar`: aplica `filter` para los filtros de la consulta.

## 6. Justificación tecnológica

| Criterio | Python + Flask (elegido) | Kotlin + Ktor | Rust + Axum |
|---|---|---|---|
| Curva de aprendizaje | Baja | Media | Alta |
| Velocidad para construir el MVP | Alta | Media | Baja |
| Rendimiento bruto | Menor (interpretado) | Alto (JVM) | Muy alto (nativo, sin recolector de basura) |
| Seguridad de tipos | Opcional (anotaciones) | Fuerte | Muy fuerte |

**Decisión:** Python + Flask, por velocidad de desarrollo y curva de aprendizaje baja, que importan más en un MVP.
La carga estimada en la sustentación es de unos 1.000 envíos mensuales como mínimo de equilibrio, un volumen que Python maneja sin problema.
En este MVP no se midió rendimiento.

**Contexto de mercado** (ver radar de lenguajes 2026):
Python lidera el índice TIOBE de octubre 2026 (19,23%), aunque cede 5,23 puntos frente a octubre 2025;
Rust es #10 (1,44%) y el lenguaje más admirado de la encuesta de Stack Overflow 2025 (72%);
Kotlin es #20 en TIOBE (enero 2026) y Android es *Kotlin-first* desde 2019.

**Ruta de evolución:** si el volumen crece, la capa de servicio puede migrarse a Kotlin (Ktor) o Rust (Axum) conservando el contrato de la API. Para el seguimiento en tiempo real a gran escala, Elixir sería un candidato por su modelo de concurrencia.

## 7. Limitaciones y siguientes pasos

1. Persistencia real (SQLite o PostgreSQL) en lugar de memoria.
2. Autenticación (JWT) y 2FA.
3. Integración con una pasarela de pago real. Nunca se almacenan datos de tarjeta.
4. Cumplimiento de la Ley 1581 de 2012 (consentimiento, acceso y eliminación de datos).
5. Contenerización con Docker y despliegue.
