"""HT5 — Arquitectura JERÁRQUICA (persona 3).

Se pide AL MENOS 2 managers. La diferencia con la centralizada es que aquí
hay más de un nivel: un manager principal no llama directo a los workers,
sino a sub-managers, y esos sub-managers son quienes llaman (`as_tool()`) a
los workers reales.

Ejemplo de estructura sugerida (puedes ajustarla, con tal de tener 2+
managers reales):

    Usuario -> Manager Principal
                   |-- as_tool --> Sub-Manager "Información"
                   |                    |-- as_tool --> Agente FAQ
                   |
                   |-- as_tool --> Sub-Manager "Operaciones"
                                        |-- as_tool --> Agente de Citas y Clima

Con solo 2 workers esto es un poco artificial (podría hacerse en un solo
nivel), así que vale la pena justificarlo en el PDF: por ejemplo, agrupar
"Información" (hoy solo FAQ) y "Operaciones" (hoy solo citas) anticipa que
Parachute S.A. va a seguir pidiendo funcionalidades nuevas (ya lo advirtió),
y cada sub-manager podrá absorber los workers nuevos de su dominio sin que
el manager principal crezca.

TODO (persona 3):
1. Reutiliza `build_faq_agent` y `build_weather_agent` de
   `hdt5.shared.agents_factory` — no reimplementes sus tools.
2. Crea 2 sub-manager `Agent` (uno por dominio), cada uno con
   `tools=[worker.as_tool(...)]` de su dominio, igual que se hizo en
   `hdt5/centralizada/main.py` (revísalo como referencia de la sintaxis de
   `as_tool`).
3. Crea el manager principal con
   `tools=[sub_manager_1.as_tool(...), sub_manager_2.as_tool(...)]`.
4. Escribe las `instructions` de cada nivel: el manager principal debe
   saber que delega en sub-managers por dominio (no en los workers
   directamente), y cada sub-manager debe saber en qué worker(s) delegar.
5. El loop conversacional de abajo ya está listo — solo completa
   `build_manager_principal()`.

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


def build_manager_principal(model) -> Agent:
    faq_agent = build_faq_agent(model)
    weather_agent = build_weather_agent(model)

    # TODO: crear sub_manager_informacion (envuelve a faq_agent con as_tool)
    # sub_manager_informacion = Agent(
    #     name="Sub-Manager Información",
    #     instructions="...",
    #     model=model,
    #     tools=[faq_agent.as_tool(tool_name="consultar_faq", tool_description="...")],
    # )

    # TODO: crear sub_manager_operaciones (envuelve a weather_agent con as_tool)
    # sub_manager_operaciones = Agent(
    #     name="Sub-Manager Operaciones",
    #     instructions="...",
    #     model=model,
    #     tools=[weather_agent.as_tool(tool_name="calendarizar_cita", tool_description="...")],
    # )

    # TODO: crear el manager principal con
    # tools=[sub_manager_informacion.as_tool(...), sub_manager_operaciones.as_tool(...)]
    raise NotImplementedError("Completa los sub-managers y el manager principal (ver TODOs arriba).")


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
