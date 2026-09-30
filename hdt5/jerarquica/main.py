"""HT5 — Arquitectura JERÁRQUICA (persona 3).

El manager principal conserva la conversación con el usuario y solo delega a
sub-managers de dominio. Cada sub-manager llama como herramienta al worker que
posee la lógica del dominio; por lo tanto, el manager principal nunca invoca
workers ni integraciones directamente.

    Usuario -> Manager Principal
                   |-- as_tool --> Sub-Manager Información
                   |                    |-- as_tool --> Agente FAQ
                   |
                   |-- as_tool --> Sub-Manager Operaciones
                                        |-- as_tool --> Agente de Citas y Clima

Esta separación permite incorporar futuros workers de información u
operaciones sin ampliar las herramientas del manager principal.

Ejecutar desde la raíz del repo:
    python -m hdt5.jerarquica.main
"""

from __future__ import annotations

from dotenv import load_dotenv

from agents import Agent, Runner

from hdt5.shared.agents_factory import build_faq_agent, build_weather_agent
from hdt5.shared.console import configure_console
from hdt5.shared.faq_tool import prepare_faq_search
from hdt5.shared.model_config import get_model

MANAGER_PRINCIPAL_INSTRUCTIONS = """
Eres el manager principal y la única interfaz con el usuario de Parachute S.A.
Coordina sub-managers por dominio; no posees herramientas de FAQ ni de clima y
no debes responder usando conocimiento propio.

- `gestionar_informacion`: úsala para servicios, precios, políticas y cualquier
  información general de Parachute S.A.
- `gestionar_operaciones`: úsala para agendar una cita de salto o confirmar si
  una fecha es apta según el clima.

Para solicitudes que mezclen ambos dominios, llama a los dos sub-managers y
combina sus resultados. Redacta siempre la respuesta final en español.
""".strip()

INFORMACION_MANAGER_INSTRUCTIONS = """
Eres el sub-manager de Información de Parachute S.A. No hablas directamente
con el usuario: tu resultado vuelve al manager principal.

Para cada consulta de información general, servicios, precios o políticas,
llama a `resolver_faq`. No respondas con conocimiento propio ni intentes
calendarizar citas o consultar el clima. Devuelve al manager principal una
respuesta factual y concisa en español basada en el worker.
""".strip()

OPERACIONES_MANAGER_INSTRUCTIONS = """
Eres el sub-manager de Operaciones de Parachute S.A. No hablas directamente
con el usuario: tu resultado vuelve al manager principal.

Para cada petición de agendar una cita o saber si una fecha es apta para
saltar, llama a `evaluar_cita_y_clima`. No respondas con conocimiento propio
ni atiendas consultas generales de FAQ. Devuelve al manager principal una
respuesta clara y concisa en español basada en el worker.
""".strip()


def build_manager_principal(model) -> Agent:
    """Construye la jerarquía manager principal -> sub-managers -> workers."""
    faq_agent = build_faq_agent(model)
    weather_agent = build_weather_agent(model)

    sub_manager_informacion = Agent(
        name="Sub-Manager Información",
        instructions=INFORMACION_MANAGER_INSTRUCTIONS,
        model=model,
        tools=[
            faq_agent.as_tool(
                tool_name="resolver_faq",
                tool_description=(
                    "Consulta al worker de FAQs para responder preguntas sobre "
                    "servicios, precios, políticas e información general."
                ),
            )
        ],
    )
    sub_manager_operaciones = Agent(
        name="Sub-Manager Operaciones",
        instructions=OPERACIONES_MANAGER_INSTRUCTIONS,
        model=model,
        tools=[
            weather_agent.as_tool(
                tool_name="evaluar_cita_y_clima",
                tool_description=(
                    "Consulta al worker de citas y clima para evaluar si una "
                    "fecha de salto puede agendarse."
                ),
            )
        ],
    )

    return Agent(
        name="Manager Principal Parachute S.A.",
        instructions=MANAGER_PRINCIPAL_INSTRUCTIONS,
        model=model,
        tools=[
            sub_manager_informacion.as_tool(
                tool_name="gestionar_informacion",
                tool_description=(
                    "Delega en el sub-manager de Información las consultas "
                    "generales de Parachute S.A."
                ),
            ),
            sub_manager_operaciones.as_tool(
                tool_name="gestionar_operaciones",
                tool_description=(
                    "Delega en el sub-manager de Operaciones las solicitudes "
                    "de citas de salto y verificación de clima."
                ),
            ),
        ],
    )


def main() -> None:
    configure_console()
    load_dotenv()
    model = get_model()
    prepare_faq_search()
    manager = build_manager_principal(model)

    print("=" * 70)
    print(" PARACHUTE S.A. — Arquitectura JERÁRQUICA")
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
