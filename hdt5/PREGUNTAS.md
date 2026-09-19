# Respuestas — HT5 Orquestación

## 1. ¿Qué arquitectura(s) resuelve(n) mejor este problema? ¿Por qué?

Para los requisitos actuales, la arquitectura **centralizada** es la que mejor
equilibra simplicidad, control y mantenibilidad. Solo existen dos dominios:
información de FAQs y calendarización con clima. Un único manager puede
clasificar la intención, invocar el worker adecuado mediante `as_tool()` y
combinar ambas respuestas si el usuario pregunta, por ejemplo, por un servicio
y por la disponibilidad de una fecha. El manager mantiene una única respuesta
final, por lo que es fácil validar qué tools se llamaron y evitar que un worker
responda fuera de su especialidad.

La arquitectura **jerárquica** es la mejor alternativa si el crecimiento que
anticipa Parachute S.A. se concreta. El manager principal solo conoce los
dominios de Información y Operaciones; cada sub-manager conoce sus workers.
Así, un nuevo worker —por ejemplo, pagos, logística, disponibilidad de
instructores o mantenimiento— se incorpora al sub-manager correspondiente sin
sobrecargar ni modificar el enrutamiento del manager principal. Su costo hoy
es mayor complejidad, latencia y llamadas al modelo para solo dos workers, por
lo que no es la opción más eficiente para el alcance actual.

La arquitectura **descentralizada** también funciona, pero es menos adecuada
en este caso. Los `handoffs` son valiosos cuando un especialista debe tomar
control de una conversación larga. Aquí predominan consultas acotadas y pueden
existir solicitudes mixtas; transferir el control entre agentes vuelve más
difícil coordinar ambos dominios y mantener una respuesta unificada. Por ello,
elegimos centralizada para el presente y jerárquica como diseño preparado para
la expansión.

## 2. ¿Es necesario utilizar un sistema multiagente en este caso? ¿Por qué?

No es estrictamente necesario con el alcance actual. Un único agente con las
dos function tools (`faq_tool` y `weather_tool`) puede consultar la base de
conocimiento, validar la fecha de hasta 16 días, llamar a Open-Meteo y aplicar
los criterios de seguridad. Esa alternativa tendría menos prompts, menor
latencia, menor costo y una depuración más simple.

Sin embargo, el sistema multiagente está justificado como decisión de diseño y
como parte del objetivo de la actividad. Los workers encapsulan reglas
distintas: el agente FAQ solo usa información recuperada, mientras que el de
citas interpreta fechas y evalúa condiciones meteorológicas. Esta separación
reduce el acoplamiento, permite probar cada integración de manera aislada y
facilita añadir nuevos dominios sin reescribir la lógica existente. En resumen,
un solo agente basta hoy; la organización multiagente aporta valor cuando la
cantidad de funciones, reglas o equipos responsables aumente.
