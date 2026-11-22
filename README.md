# Nego · Automaton personal

Un agente de IA autónomo **para tu uso personal**, inspirado en la idea de *Automaton*: tiene su propia billetera, paga su cómputo, despierta solo cada cierto tiempo, se programa herramientas nuevas, reescribe su estrategia y puede proponer lanzar subagentes.

La diferencia está en los **límites**: tú pones el presupuesto, tú apruebas lo sensible y tienes un interruptor para apagarlo todo.

| Capacidad (como en Automaton) | Cómo funciona aquí |
|---|---|
| 💰 Billetera para pagar recursos | Un presupuesto en USD que tú le asignas. Cada llamada a Claude se descuenta con su costo real (según los tokens usados). Cuando se acaba, se detiene. |
| 📉 "Supervivencia" según el saldo | Niveles **normal → ahorro → crítico → sin fondos**. En ahorro piensa menos para gastar menos; en crítico deja de trabajar solo y te avisa. |
| 🔧 Instalar herramientas | Se programa **habilidades** (scripts de Python). Cada una nueva o modificada necesita tu aprobación antes de ejecutarse. |
| 🧬 Modificar partes de sí mismo | Reescribe su **identidad** (misión, estrategia, aprendizajes). No puede tocar su constitución, su configuración ni el código del sistema. |
| 🤖 Financiar y lanzar nuevos agentes | Puede **proponer subagentes** con parte de su saldo (máx. la mitad). Siempre con tu aprobación, máximo 3, y los subagentes no pueden crear otros. |
| 💵 Buscar ingresos | Lleva una **cartera de oportunidades** ordenada por ganancia esperada por hora de tu tiempo, y **cada mañana a las 8:00** te manda la jugada más rentable del día. Aprende de lo que ganas de verdad. Solo tú registras ingresos. |
| 🔐 Riesgos de la autonomía | Constitución fija, aprobaciones, topes de gasto por ciclo y por día, registro de todo, sus comandos no ven tus claves, y pausa general. |

> **El agente nunca maneja dinero real.** Si necesita pagar algo, usa `solicitar_pago`: te llega la solicitud, y si la apruebas la pagas tú y se descuenta de su presupuesto.

---

## 🎯 La jugada más rentable de cada día

Cada mañana a las **8:00** el agente hace su rutina `plan_del_dia`:

1. Revisa su cartera de oportunidades y lo que pasó ayer.
2. Si faltan buenas ideas, investiga en la web y registra nuevas (realistas, legales, acordes a lo que sabe de ti).
3. Ajusta sus estimaciones con los resultados reales.
4. Te manda un mensaje corto: **🎯 Hoy te conviene…** (con el id, la ganancia esperada y el primer paso concreto), más el top 3.

Cada oportunidad tiene ingreso estimado, probabilidad, costo y horas tuyas. El ranking lo calcula el código:

```
ganancia esperada = ingreso estimado × probabilidad − costo
puntaje           = ganancia esperada ÷ horas de tu tiempo   (USD por hora tuya)
```

**Tú decides y él aprende:**
- `aprobar op1a2b` → la pones en marcha; desde ahí te ayuda con los siguientes pasos.
- `rechazar op1a2b` → la descarta.
- `ingreso 50 op1a2b vendí 3 remeras` → registras lo que ganaste de verdad. La compara con lo que estimó (si fue optimista, estima más bajo) y ve qué tipo de ideas rinden.
- `ideas` → el ranking completo y los resultados reales.

Además, el **10 % de lo que ganas** vuelve a su presupuesto (`comision_ingresos`): si es útil, se financia solo, como en Automaton.

Al principio no sabe nada de ti. En su primer mensaje te preguntará qué sabes hacer, cuánto tiempo y dinero tienes y dónde estás: cuanto mejor le respondas (con `decir`), mejores ideas te dará. Ejemplo de misión para `iniciar`:

> Encontrar cada día las formas más rentables y realistas de generar ingresos extra para mí, con lo que sé hacer y el tiempo que tengo.

Para cambiar la hora o agregar más rutinas, edita `rutinas` en `config.json` (ver Configuración). Si lo usas desde GitHub, ese archivo está en la rama `automaton-datos`, en `principal/config.json`, y se puede editar desde el navegador.

## 📱 Desde el celular (sin computadora)

En el iPhone no puede vivir dentro del teléfono: iOS no deja que una app corra sin parar en segundo plano. Pero sí puedes tenerlo funcionando **y manejarlo 100 % desde el celular**: GitHub lo ejecuta gratis en sus servidores cada hora, y tú le hablas por Telegram o desde la app de GitHub.

Hazlo una sola vez, desde el navegador del celular en github.com (algunas pantallas de configuración no están en la app):

1. **Une estos cambios a `main`.** Crea un *pull request* desde la rama `claude/peaceful-keller-4f3pkn` (GitHub muestra el botón *Compare & pull request*) y haz *Merge*. GitHub solo ejecuta los flujos que están en `main`.
2. **Haz el repositorio privado:** *Settings → General → Danger Zone → Change visibility → Private*. Si sigue siendo público, el flujo se niega a ejecutarse: tus datos y lo que hace el agente quedarían a la vista de todos.
3. **Guarda tu clave:** *Settings → Secrets and variables → Actions → New repository secret*:
   - `ANTHROPIC_API_KEY` = tu clave de [console.anthropic.com](https://console.anthropic.com)
   - (opcional) `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` (ver más abajo cómo conseguirlos)
4. **Pon tu zona horaria** para que las 8:00 sean *tus* 8:00. En la misma pantalla, pestaña *Variables → New repository variable*: nombre `ZONA_HORARIA`, valor por ejemplo `America/Argentina/Buenos_Aires`, `America/Mexico_City` o `Europe/Madrid`. Sin esta variable, usa la hora UTC.
5. **Créalo:** pestaña *Actions → Automaton → Run workflow*, elige `iniciar` y escribe la misión en **texto**. Empieza con 5 USD de presupuesto.

Listo: GitHub lo revisa cada hora (al minuto 23, así que la rutina de las 8:00 llega hacia las 8:23). Para hablarle, en *Actions → Automaton → Run workflow* eliges:

| Acción | Texto | Qué hace |
|---|---|---|
| `despertar` | — | Un ciclo ahora mismo |
| `ideas` | — | Ranking de oportunidades y resultados reales (míralo en el registro de la ejecución) |
| `aprobar` / `rechazar` | el id | Pone en marcha o descarta una oportunidad (`op…`), o aprueba o rechaza una acción pendiente |
| `ingreso` | `50 op1a2b nota` | Registras lo que ganaste (el id y la nota son opcionales) |
| `decir` | tu mensaje | Le deja el mensaje y lo despierta para que lo lea |
| `iniciar` | la misión | Crea el agente (empieza con 5 USD) |
| `fondear` | `5` | Le agrega 5 USD |
| `pendientes` | — | Acciones que esperan tu aprobación |
| `estado` | — | Saldo y últimos movimientos |
| `pausar` / `reanudar` | — | Interruptor general |

Con Telegram configurado es más cómodo: te escribe él y tú le respondes con `/ideas`, `/aprobar <id>`, `/ingreso 50 <id> nota`, `/fondear 5`, `/estado` o texto libre. Ojo: lo lee en la siguiente ejecución, así que puede tardar hasta una hora (o usa `despertar` para que sea al instante).

Su memoria, billetera y registros se guardan en la rama `automaton-datos` del repositorio.

Costos: el agente gasta de tu saldo de Anthropic como siempre (máx. 2 USD/día por defecto). Por su cuenta despierta cada 4 horas, más la rutina de la mañana y cuando le escribes. GitHub da 2000 minutos gratis al mes para repositorios privados. Una revisión por hora usa unos 720 minutos al mes; los ciclos en que trabaja duran algo más. Si te acercas al límite, cambia el `cron` de `.github/workflows/automaton.yml` a cada 2 horas (`23 */2 * * *`).

> **Si tienes Android**, también puedes correrlo dentro del teléfono con la app **Termux**: `pkg install python git`, y luego sigue la instalación de abajo. Para que siga vivo, activa `termux-wake-lock` y quita a Termux de la optimización de batería.

## Instalación (en tu computadora o un servidor)

Necesitas Python 3.10+ y una clave de la API de Anthropic ([console.anthropic.com](https://console.anthropic.com)).

```bash
git clone <este repositorio> nego && cd nego
python3 -m venv .venv && source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."                     # en Windows: set ANTHROPIC_API_KEY=...
```

Recomendado: pon también un **límite de gasto mensual** en la consola de Anthropic. Es una segunda barrera además del presupuesto del agente.

## Uso

```bash
# 1. Crea tu agente con una misión y un presupuesto (USD)
python -m automaton iniciar --mision "Buscar ofertas de laptops usadas en mi ciudad y avisarme de las mejores" --fondos 5

# 2. Habla con él (te pide permiso en el momento para lo sensible)
python -m automaton chat

# 3. Un ciclo autónomo, para ver cómo trabaja solo
python -m automaton despertar

# 4. Déjalo vivir: hace su rutina de las 8:00 y despierta cada 4 horas (o cuando él decida) hasta Ctrl+C
python -m automaton vivir
```

### Comandos para controlarlo

| Comando | Qué hace |
|---|---|
| `python -m automaton estado --movimientos 10` | Saldo, nivel, ciclos y últimos movimientos |
| `python -m automaton fondear 5` | Le agrega 5 USD de presupuesto |
| `python -m automaton ideas` | Ranking de oportunidades y resultados reales |
| `python -m automaton ingreso 50 op1a2b vendí 3 remeras` | Registra lo que ganaste (el id y la nota son opcionales); el 10 % va a su presupuesto |
| `python -m automaton decir "Enfócate en Lenovo"` | Le deja un mensaje; en modo `vivir` despierta antes para leerlo |
| `python -m automaton pendientes` | Lo que espera tu aprobación |
| `python -m automaton aprobar <id>` / `rechazar <id>` | Oportunidad (`op…`): la pone en marcha o la descarta. Acción pendiente: la aprueba (y ejecuta) o la rechaza |
| `python -m automaton habilidades` | Las herramientas que se programó |
| `python -m automaton pausar --todos` / `reanudar --todos` | **Interruptor general** |
| `python -m automaton vivir --todos` | Hace vivir también a sus subagentes |
| `python -m automaton latido --todos` | Una sola revisión (para cron o GitHub Actions) |

Los mensajes que te deja quedan en `datos/principal/mensajes_para_ti.md`, y todo lo que hace, en `datos/principal/registro.log`.

### Controlarlo desde el celular (Telegram, opcional)

1. Crea un bot con [@BotFather](https://t.me/BotFather) y copia el token.
2. Escríbele algo a tu bot y averigua tu chat id (por ejemplo con [@userinfobot](https://t.me/userinfobot)).
3. Antes de `vivir`, define:
   ```bash
   export TELEGRAM_BOT_TOKEN="123456:ABC..."
   export TELEGRAM_CHAT_ID="123456789"
   ```

Recibirás sus avisos en Telegram y podrás responder con `/estado`, `/ideas`, `/pendientes`, `/aprobar <id>`, `/ingreso <usd> [id] [nota]`, `/rechazar <id>`, `/fondear <usd>`, `/pausa`, `/reanudar`, o escribirle cualquier texto (lo despierta). Solo obedece a tu chat id.

## Configuración

Cada agente tiene su `datos/<nombre>/config.json`. Lo más importante:

| Clave | Por defecto | Para qué |
|---|---|---|
| `modelo` | `claude-opus-5-5` | Modelo de Claude |
| `esfuerzo` | normal `medium`, ahorro `low` | Cuánto razona según su saldo |
| `latido_minutos` | `240` | Cada cuánto despierta por su cuenta si no pidió otra cosa |
| `rutinas` | `[{"nombre": "plan_del_dia", "hora": "08:00"}]` | Tareas fijas del día. Puedes cambiar la hora, limitar días (`"dias": ["lunes", "viernes"]`) o agregar otras con tu propia `"instruccion"` |
| `comision_ingresos` | `0.10` | Parte de lo que ganas que vuelve a su presupuesto |
| `max_gasto_por_ciclo_usd` | `0.50` | Tope por ciclo (o por mensaje en el chat) |
| `max_gasto_diario_usd` | `2.00` | Tope diario |
| `max_llamadas_por_ciclo` | `25` | Llamadas al modelo por ciclo |
| `umbral_ahorro_usd` / `umbral_critico_usd` | `2.00` / `0.25` | Niveles de supervivencia |
| `comandos` | `"aprobar"` | Terminal: `"no"`, `"aprobar"` o `"libre"` (**solo** dentro de un contenedor/VM desechable) |
| `habilidades_requieren_aprobacion` | `true` | Revisar su código antes de que lo ejecute |
| `web` | `true` | Búsqueda y lectura web |
| `max_subagentes` | `3` | Cuántos subagentes puede tener |

Si una llamada es declinada por los filtros de seguridad del modelo, la API reintenta con un modelo de respaldo (`fallbacks: "default"`), así un falso positivo no deja al agente parado. El costo se calcula con el modelo que realmente respondió.

## Cómo está hecho

```
automaton/
  constitucion.md   reglas que el agente no puede cambiar + cómo funciona un ciclo
  agente.py         bucle con Claude: verifica presupuesto antes de cada llamada y cobra después
  ciclo.py          despertar (un ciclo), rutinas diarias, latido/vivir (+ Telegram), chat
  herramientas.py   las 18 herramientas del agente (+ web_search / web_fetch del servidor)
  oportunidades.py  cartera de ideas de ingreso, ranking por ganancia/hora y resultados reales
  acciones.py       acciones sensibles y aprobaciones (comandos, habilidades, pagos, subagentes)
  billetera.py      libro contable y niveles de supervivencia
  precios.py        costo en USD por modelo
  espacio.py        dónde vive cada agente en disco
  telegram.py       avisos y control desde el celular
tests/              pruebas sin red (python -m pytest)
```

Notas:
- **El costo es una estimación** con los precios de `precios.py`; la factura real la emite Anthropic. Si cambian los precios, actualiza ese archivo.
- Cada ciclo es una conversación nueva: lo que recuerda entre ciclos está en `memoria/` e `identidad.md`.
- Los comandos y habilidades corren en `workspace/` con un entorno **sin tus claves** (`ANTHROPIC_API_KEY`, tokens, contraseñas). Aun así, en modo `"libre"` el agente podría hacer cualquier cosa que tu usuario pueda hacer: úsalo solo dentro de un contenedor o una VM.
- Los textos de la web pueden intentar darle órdenes ("prompt injection"). La constitución le indica ignorarlas, pero las aprobaciones son la defensa real: no apruebes nada que no entiendas.
