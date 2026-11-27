# Datos con Cara: cómo hacer un short nuevo

Canal de Shorts animados de curiosidades. **El protagonista del dato lo cuenta él mismo, con cara**
(el pulpo explica sus tres corazones, Venus presume de su día eterno...). Humor blanco, datos verdaderos.

## Cuando el usuario pida un short ("hazme uno sobre X", "dame ideas")
1. Si pide ideas: propone 5 con un gancho de una línea cada una e indica qué personajes existen ya.
2. **Comprueba el dato** antes de escribir (fuentes fiables). Si es dudoso, suavízalo ("unos", "miles de")
   o descártalo. Nada de mitos (no usamos el 10 % del cerebro, etc.).
3. Escribe `guiones/NN-slug.json` (siguiente número libre). Copia la forma de `guiones/01-pulpo-tres-corazones.json`.
4. Si falta un personaje, dibújalo en `tools/personajes.py` (ver abajo) y revisa `python3 tools/animar.py reparto`.
5. Prueba fotogramas: `python3 tools/animar.py prueba NN 3` → `salida/prueba-NN-3.png`. Míralos.
6. Renderiza: `python3 tools/animar.py render NN` → `videos-listos/NN-slug.mp4`, `-portada.jpg` y `.txt`.
7. Revisa una tira de fotogramas del vídeo final (ffmpeg `fps=2/3,scale=270:480,tile=10x2`).

## Reglas del guion
- 6 a 9 escenas, **20–35 s**. Gancho en la primera frase (el dato más sorprendente, en 1.ª persona).
- Una frase por escena, corta. El último remate es un chiste y lleva `"sfx": [["badumtss", "fin"]], "pausa": 0.9`
  (o `trompeta`, la trompetilla triste, si el chiste es de alguien que sale perdiendo).
- Diálogo entre 2 personajes como máximo a la vez; Chispa (`bombilla`) hace de espectador curioso.
- `*palabra*` resalta en amarillo en subtítulos y rótulos. Rótulos: 1–4 palabras en MAYÚSCULAS.
- Números: escríbelos con cifras (Piper los lee bien). Pronunciaciones raras: añádelas a `PRON` en `animar.py`.

## Formato de escena
```json
{
  "habla": "pulpo",                       // clave del actor que habla (mueve la boca, su tono de voz)
  "texto": "Tengo *tres corazones*.",     // lo que dice (subtítulos + voz)
  "rotulo": "*3* CORAZONES",              // opcional; "|" fuerza salto de línea; "rotulo_color": "#hex"
  "actores": {
    "pulpo": {"x": 0.5, "y": 0.56, "s": 1.2, "cara": "feliz"},
    "corazon#2": {"x": 0.8, "y": 0.3, "s": 0.34, "retraso": "60%", "entra": "cae", "accion": "latir"}
  },
  "fx": [{"tipo": "corazones", "en": "pulpo", "retraso": "70%"}],
  "sfx": [["ding", "40%"], ["badumtss", "fin"]],
  "camara": "temblor",                    // o "zoom"
  "pausa": 0.5,                           // segundos extra al final de la escena
  "fondo": "mar", "color": "#7AD957"      // opcional: cambia el fondo (hace transición de barrido)
}
```
- Actor: clave = nombre del personaje; `#2`, `#3`… para repetir el mismo. Si el actor sigue en la escena
  siguiente, se desliza a su nueva posición; si desaparece, se encoge; si es nuevo, entra.
- `x`, `y` = centro en fracción de pantalla. Zona útil: `y` 0.45–0.62 (arriba van rótulos, abajo subtítulos
  y la interfaz de YouTube). Uno solo: `s` 1.0–1.25. Dos: `x` 0.28 / 0.72, `s` 0.6–0.9.
- `cara`: feliz, presumido, sorprendido, asustado, enfadado, triste, pensativo, dormido, neutro.
- `entra`: pop (defecto), izq, der, cae, aparece. `accion`: girar, saltar, temblar, latir, crecer, encoger
  (`accion_en`: segundos desde que entra, o "NN%" de la frase). `mira`: izq, der, arriba, abajo, centro
  (si no, mira a quien habla). `gris`: 0–1 (desatura; cambia en `gris_en`, p. ej. "60%"). `texto`: para calendario y cartel.
  `espejo`: true lo voltea.
- Tiempos (`retraso`, `accion_en`, `sfx`, `rotulo_en`): número = segundos desde el inicio de la escena;
  `"60%"` = en ese punto de la frase (para sincronizar con la palabra clave); `"fin"` = al acabar la frase.
- `fx`: corazones, brillos, interrogacion, exclamacion, sudor, confeti, zzz, resplandor (`color`).
- `sfx`: pop, pop2, whoosh, boing, ding, brillo, tada, subida, bajada, giro, brr, latido, gota, golpe,
  badumtss (remate de chiste), trompeta (trompetilla triste).
  Las entradas, acciones, rótulos y fx ya suenan solos; añade `sfx` solo para gags.
- Fondos: rayos y lunares (con `color`), espacio, mar, desierto, campo, laguna.

## Personajes (tools/personajes.py)
bombilla (Chispa, mascota), pulpo, corazon, gota, venus, tierra, sol, calendario (texto), cartel (texto),
platano, tarro, abeja, piramide, flamenco, gamba.

Para añadir uno: función `p_nombre(L, fase, texto, boca)` que dibuje en un lienzo de 600×600 con
`L.ellipse / L.circle / L.poly / L.tube / L.rrect / L.stroke / L.texto` (colores planos, contorno
`INK`, deja ~30 u de margen) y regístralo en `PERSONAJES` con `cara=(x, y, escala)` (centro de la
cara; los ojos ocupan ±80·escala), `piel` (color bajo los párpados), `suelo`/`pie`, `voz` (tono) y
`fases` si se anima. Los detalles semitransparentes van en `L.capa()` + `L.encima()`; lo que deba quedar
dentro de una silueta, con `L.recorta(capa, mascara)`.

## Voz
Por defecto Piper (`PIPER_VOICE`, voz es_ES-davefx). Si existe `pon-aqui-tu-voz/NN.mp3|wav|m4a`, se usa ese
audio y se reparte entre escenas por los silencios. `python3 tools/animar.py guion NN` imprime el texto para ElevenLabs.
