"""HT5 — Arquitectura CENTRALIZADA.

Un único manager/supervisor recibe todos los mensajes del usuario y decide,
turno a turno, a cuál worker delegar la tarea llamándolo COMO HERRAMIENTA
(`Agent.as_tool()`). Los workers nunca hablan directo con el usuario ni
entre ellos: todo pasa por el manager.

    Usuario -> Manager -> [Agente FAQ | Agente de Citas y Clima] -> Manager -> Usuario

Ejecutar desde la raíz del repo:
    python -m hdt5.centralizada.main
"""

from __future__ import annotations

from dotenv import load_dotenv

from agents import Agent, Runner

from hdt5.shared.agents_factory import build_faq_agent, build_weather_agent
from hdt5.shared.faq_tool import prepare_faq_search
from hdt5.shared.model_config import get_model

MANAGER_INSTRUCTIONS = """
Eres el asistente virtual de Parachute S.A. Coordinas dos especialistas y
NUNCA respondes tú mismo con conocimiento propio:

- `consultar_faq`: para preguntas sobre servicios, políticas o información
  general de la empresa.
- `calendarizar_cita`: para agendar/consultar si una fecha es apta para
  saltar (revisa el clima).

Para cada mensaje del usuario, decide qué herramienta(s) llamar según la
intención, y luego redacta la respuesta final combinando lo que devolvieron.
Si el mensaje mezcla ambas cosas, llama a las dos herramientas necesarias.
Responde siempre en español.
""".strip()


def build_manager(model) -> Agent:
    faq_agent = build_faq_agent(model)
    weather_agent = build_weather_agent(model)

    return Agent(
        name="Manager Parachute S.A.",
        instructions=MANAGER_INSTRUCTIONS,
        model=model,
        tools=[
            faq_agent.as_tool(
                tool_name="consultar_faq",
                tool_description=(
                    "Delega en el especialista de FAQs cualquier pregunta "
                    "sobre servicios, precios, políticas o información "
                    "general de Parachute S.A."
                ),
            ),
            weather_agent.as_tool(
                tool_name="calendarizar_cita",
                tool_description=(
                    "Delega en el especialista de citas cualquier solicitud "
                    "de agendar o consultar si una fecha es apta para saltar."
                ),
            ),
        ],
    )


def main() -> None:
    load_dotenv()
    model = get_model()
    prepare_faq_search()
    manager = build_manager(model)

    print("=" * 70)
    print(" PARACHUTE S.A. — Arquitectura CENTRALIZADA")
    print("=" * 70)
    print("Escribe tu mensaje. Para salir escribe 'Bye' o presiona Ctrl-C.")
    print("-" * 70)

    historial = []
    while True:
        try:
            mensaje = input("\nTú: ").strip()
            if not mensaje:
                continue
            if mensaje.lower() == "bye":
                print("Agente: ¡Hasta luego!")
                break

            historial.append({"role": "user", "content": mensaje})
            resultado = Runner.run_sync(manager, historial)
            print(f"\nAgente: {resultado.final_output}")
            historial = resultado.to_input_list()

        except KeyboardInterrupt:
            print("\n\nAgente: ¡Hasta luego!")
            break
        except Exception as error:  # noqa: BLE001 — loop de demo, no debe morir
            print(f"\nAgente: Ocurrió un error: {error}")


if __name__ == "__main__":
    main()
