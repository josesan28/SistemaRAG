"""Capa compartida de HT5: modelo (Groq vía Agents SDK) y tools reutilizables
por las 3 arquitecturas (centralizada, jerárquica, descentralizada).

La interfaz acordada es `faq_tool(query)` y `weather_tool(fecha)`. Los workers
reutilizables se construyen con `build_faq_agent()` y `build_weather_agent()`.
Ninguna arquitectura debe duplicar la lógica de integración o de seguridad.
"""

from hdt5.shared.faq_tool import faq_tool, prepare_faq_search
from hdt5.shared.weather_tool import weather_tool

__all__ = ["faq_tool", "prepare_faq_search", "weather_tool"]
