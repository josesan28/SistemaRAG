"""Capa compartida de HT5: modelo (Groq vía Agents SDK) y tools reutilizables
por las 3 arquitecturas (centralizada, jerárquica, descentralizada).

Nadie debe reimplementar la lógica de clima o de FAQ dentro de cada
arquitectura: todas importan `get_model()`, `faq_agent_tool()` y
`weather_agent_tool()` desde aquí. Así, cambiar un criterio de seguridad o
el umbral del RAG se hace en un solo lugar.
"""
