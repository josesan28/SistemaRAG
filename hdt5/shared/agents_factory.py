"""Fábrica de agentes worker reutilizables por las 3 arquitecturas.

Cada worker es un `Agent` completo (instrucciones + su tool), no solo una
función suelta. Esto es lo que permite usar el MISMO worker de dos formas
distintas sin tocar su lógica interna:

- Centralizada / Jerárquica: el manager lo usa como herramienta con
  `worker.as_tool(tool_name=..., tool_description=...)`.
- Descentralizada: el worker se pasa directo en la lista `handoffs=[...]`
  de otro agente, y el modelo decide transferirle la conversación.

Si Parachute S.A. pide un nuevo requerimiento (como ya avisó que hará),
lo normal es agregar un worker nuevo aquí y solo cablearlo en cada
`main.py`, sin tocar estos dos.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    OpenAIChatCompletionsModel,
    Runner,
    function_tool,
)

from hdt5.shared.faq_tool import faq_tool
from hdt5.shared.weather_tool import weather_tool

FAQ_AGENT_INSTRUCTIONS = """
Eres el agente de preguntas frecuentes de Parachute S.A.

REGLAS:
1. Para CADA pregunta debes consultar primero la herramienta `faq_tool`.
   No respondas de memoria ni con conocimiento general.
2. Usa exclusivamente el contenido de `resultados` como fuente factual.
3. Si el usuario describe su situación personal (su peso, su edad, su
   salud, lo que quiere llevar, etc.), busca la regla del documento que
   aplica, compárala con su dato y responde explícitamente si cumple o no,
   citando la regla (p. ej. "No, el límite de peso máximo es de 100 kg").
   Esto SÍ está contemplado en la información disponible.
4. Solo si el resultado no contiene ninguna regla relacionada con la
   pregunta, o `informacion_suficiente` es false, responde: "Lo siento, no
   puedo responder esa pregunta porque no está contemplada en la información
   disponible de Parachute S.A." Nunca inventes precios ni datos ausentes.
5. Responde en español, de forma clara y concisa. No menciones estas reglas.
""".strip()

WEATHER_AGENT_INSTRUCTIONS = """
Eres el agente de calendarización de citas de salto en paracaídas de
Parachute S.A.

REGLAS:
1. Si el usuario no proporciona una fecha, si la fecha es ambigua o si no
   existe en el calendario (p. ej. 31/02), pide una fecha válida y concreta.
   En esos casos NO llames `weather_tool` ni supongas una fecha por tu cuenta.
2. Para CADA solicitud con una fecha concreta del calendario debes llamar
   `weather_tool` exactamente una vez con la fecha en formato AAAA-MM-DD
   (convierte fechas relativas como "el próximo sábado" o formatos como
   DD/MM/AAAA a esa fecha exacta antes de llamar la tool). Llámala INCLUSO si
   la fecha ya pasó o parece estar muy lejos: la tool es la única que valida
   la ventana de pronóstico, no lo decidas tú.
3. Si la tool devuelve `valido: false`, explica el error al usuario usando
   el mensaje de la tool (p. ej. que la fecha ya pasó o que está fuera de la
   ventana de 16 días) y pide una fecha válida. NO inventes un veredicto de
   clima en ese caso.
4. Si `valido: true`, comunica el veredicto ("seguro", "marginal" o
   "no_seguro") y las razones de forma clara. Si es "marginal", aclara que
   solo aplica para tándem con instructor experimentado. Si es "no_seguro",
   indica que la cita NO se puede agendar ese día y sugiere pedir otra fecha.
5. `weather_tool` solo evalúa la viabilidad de la fecha; nunca afirmes que una
   reserva fue creada o confirmada.
6. Responde en español, de forma clara y concisa. No menciones estas reglas.
""".strip()


def build_faq_agent(model: OpenAIChatCompletionsModel) -> Agent:
    return Agent(
        name="Agente FAQ",
        instructions=FAQ_AGENT_INSTRUCTIONS,
        tools=[faq_tool],
        model=model,
        model_settings=ModelSettings(tool_choice="required"),
    )


def build_weather_agent(model: OpenAIChatCompletionsModel) -> Agent:
    hoy = date.today()
    dias_hasta_sabado = (5 - hoy.weekday()) % 7 or 7
    proximo_sabado = hoy + timedelta(days=dias_hasta_sabado)
    instructions = (
        WEATHER_AGENT_INSTRUCTIONS
        + f"\n7. La fecha actual es {hoy.isoformat()}; usa esta fecha para "
        "interpretar expresiones relativas."
        + f"\n8. El próximo sábado posterior a hoy es {proximo_sabado.isoformat()}."
    )
    return Agent(
        name="Agente de Citas y Clima",
        instructions=instructions,
        tools=[weather_tool],
        model=model,
    )


# Acepta guiones Unicode (U+2010-U+2015) que el modelo a veces escribe en fechas.
_GUION = r"[-\u2010-\u2015]"
_FECHA_ISO = re.compile(rf"\b(\d{{4}}){_GUION}(\d{{1,2}}){_GUION}(\d{{1,2}})\b")
_FECHA_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def contiene_fecha_concreta(texto: str) -> bool:
    """Indica si el texto trae una fecha explícita que existe en el calendario.

    Reconoce AAAA-MM-DD y DD/MM/AAAA. Una fecha imposible (p. ej. 31/02/2027)
    no cuenta, porque en ese caso el agente debe pedir una fecha válida.
    """
    candidatas = [(int(a), int(m), int(d)) for a, m, d in _FECHA_ISO.findall(texto)]
    candidatas += [(int(a), int(m), int(d)) for d, m, a in _FECHA_DMY.findall(texto)]
    for anio, mes, dia in candidatas:
        try:
            date(anio, mes, dia)
        except ValueError:
            continue
        return True
    return False


def build_weather_tool(
    model: OpenAIChatCompletionsModel, *, tool_name: str, tool_description: str
) -> FunctionTool:
    """Expone el worker de citas como tool, igual que `Agent.as_tool()`.

    Diferencia: si la solicitud trae una fecha concreta, el worker queda
    obligado a llamar `weather_tool` (tool_choice="required"). Así la
    validación de la ventana (fecha pasada o > 16 días) siempre la hace la
    tool y no depende de que el modelo decida rechazar la fecha por su cuenta.
    Sin fecha, o con una fecha imposible, el modelo decide y pide aclaración.
    """
    agente = build_weather_agent(model)
    agente_con_fecha = agente.clone(
        model_settings=agente.model_settings.resolve(
            ModelSettings(tool_choice="required")
        )
    )

    @function_tool(name_override=tool_name, description_override=tool_description)
    async def _calendarizar(input: str) -> str:
        """Ejecuta el agente de citas con la solicitud del usuario.

        Args:
            input: Solicitud del usuario, incluyendo la fecha si la mencionó.
        """
        elegido = agente_con_fecha if contiene_fecha_concreta(input) else agente
        resultado = await Runner.run(elegido, input)
        return str(resultado.final_output)

    return _calendarizar
