# Vídeo diario de «Dato Oculto»: procedimiento

Lo sigue cada mañana la sesión programada de Claude (y cualquiera que quiera hacerlo a mano).
Resultado: un vídeo horizontal de **8–10 min** + un Short de menos de 60 s, con miniaturas y textos listos para subir.
**Los domingos**, en lugar del vídeo nuevo, se hace la **recopilación semanal** de 25–30 min (ver el final) y un Short nuevo.

¿Por qué 8–10 min? Para monetizar, YouTube pide 1.000 suscriptores y **4.000 horas vistas en vídeos largos** (las de los
Shorts no cuentan). Además, a partir de 8 minutos se pueden poner anuncios a mitad del vídeo. Los Shorts siguen: traen
suscriptores y llevan gente a los vídeos largos.

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
  El plan tiene **150 créditos al mes** y cada consulta gasta 5. **El análisis de tus propios vídeos (paso 1b) va primero.**
  1. Mira el saldo con `vidiq_balance`, que es gratis. Investiga con vidIQ **solo los días impares** y solo si quedan
     40 créditos o más. Si no, usa las búsquedas web.
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

## 1b. Analizar las visitas de lo publicado y aprender
1. **Enlaces.** En `publicaciones.json`, a cada vídeo con `estado: "programado"` y sin `url`, ponle la `postUrl` que
   devuelve `vidiq_social_post_status` con su `vidiq_post`.
2. **Datos.** Hazlo los **días pares** (o si han pasado 2 días desde el último análisis) y solo si hay algún vídeo
   publicado hace 48 h o más. Llama una vez a `vidiq_channel_analytics`, que gasta 5 créditos:
   - `channelId`: el de `publicaciones.json`; `dimensions`: `["video"]`; `startDate`: 2026-11-27; `endDate`: hoy; `maxResults`: 200;
   - `metrics`: `views, engagedViews, averageViewPercentage, averageViewDuration, likes, comments, shares, subscribersGained`.

   Guarda la respuesta tal cual en `trabajo/analitica-$FECHA.json`. Después:
   `python3 tools/rendimiento.py importar trabajo/analitica-$FECHA.json && python3 tools/rendimiento.py informe`.
3. **Conclusiones.** Lee el informe y actualiza `aprendizajes.md`: la receta, las pruebas y una fila nueva en el historial.
   Sigue sus normas: cambia una regla solo si el patrón se repite (2 vídeos o más por lado y una diferencia del 30 % o más).
   Si no, apúntalo como indicio. Fíjate también en lo concreto: qué temas, ganchos y títulos tienen los 3 mejores y los
   3 peores Shorts, y qué tienen en común.
4. **Aplicarlo.** El tema, el gancho, el título y la duración de hoy siguen la receta de `aprendizajes.md`, salvo el día
   de prueba (1 de cada 3), que cambia una sola cosa. Pon en el guion `"categoria"` y, el día de prueba,
   `"prueba": "<qué se prueba>"`. Si un Short ya aprobado pero sin subir va claramente en contra de lo aprendido
   (por ejemplo, por el título), propón el cambio al usuario. Cambiar un borrador obliga a pedirle otro «sí».

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
**Formato del vídeo: una lista de 5 a 7 elementos del mismo tema** («7 lugares donde…», «6 animales que…»), como
`guiones/2026-11-27-11-lugares.json`. Es lo que mejor funciona en curiosidades y deja un capítulo por elemento:
- **Intro (2 escenas):** el gancho, en menos de 15 s, con lo mejor de la lista («…y el número uno ni siquiera te dejan
  pisarlo»), y una promesa.
- **Cada elemento (3–4 escenas):** la primera lleva `titulo` (nombre y país), `cifra` (`"#7"`) y `capitulo`
  (`"7. Nombre: idea"`); las demás, sin `titulo`. De menos a más sorprendente.
- **Cierre (1 escena):** pregunta para los comentarios y suscripción.
- Si un elemento ya salió en otro vídeo (`historial.json`), cuéntalo desde otro ángulo o cámbialo.
- El **Short** sale del elemento más sorprendente de la lista.

Los campos:

| Campo | Regla |
|---|---|
| `tema`, `por_que` | Qué es y por qué se eligió (con los datos de la investigación) |
| `categoria` | lugares, historia, ciencia, animales, misterios, inventos, cuerpo humano, récords o actualidad |
| `titulo` | ≤ 70 caracteres, honesto (el vídeo cumple lo que promete), con 1–3 palabras clave en MAYÚSCULAS |
| `miniatura` | 2 líneas de ≤ 14 caracteres que **complementen** el título, no que lo repitan |
| `miniatura_imagen` | Índice de la escena cuya foto va en la miniatura (la más impactante) |
| `descripcion` | 2–3 frases con las palabras que buscaría la gente |
| `etiquetas` (8–12), `hashtags` (3) | En español y en minúsculas |
| `pron` | Pronunciación para la voz: `{"Longyearbyen": "Long yir bien"}` (los subtítulos usan el texto original) |
| `fuentes` | `[{"titulo": …, "url": …}]` |
| `escenas` | **26–34 escenas, 1.450–1.800 palabras en total** (8–10 min), con **15–25 fotos distintas** |
| `short` | `titulo` (con #shorts), `gancho` (2 líneas), `descripcion`, `escenas`: **4–6, 90–140 palabras** (menos de 55 s) |

Cada escena tiene `titulo` (en pantalla, MAYÚSCULAS, ≤ 28 caracteres), `capitulo` (texto del capítulo en YouTube),
`narracion` (35–60 palabras, una sola idea) e `imagen`. Opcionalmente lleva `cifra`, un número o frase corta
(≤ 12 caracteres) que aparece en grande.

**Antes de escribir, lee `aprendizajes.md`:** su receta (gancho, duración, título, final) manda sobre lo de abajo.

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
python3 tools/producir.py $FECHA      # unos 20-25 minutos: ejecútalo en segundo plano
```
Revisa `trabajo/<id>/fotogramas.jpg` y `salida/<id>/miniatura.jpg`: que el texto se lea, que ninguna imagen sea un
error y que la miniatura llame la atención. El vídeo debe durar entre **8:00 y 10:30** (si dura menos de 8 min, añade un elemento a la lista) y el Short, menos
de 60 s (si no, el script avisa).
Si cambias algo, `--solo video|short|miniatura|textos` regenera solo esa parte.

## 6. Entregar
```bash
cd .. && git add canal-curiosidades && git commit -m "Vídeo diario $FECHA: <título>" && git push -u origin <rama>
```
Los `.mp4` no van a git (los excluye `.gitignore`). Se entregan con **SendUserFile** (`status: proactive`):
`video.mp4`, `short.mp4` y `miniatura.jpg`. **Haz el push antes del paso 7**: la miniatura se le pasa a vidIQ desde GitHub.

## 7. Subir a YouTube con vidIQ (si el conector está disponible)
El usuario lo quiere así: **públicos y programados**, el vídeo a las **18:00** y el Short a las **13:00** (hora de España,
`Europe/Madrid`). Subir a YouTube con vidIQ **no gasta créditos**. Lo que está previsto se apunta en `publicaciones.json`.
**Límite del plan gratuito de vidIQ: 3 subidas a YouTube al día**, que se reinician a medianoche del Pacífico (las 9:00 en
España; por eso la tarea se ejecuta a las 9:17). Cuenta cuando se publica, no cuando se crea el borrador. Cada día: el vídeo
y el Short del día (2) y, como mucho, 1 Short pendiente (`estado: "aprobado"` con `subir_el` de hoy).
1. **Horas libres.** Mira `publicaciones.json`. El vídeo va al **primer día, empezando por hoy, sin otro vídeo
   (`formato: video`) a las 18:00**. El Short va a la **primera hora de las 13:00 libre**. Nunca programes nada en el pasado.
2. **Cuenta.** `vidiq_social_account_list` (platform YOUTUBE). El `platformAccountId` del canal es el de `publicaciones.json`.
3. **Miniatura.** `vidiq_upload_image` con `image` =
   `https://raw.githubusercontent.com/ezequielhoracio0808-arch/Nego/<rama>/canal-curiosidades/salida/<id>/miniatura.jpg`.
   No uses el enlace de subida de vidIQ: este entorno no llega a mcp.vidiq.com.
4. **Vídeos.** Para `video.mp4` y para `short.mp4`: `vidiq_video_upload` con `localFile` (ruta absoluta, `wc -c` y
   `video/mp4`). Ejecuta en la terminal la orden que devuelve (tarda segundos) y luego llama otra vez con el `uploadId`
   hasta que diga `ready`.
5. **Borradores.** Uno por vídeo con `vidiq_social_post_draft_create`. Si responde «has not finished rendering», espera
   un minuto y repite. Datos del borrador:
   - `title`: la primera línea de `descripcion.txt` o `descripcion-short.txt`;
   - `text`: el resto del archivo, sin la línea «Etiquetas:»;
   - `tags`: `etiquetas` del guion;
   - `categoryId`: 27; `privacyStatus`: `public`; `publishAt`: la hora del punto 1, con `+01:00` o `+02:00` según el horario;
   - el vídeo largo lleva además `thumbnailImageId`.
6. **Apúntalo** en `publicaciones.json` con `estado: "borrador"` (con `vidiq_post` y `revision`), haz commit y push.
7. **Pide el visto bueno.** vidIQ solo publica cuando el usuario lo aprueba después de ver el borrador. Así que **no llames
   a `vidiq_social_post_publish`** hasta que el usuario responda «sí» en esta conversación. En el resumen final enséñale
   cada borrador: cuenta, título, hora y coste (0). Cuando diga que sí, publica cada `postId` con su `revision`, cambia el
   `estado` a `"programado"`, guarda en `url` la `postUrl` de `vidiq_social_post_status` y haz commit. Si la hora ya ha pasado cuando responda, muévela a la siguiente hora libre con
   `vidiq_social_post_draft_update` y avísale.
8. **Comentario fijado.** Si existe `salida/<id>/comentario-fijado.txt`, recuérdale que lo pegue y lo fije, porque vidIQ
   no fija comentarios.

## 8. Resumen final
Termina con un resumen breve en español:
- el tema y **por qué** se eligió (cifras de la investigación),
- **qué se ha aprendido de las visitas** (los mejores y peores vídeos, con cifras) y qué se ha cambiado por ello,
- el título (y, si es día de prueba, qué se prueba),
- qué revisar (pronunciación de nombres raros y cualquier dato con matices),
- los borradores de YouTube con su hora, y la pregunta: «¿Los programo? Responde **sí**».
  Sin conector de vidIQ: cuándo publicar a mano (vídeo a las 18:00 y Short a las 13:00).

## Domingos: recopilación semanal (25–30 min)
Los domingos no se hace vídeo nuevo, sino una recopilación de **los 3 vídeos largos de la semana (lunes a sábado) con más
visitas por hora**, según `python3 tools/rendimiento.py informe`. Si aún no hay datos, se usan los 3 más recientes.
Lo que ya está verificado no hay que volver a comprobarlo, y las fotos ya están descargadas.
1. Escribe la receta en `trabajo/receta-$FECHA.json` (ver `tools/recopilar.py`). Lleva:
   - `id`: `$FECHA-recopilacion-<slug>`;
   - un título nuevo con palabras clave que se buscan («lugares prohibidos del mundo», «misterios sin resolver»…);
   - la miniatura;
   - una `intro` nueva (gancho de 2–3 frases) y un `cierre` con pregunta y suscripción;
   - los 3 `videos` en orden, de menos a más sorprendente.
2. `python3 tools/recopilar.py trabajo/receta-$FECHA.json` y después
   `python3 tools/producir.py $FECHA-recopilacion-<slug> --solo video miniatura textos` (unos 60 min; en segundo plano).
3. Revisa los fotogramas, la miniatura y la duración (25–30 min; si se queda corta, añade un cuarto vídeo).
4. El Short del domingo es un **Short suelto nuevo** (`guiones/shorts/$FECHA-s01-<slug>.json`, como los del 27/11),
   sobre un tema que siga la receta de `aprendizajes.md`.
5. Súbelos como cualquier día (paso 7): la recopilación a las 18:00 y el Short a las 13:00. La recopilación lleva un
   `comentario-fijado.txt` con los créditos de las fotos: recuérdaselo al usuario.

