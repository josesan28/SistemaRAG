# Borrador de respuestas (HT5) — completar juntos al final

No es el entregable en sí (ese va en PDF), es para dejar ideas mientras cada
quien termina su arquitectura. Editen libremente.

## 1. ¿Qué arquitectura(s) resuelve(n) mejor este problema? ¿Por qué?

Puntos a favor de **centralizada** para este caso concreto:
- Solo hay 2 dominios (FAQ y citas/clima) que no dependen entre sí dentro de
  una misma solicitud del usuario — no hace falta que un worker le pase
  contexto a otro, así que la coordinación de un solo manager alcanza.
- Es la más simple de razonar, depurar y mantener con 2 workers.

Puntos a favor de **jerárquica** pensando en el futuro:
- Parachute S.A. avisó que van a seguir agregando requerimientos. Si crece
  a 5-6 dominios, un solo manager con 6 tools se vuelve difícil de
  mantener; agrupar por sub-manager (p. ej. "Información" vs
  "Operaciones") escala mejor.
- Hoy, con solo 2 workers, es más estructura de la que el problema necesita.

**Descentralizada** encaja peor aquí: los handoffs brillan cuando el
usuario necesita que la conversación completa "viva" con un especialista
por un rato (p. ej. soporte técnico largo), no cuando cada mensaje es una
consulta independiente de un dominio u otro. Además, sin un punto central,
es más fácil que ningún agente sepa cuándo transferir si el usuario mezcla
temas en un mismo mensaje.

_(Completar con lo que observen al probar las 3 implementaciones — esto es
solo el punto de partida.)_

## 2. ¿Es necesario un sistema multiagente en este caso? ¿Por qué?

Argumento en contra: con 2 tools y sin dependencias entre ellas, un solo
agente con ambas tools (sin ningún framework de multiagentes) probablemente
resuelve el problema igual de bien — el "sistema multiagente" agrega
complejidad de infraestructura sin necesidad real cuando los dominios no
requieren especialización profunda ni aislamiento de contexto.

Argumento a favor: al ser un requisito de la universidad (y una apuesta de
Parachute S.A. a que seguirán creciendo los requerimientos), separar en
agentes desde ahora facilita escalar sin reescribir la arquitectura cuando
aparezcan más dominios con lógica más compleja cada uno.

_(Definan su postura real como equipo — las 2 arquitecturas que implementen
mejor deberían justificar la respuesta que den aquí.)_
