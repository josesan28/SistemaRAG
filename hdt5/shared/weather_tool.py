"""Tool de clima/citas para Parachute S.A. (Open-Meteo).

Contiene TODA la lógica de negocio nueva de la HT5: llamar a Open-Meteo,
validar la ventana de 16 días y aplicar los criterios de seguridad. Las 3
arquitecturas importan `calendarizar_cita` (o el Agent que la envuelve, ver
`agents_factory.py`) y no deben duplicar ninguno de estos criterios.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import requests
from agents import function_tool

LANDING_LAT = 14.013722
LANDING_LON = -90.771611
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS_LIMIT = 16

DAILY_VARS = [
    "wind_gusts_10m_max",
    "temperature_2m_max",
    "precipitation_sum",
    "cloud_cover_mean",
    "wind_speed_10m_max",
]


def _parse_fecha(fecha: str) -> date:
    try:
        return datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError(
            f"Formato de fecha inválido: '{fecha}'. Usa AAAA-MM-DD."
        ) from error


def _validar_ventana(
    fecha_solicitada: date, hoy: date | None = None
) -> dict[str, Any] | None:
    """Devuelve un dict de error si la fecha está fuera de rango; si no, None."""
    hoy = hoy or date.today()
    # Open-Meteo cuenta hoy como el primer día de los 16 disponibles.
    limite = hoy + timedelta(days=FORECAST_DAYS_LIMIT - 1)

    if fecha_solicitada < hoy:
        return {
            "valido": False,
            "error": (
                f"La fecha {fecha_solicitada.isoformat()} ya pasó. Elige una "
                "fecha de hoy en adelante."
            ),
        }
    if fecha_solicitada > limite:
        return {
            "valido": False,
            "error": (
                f"Open-Meteo solo da una ventana de {FORECAST_DAYS_LIMIT} días "
                f"incluyendo hoy (hasta {limite.isoformat()}). No se puede calendarizar "
                f"la cita para el {fecha_solicitada.isoformat()}; pide una fecha "
                f"dentro de ese rango."
            ),
        }
    return None


def _clasificar(datos: dict[str, float]) -> dict[str, Any]:
    """Aplica los criterios de seguridad de Parachute S.A. sobre un día."""
    viento = datos["wind_speed_10m"]
    rafaga = datos["wind_gust_10m"]
    precipitacion = datos["precipitation"]
    nubosidad = datos["cloud_cover"]

    razones: list[str] = []
    veredicto = "seguro"  # seguro | marginal | no_seguro

    def _peor(actual: str, nuevo: str) -> str:
        orden = {"seguro": 0, "marginal": 1, "no_seguro": 2}
        return nuevo if orden[nuevo] > orden[actual] else actual

    # Viento en superficie
    if viento > 28:
        veredicto = _peor(veredicto, "no_seguro")
        razones.append(f"viento en superficie {viento:.1f} km/h (> 28 km/h)")
    elif viento >= 20:
        veredicto = _peor(veredicto, "marginal")
        razones.append(
            f"viento en superficie {viento:.1f} km/h (20-28 km/h, "
            "solo tándem experimentado)"
        )

    # Ráfagas
    if rafaga > 35:
        veredicto = _peor(veredicto, "no_seguro")
        razones.append(f"ráfagas de {rafaga:.1f} km/h (> 35 km/h)")

    # Precipitación
    if precipitacion > 0.0:
        veredicto = _peor(veredicto, "no_seguro")
        razones.append(f"precipitación de {precipitacion:.1f} mm (> 0.0 mm)")

    # Cobertura de nubes / visibilidad
    if nubosidad > 75:
        veredicto = _peor(veredicto, "no_seguro")
        razones.append(f"cobertura de nubes {nubosidad:.0f}% (> 75%)")
    elif nubosidad >= 30:
        veredicto = _peor(veredicto, "marginal")
        razones.append(f"cobertura de nubes {nubosidad:.0f}% (30-75%, nubes dispersas)")

    if not razones:
        razones.append("todas las variables dentro de rango ideal")

    return {"veredicto": veredicto, "razones": razones}


def _fetch_open_meteo(fecha: date) -> dict[str, float]:
    """Consulta Open-Meteo con `daily=` para la fecha pedida.

    Usamos `daily` (no `current`) porque el usuario pide una fecha futura de
    hasta 16 días, no el clima de este instante.
    """
    params = {
        "latitude": LANDING_LAT,
        "longitude": LANDING_LON,
        "daily": ",".join(DAILY_VARS),
        "timezone": "America/Guatemala",
        "start_date": fecha.isoformat(),
        "end_date": fecha.isoformat(),
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()

    daily = payload.get("daily", {})
    if not daily.get("time"):
        raise RuntimeError("Open-Meteo no devolvió datos para esa fecha.")

    variable_map = {
        "wind_gust_10m": "wind_gusts_10m_max",
        "temperature_2m": "temperature_2m_max",
        "precipitation": "precipitation_sum",
        "cloud_cover": "cloud_cover_mean",
        "wind_speed_10m": "wind_speed_10m_max",
    }
    datos: dict[str, float] = {}
    for nombre_publico, nombre_api in variable_map.items():
        try:
            valor = daily[nombre_api][0]
            if valor is None:
                raise ValueError
            datos[nombre_publico] = float(valor)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError(
                f"Open-Meteo no devolvió un valor válido para {nombre_api}."
            ) from error
    return datos


def _weather_tool_impl(fecha: str) -> dict[str, Any]:
    """Evalúa si una fecha es apta para saltar en paracaídas según el clima.

    Args:
        fecha: Fecha deseada por el usuario en formato AAAA-MM-DD. Open-Meteo
            solo da pronóstico hasta 16 días a futuro; si el usuario pide una
            fecha más lejana, esta tool devuelve el error correspondiente en
            vez de una predicción.
    """
    try:
        fecha_solicitada = _parse_fecha(fecha)
    except ValueError as error:
        return {"valido": False, "error": str(error)}

    error_ventana = _validar_ventana(fecha_solicitada)
    if error_ventana is not None:
        return error_ventana

    try:
        datos = _fetch_open_meteo(fecha_solicitada)
    except (requests.RequestException, RuntimeError) as error:
        return {
            "valido": False,
            "error": f"No fue posible consultar Open-Meteo: {error}",
        }
    clasificacion = _clasificar(datos)

    return {
        "valido": True,
        "fecha": fecha_solicitada.isoformat(),
        "coordenadas": {"lat": LANDING_LAT, "lon": LANDING_LON},
        "datos": datos,
        "veredicto": clasificacion["veredicto"],
        "razones": clasificacion["razones"],
    }


@function_tool
def weather_tool(fecha: str) -> dict[str, Any]:
    """Evalúa si una fecha es apta para saltar según el clima.

    Args:
        fecha: Fecha deseada en formato AAAA-MM-DD.
    """
    return _weather_tool_impl(fecha)


# Alias temporal para no romper imports escritos antes de acordar la interfaz.
calendarizar_cita = weather_tool
