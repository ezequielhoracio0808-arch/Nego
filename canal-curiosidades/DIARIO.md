# Vídeo diario de «Dato Oculto»: procedimiento

Lo sigue cada mañana la sesión programada de Claude (y cualquiera que quiera hacerlo a mano).
Resultado: un vídeo horizontal de 3–4 min + un Short de menos de 60 s, con miniaturas y textos listos para subir.

## 0. Preparar
```bash
cd canal-curiosidades
FECHA=$(TZ=Europe/Madrid date +%F)
ls guiones/$FECHA-* 2>/dev/null && echo "YA HAY VÍDEO HOY"   # si ya existe, para aquí: no hagas otro
python3 -c "import piper" 2>/dev/null || pip install piper-tts
```
La voz (`es_ES-davefx-medium`) se descarga sola en `~/.cache/piper-voces/` si no está.

## 1. Investigar qué funciona
```bash
python3 tools/investigar.py        # -> investigacion/$FECHA.md (+ .json)
```
- **Con API de YouTube** (código 0): lee el informe. Fíjate sobre todo en la columna **× canal** (visitas ÷ suscriptores):
  si un canal pequeño tiene un vídeo con muchas visitas, lo que funcionó es **el tema y el título**. Busca 2–3 temas
  que se repitan o que destaquen, y mira qué formato tienen los títulos y miniaturas que ganan.
- **Con el conector de vidIQ** (herramientas `vidiq_*`), úsalo antes que las búsquedas web: da visitas reales.
  El plan tiene **150 créditos al mes** y cada consulta gasta 5, así que:
  1. Mira el saldo con `vidiq_balance`, que es gratis. Si quedan menos de 30 créditos, no gastes y pasa a las búsquedas web.
  2. Haz **una sola consulta**, alternando por días:
     - días pares: `vidiq_outliers` (`contentType` short, `language` es, `publishedWithin` thisMonth) con la categoría que toque;
     - días impares: `vidiq_trending_videos` (`videoFormat` short, `videoTitleLanguage` es, `sortBy` recentVph,
       `titleQuery` «curiosidades datos curiosos sabías que», los últimos 14 días).
  3. Apunta en `investigacion/$FECHA.md` los 5 mejores (título, canal, suscriptores, visitas, × canal) y lo que copias del
     formato. No copies las granjas de «Por favor comparte…» (interacción por debajo del 1 %).
  Lo que ya se sabe está en `investigacion/2026-11-27-vidiq.md`: funcionan los lugares prohibidos en serie numerada,
  los «¿Sabías que…?» de animales y las búsquedas «lugares prohibidos del mundo» (+45 %) y «… que no puedes visitar» (+81 %).
- **Sin API ni vidIQ** (código 2): investiga con búsquedas web (4–6 búsquedas): temas de curiosidades virales esta semana,
  efemérides de hoy («un día como hoy» + la fecha), descubrimientos científicos o noticias raras de los últimos días y
  qué han publicado los grandes canales de curiosidades en español. Apunta lo que encuentres al final de `investigacion/$FECHA.md`.

**Elegir el tema.** Debe cumplir todo esto:
1. Tiene demanda demostrada: vídeos parecidos con muchas visitas, o una noticia o efeméride de la que se habla ahora.
2. **No está en `historial.json`**. Varía la categoría a lo largo de la semana: lugares, historia, ciencia, animales, misterios, inventos, cuerpo humano, récords.
3. Se puede verificar con fuentes fiables y hay fotos libres en Commons (compruébalo con `tools/imagenes.py --buscar`).
4. Ángulo propio: coge el **tema**, nunca el guion ni el título de otro canal.
5. Nada de consejos de salud, bulos o conspiraciones presentados como ciertos, personas privadas vivas, tragedias recientes ni política.

## 2. Verificar los datos
Cada dato del guion tiene que estar respaldado por **dos fuentes fiables** como mínimo: museos, organismos oficiales,
artículos científicos, enciclopedias o grandes medios. Si las fuentes no coinciden, usa «unos», «según…» o quita el dato.
Si algo es leyenda, dilo («no hay ninguna ley que…»). **No inventes cifras.** Guarda entre 3 y 6 enlaces en `fuentes`.

## 3. Escribir el guion: `guiones/$FECHA-<slug>.json`
Copia la estructura de un guion anterior (por ejemplo `guiones/2026-11-27-longyearbyen.json`). Los campos:

| Campo | Regla |
|---|---|
| `tema`, `por_que` | Qué es y por qué se eligió (con los datos de la investigación) |
| `titulo` | ≤ 70 caracteres, honesto (el vídeo cumple lo que promete), con 1–3 palabras clave en MAYÚSCULAS |
| `miniatura` | 2 líneas de ≤ 14 caracteres que **complementen** el título, no que lo repitan |
| `miniatura_imagen` | Índice de la escena cuya foto va en la miniatura (la más impactante) |
| `descripcion` | 2–3 frases con las palabras que buscaría la gente |
| `etiquetas` (8–12), `hashtags` (3) | En español y en minúsculas |
| `pron` | Pronunciación para la voz: `{"Longyearbyen": "Long yir bien"}` (los subtítulos usan el texto original) |
| `fuentes` | `[{"titulo": …, "url": …}]` |
| `escenas` | **11–14 escenas, 520–680 palabras en total** (3–4 min) |
| `short` | `titulo` (con #shorts), `gancho` (2 líneas), `descripcion`, `escenas`: **4–6, 90–140 palabras** (menos de 55 s) |

Cada escena tiene `titulo` (en pantalla, MAYÚSCULAS, ≤ 28 caracteres), `capitulo` (texto del capítulo en YouTube),
`narracion` (35–60 palabras, una sola idea) e `imagen`. Opcionalmente lleva `cifra`, un número o frase corta
(≤ 12 caracteres) que aparece en grande.

**Estilo:** español de España, frases cortas, tono de conversación, sin relleno.
- **Escena 1 = gancho** (menos de 15 s): el dato más sorprendente y una promesa («quédate hasta el final porque…»). Cumple la promesa.
- Mete una pregunta o un giro cada 3–4 escenas para que la gente no se vaya.
- **Última escena:** pregunta para los comentarios y «suscríbete a Dato Oculto: cada día, una curiosidad nueva».
- Short: la primera frase engancha sola y la última es una pregunta. Los Shorts que se ven en bucle funcionan mejor.
- Números: los años en cifras (1950); las cantidades grandes, mejor en palabras. Sin abreviaturas (km → kilómetros).

**Imágenes** (`imagen`): mejor un archivo exacto de Commons (`"File:Nombre.jpg"`), elegido con
`python3 tools/imagenes.py --buscar "longyearbyen cemetery"`. También vale una búsqueda corta en inglés, de 2 o 3 palabras.
`"@fondo"` es el fondo de la marca, útil para una cifra. Una escena sin `imagen` reutiliza la de la anterior.
Usa fotos distintas en cada escena siempre que puedas.

## 4. Imágenes
```bash
python3 tools/imagenes.py $FECHA
```
Abre `trabajo/<id>/contacto.jpg` y **mira todas las fotos**: ¿cuadra cada foto con lo que dice su escena? ¿Hay alguna
borrosa, con marcas de agua o con personas en primer plano? Para cambiar una, edita su `imagen` o usa `--forzar h3 s1`
(h = vídeo, s = Short) y repite el comando. Solo se aceptan licencias que permiten uso comercial y modificación;
la atribución va sola a la descripción y a la esquina del vídeo. Si Commons responde «429» (demasiadas peticiones),
el script espera y reintenta. Si sigue fallando, reutiliza fotos ya descargadas.

## 5. Producir
```bash
python3 tools/producir.py $FECHA      # 8-10 minutos (ejecútalo en segundo plano si hace falta)
```
Revisa `trabajo/<id>/fotogramas.jpg` y `salida/<id>/miniatura.jpg`: que el texto se lea, que ninguna imagen sea un
error y que la miniatura llame la atención. El vídeo debe durar entre 2:30 y 4:30 y el Short, menos de 60 s (si no, el script avisa).
Si cambias algo, `--solo video|short|miniatura|textos` regenera solo esa parte.

## 6. Entregar
```bash
cd .. && git add canal-curiosidades && git commit -m "Vídeo diario $FECHA: <título>" && git push -u origin <rama>
```
Los `.mp4` no van a git (los excluye `.gitignore`). Se entregan con **SendUserFile** (`status: proactive`):
`video.mp4`, `short.mp4` y `miniatura.jpg`. Termina con un resumen breve en español:
- el tema y **por qué** se eligió (cifras de la investigación),
- el título,
- qué revisar antes de subir (pronunciación de nombres raros y cualquier dato con matices),
- cuándo publicar: el vídeo entre las **17:00 y las 19:00** (hora de España) y el Short 2–3 horas después,
  o el Short por la mañana para atraer gente al vídeo.
