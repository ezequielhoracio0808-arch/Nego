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
| 💵 Buscar ingresos | Puede investigar en la web y **proponerte** ideas para generar dinero. Solo tú registras ingresos; el agente no puede subir su propio saldo. |
| 🔐 Riesgos de la autonomía | Constitución fija, aprobaciones, topes de gasto por ciclo y por día, registro de todo, sus comandos no ven tus claves, y pausa general. |

> **El agente nunca maneja dinero real.** Si necesita pagar algo, usa `solicitar_pago`: te llega la solicitud, y si la apruebas la pagas tú y se descuenta de su presupuesto.

---

## 📱 Desde el celular (sin computadora)

En el iPhone no puede vivir dentro del teléfono: iOS no deja que una app corra sin parar en segundo plano. Pero sí puedes tenerlo funcionando **y manejarlo 100 % desde el celular**: GitHub lo ejecuta gratis en sus servidores cada hora, y tú le hablas por Telegram o desde la app de GitHub.

Hazlo una sola vez, desde el navegador del celular en github.com (algunas pantallas de configuración no están en la app):

1. **Une estos cambios a `main`.** Crea un *pull request* desde la rama `claude/peaceful-keller-4f3pkn` (GitHub muestra el botón *Compare & pull request*) y haz *Merge*. GitHub solo ejecuta los flujos que están en `main`.
2. **Haz el repositorio privado:** *Settings → General → Danger Zone → Change visibility → Private*. Si sigue siendo público, el flujo se niega a ejecutarse: tus datos y lo que hace el agente quedarían a la vista de todos.
3. **Guarda tu clave:** *Settings → Secrets and variables → Actions → New repository secret*:
   - `ANTHROPIC_API_KEY` = tu clave de [console.anthropic.com](https://console.anthropic.com)
   - (opcional) `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` (ver más abajo cómo conseguirlos)
4. **Créalo:** pestaña *Actions → Automaton → Run workflow*, elige `iniciar` y escribe la misión en **texto**. Empieza con 5 USD de presupuesto.

Listo: desde ahí despierta solo cada hora. Para hablarle, en *Actions → Automaton → Run workflow* eliges:

| Acción | Texto | Qué hace |
|---|---|---|
| `despertar` | — | Un ciclo ahora mismo |
| `decir` | tu mensaje | Le deja el mensaje y lo despierta para que lo lea |
| `fondear` | `5` | Le agrega 5 USD |
| `pendientes` | — | Muestra lo que espera tu aprobación (míralo en el registro de la ejecución) |
| `aprobar` / `rechazar` | el id | Aprueba (y ejecuta) o rechaza |
| `estado` | — | Saldo y últimos movimientos |
| `pausar` / `reanudar` | — | Interruptor general |

Con Telegram configurado es más cómodo: te escribe él y tú le respondes con `/aprobar <id>`, `/fondear 5`, `/estado` o texto libre. Ojo: lo lee en la siguiente ejecución, así que puede tardar hasta una hora (o usa `despertar` para que sea al instante).

Su memoria, billetera y registros se guardan en la rama `automaton-datos` del repositorio.

Costos: el agente gasta de tu saldo de Anthropic como siempre (máx. 2 USD/día por defecto). GitHub da 2000 minutos gratis al mes para repositorios privados. Una revisión por hora usa unos 720 minutos al mes; los ciclos en que trabaja duran algo más. Si te acercas al límite, cambia el `cron` de `.github/workflows/automaton.yml` a cada 2 horas (`23 */2 * * *`).

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

# 4. Déjalo vivir: despierta cada hora (o cuando él decida) hasta que lo detengas con Ctrl+C
python -m automaton vivir
```

### Comandos para controlarlo

| Comando | Qué hace |
|---|---|
| `python -m automaton estado --movimientos 10` | Saldo, nivel, ciclos y últimos movimientos |
| `python -m automaton fondear 5` | Le agrega 5 USD de presupuesto |
| `python -m automaton ingreso 20 "vendí la laptop que encontró"` | Registra dinero que te ayudó a ganar (sube su saldo y se lo cuenta) |
| `python -m automaton decir "Enfócate en Lenovo"` | Le deja un mensaje; en modo `vivir` despierta antes para leerlo |
| `python -m automaton pendientes` | Lo que espera tu aprobación |
| `python -m automaton aprobar <id>` / `rechazar <id>` | Aprueba (y ejecuta) o rechaza |
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

Recibirás sus avisos en Telegram y podrás responder con `/estado`, `/pendientes`, `/aprobar <id>`, `/rechazar <id>`, `/fondear <usd>`, `/pausa`, `/reanudar`, o escribirle cualquier texto (lo despierta). Solo obedece a tu chat id.

## Configuración

Cada agente tiene su `datos/<nombre>/config.json`. Lo más importante:

| Clave | Por defecto | Para qué |
|---|---|---|
| `modelo` | `claude-opus-5-5` | Modelo de Claude |
| `esfuerzo` | normal `medium`, ahorro `low` | Cuánto razona según su saldo |
| `latido_minutos` | `60` | Cada cuánto despierta si no pidió otra cosa |
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
  ciclo.py          despertar (un ciclo), vivir (bucle + Telegram), chat
  herramientas.py   las 15 herramientas del agente (+ web_search / web_fetch del servidor)
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
