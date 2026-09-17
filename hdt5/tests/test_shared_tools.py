from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from hdt5.shared.faq_tool import _faq_tool_impl, prepare_faq_search
from hdt5.shared.weather_tool import (
    FORECAST_DAYS_LIMIT,
    _clasificar,
    _validar_ventana,
    _weather_tool_impl,
)


class FaqToolTests(unittest.TestCase):
    def test_recupera_documento_de_hdt4(self) -> None:
        resultado = _faq_tool_impl("¿Cuál es el peso máximo?")

        self.assertTrue(resultado["valido"])
        self.assertIn("100 kg", resultado["resultados"])
        self.assertEqual(resultado["resultados"], prepare_faq_search())

    def test_rechaza_consulta_vacia(self) -> None:
        resultado = _faq_tool_impl("   ")

        self.assertFalse(resultado["valido"])
        self.assertFalse(resultado["informacion_suficiente"])


class WeatherToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hoy = date(2026, 9, 16)

    def test_ventana_incluye_exactamente_16_dias(self) -> None:
        ultimo_dia = self.hoy + timedelta(days=FORECAST_DAYS_LIMIT - 1)

        self.assertIsNone(_validar_ventana(ultimo_dia, self.hoy))
        self.assertIsNotNone(
            _validar_ventana(ultimo_dia + timedelta(days=1), self.hoy)
        )

    def test_limites_marginales_son_inclusivos(self) -> None:
        resultado = _clasificar(
            {
                "wind_speed_10m": 28.0,
                "wind_gust_10m": 35.0,
                "precipitation": 0.0,
                "cloud_cover": 75.0,
                "temperature_2m": 24.0,
            }
        )

        self.assertEqual(resultado["veredicto"], "marginal")

    def test_cualquier_prohibicion_domina_el_veredicto(self) -> None:
        casos = (
            {"wind_speed_10m": 28.1, "wind_gust_10m": 0, "precipitation": 0, "cloud_cover": 0},
            {"wind_speed_10m": 0, "wind_gust_10m": 35.1, "precipitation": 0, "cloud_cover": 0},
            {"wind_speed_10m": 0, "wind_gust_10m": 0, "precipitation": 0.1, "cloud_cover": 0},
            {"wind_speed_10m": 0, "wind_gust_10m": 0, "precipitation": 0, "cloud_cover": 75.1},
        )

        for datos in casos:
            datos["temperature_2m"] = 24.0
            with self.subTest(datos=datos):
                self.assertEqual(_clasificar(datos)["veredicto"], "no_seguro")

    @patch("hdt5.shared.weather_tool._fetch_open_meteo")
    def test_respuesta_exitosa_tiene_contrato_estable(self, fetch_mock) -> None:
        fetch_mock.return_value = {
            "wind_speed_10m": 10.0,
            "wind_gust_10m": 15.0,
            "precipitation": 0.0,
            "cloud_cover": 20.0,
            "temperature_2m": 26.0,
        }
        fecha = date.today().isoformat()

        resultado = _weather_tool_impl(fecha)

        self.assertTrue(resultado["valido"])
        self.assertEqual(resultado["veredicto"], "seguro")
        self.assertEqual(resultado["fecha"], fecha)
        self.assertEqual(
            set(resultado["datos"]),
            {
                "wind_gust_10m",
                "temperature_2m",
                "precipitation",
                "cloud_cover",
                "wind_speed_10m",
            },
        )

    def test_fecha_invalida_no_consulta_api(self) -> None:
        with patch("hdt5.shared.weather_tool._fetch_open_meteo") as fetch_mock:
            resultado = _weather_tool_impl("16/09/2026")

        self.assertFalse(resultado["valido"])
        fetch_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
