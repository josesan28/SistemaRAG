"""HT5 — Arquitectura DESCENTRALIZADA (persona 2).

No hay un manager central: el usuario empieza hablando con un agente y, si
la petición no es su especialidad, ESE agente decide transferir la
conversación completa a otro usando `handoffs=[...]`. El control pasa de
agente en agente; el que responde al final es el que tiene el turno.

    Usuario -> Agente A --(handoff)--> Agente B -> Usuario
                  ^                         |
                  |------(handoff)----------|

TODO (persona 2):
1. Reutiliza `build_faq_agent` y `build_weather_agent` de
   `hdt5.shared.agents_factory` (NO reescribas su lógica de tools).
2. Dale a cada uno un `handoffs=[el_otro]` para que puedan transferirse la
   conversación entre sí cuando el usuario cambia de tema. En el Agents SDK
   los handoffs se asignan después de crear ambos agentes, ej.:

       faq_agent = build_faq_agent(model)
       weather_agent = build_weather_agent(model)
       faq_agent.handoffs = [weather_agent]
       weather_agent.handoffs = [faq_agent]

3. Decide con cuál de los dos arranca la conversación (el "entry point" del
   handoff). Puede ser cualquiera de los dos, o un tercer agente triage muy
   simple (sin tools propias) que solo decide a quién transferir al inicio
   —si hacen esto último, sigue siendo descentralizado mientras ese triage
   no sea un supervisor que llama a los otros como *tools* (eso sería
   centralizado).
4. Ajusta las instrucciones de cada agente para que sepan que pueden
   transferir la conversación (el SDK ya expone esto automáticamente al
   modelo cuando hay `handoffs`, pero ayuda mencionarlo).
5. El loop conversacional de abajo ya está listo — solo completa
   `build_agentes()`.

Ejecutar desde la raíz del repo:
    python -m hdt5.descentralizada.main
"""

from __future__ import annotations

from dotenv import load_dotenv

from agents import Runner

from hdt5.shared.agents_factory import build_faq_agent, build_weather_agent
from hdt5.shared.console import configure_console
from hdt5.shared.faq_tool import prepare_faq_search
from hdt5.shared.model_config import get_model


def build_agentes(model):
    """Devuelve el agente inicial y los especialistas disponibles."""
    faq_agent = build_faq_agent(model)
    weather_agent = build_weather_agent(model)

    faq_agent.instructions += (
        "\n5. Si el usuario solicita agendar una cita o consultar el clima "
        "para una fecha de salto, transfiere la conversación al Agente de "
        "Citas y Clima. No intentes responder esa solicitud con `faq_tool`."
    )
    faq_agent.handoffs = [weather_agent]

    agente_inicial = faq_agent
    return agente_inicial, [faq_agent, weather_agent]


def main() -> None:
    configure_console()
    load_dotenv()
    model = get_model()
    prepare_faq_search()
    agente_actual, _ = build_agentes(model)

    print("=" * 70)
    print(" PARACHUTE S.A. — Arquitectura DESCENTRALIZADA")
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
            resultado = Runner.run_sync(agente_actual, historial)
            print(f"\n[{resultado.last_agent.name}]: {resultado.final_output}")
            historial = resultado.to_input_list()
            # El siguiente turno arranca desde el agente que quedó con el
            # control tras el handoff (o el mismo si no hubo transferencia).
            agente_actual = resultado.last_agent

        except KeyboardInterrupt:
            print("\n\nAgente: ¡Hasta luego!")
            break
        except Exception as error:  # noqa: BLE001 — loop de demo, no debe morir
            print(f"\nAgente: Ocurrió un error: {error}")


if __name__ == "__main__":
    main()
