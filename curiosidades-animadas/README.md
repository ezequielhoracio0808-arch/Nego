# 🧠 Datos con Cara: la serie animada de El Dato Oculto

> **Kit del canal [@eldatooculto09](https://www.youtube.com/@eldatooculto09):** [`canal/eldatooculto.md`](canal/eldatooculto.md).
> Incluye títulos para los 3 Shorts ya publicados, la configuración del canal, las listas, el plan de 7 días y el banner.

Inspirado en el vídeo *«Así Creo Shorts de 13M de Visitas con Claude en 10 Minutos»* (Ale Ferr): Shorts
animados en 2D que cuentan un dato curioso con humor. Aquí no usamos su plantilla ni copiamos el estilo de
ningún canal. Es **un motor propio** con un formato propio:

> **El protagonista del dato lo cuenta él mismo, con cara.** El pulpo explica sus tres corazones, Venus presume
> de que su día dura más que su año y el plátano confiesa que es radiactivo. Chispa, la bombilla, hace de espectador.

Todo se genera en esta carpeta: personajes, fondos, animación, voz, música y efectos de sonido. No hay
material con derechos de autor ni hace falta ninguna suscripción.

## 5 shorts listos (`videos-listos/`)
| # | Short | Dur. | Personajes |
|---|---|---|---|
| 01 | El pulpo tiene TRES corazones (y la sangre azul) | 27 s | pulpo, corazones, gota de sangre |
| 02 | En Venus un día dura MÁS que un año | 23 s | Venus, la Tierra, el Sol |
| 03 | Los plátanos son RADIACTIVOS (de verdad) | 25 s | plátano, Chispa |
| 04 | La miel NO caduca nunca | 25 s | tarro de miel, pirámide, abeja, Chispa |
| 05 | Los flamencos NACEN GRISES | 21 s | flamenco, gamba |

Cada uno trae `NN-slug.mp4` (1080×1920, 30 fps, unos −15 LUFS), `NN-slug-portada.jpg` y `NN-slug.txt`
(título, descripción con fuentes, hashtags, comentario para fijar y guion).

**Antes de subir, escúchalos enteros.** La voz es sintética (Piper, español de España) y su tono cambia
con cada personaje. Si quieres más calidad, usa tu voz o ElevenLabs (ver abajo).

## Publicar
- **YouTube Shorts:** súbelo desde el móvil y elige como miniatura el fotograma de la portada. Copia el título y la
  descripción del `.txt`, y fija el comentario que sugiere.
- **TikTok / Reels:** el mismo vídeo sirve. Usa la portada `.jpg` y los hashtags del `.txt`.
- Ritmo: 1 al día es mejor que 5 de golpe. Contesta a los comentarios pidiendo temas, porque así salen los siguientes.
- **Monetización:** YouTube no paga por contenido «producido en masa o repetitivo». Para no caer en eso, varía
  los personajes y los fondos, comprueba cada dato y, mejor aún, pon tu propia voz. No publiques 10 iguales al día.

## Hacer un short nuevo (con Claude)
Igual que en el vídeo: abre **esta carpeta** en Claude Code y pídele, por ejemplo:
- «Dame 5 ideas de shorts nuevos»
- «Hazme un short de que las abejas bailan para decirse dónde hay flores»

Claude lee `CLAUDE.md`, escribe el guion en `guiones/`, dibuja los personajes que falten y lo renderiza.
Si algo no te gusta («cambia la música», «que el pulpo esté enfadado», «quita ese rótulo»), díselo.

### A mano
Necesita Python 3, numpy, Pillow, ffmpeg y `piper-tts` con la voz `es_ES-davefx-medium` (ruta en `PIPER_VOICE`). Desde esta carpeta:
```bash
python3 tools/animar.py lista              # guiones disponibles
python3 tools/animar.py render 03          # un short  -> videos-listos/
python3 tools/animar.py render todos       # todos (en paralelo)
python3 tools/animar.py prueba 03 4        # fotograma de la escena 4 (rápido, para revisar)
python3 tools/animar.py reparto            # hoja con todos los personajes -> salida/reparto.png
python3 tools/animar.py caras pulpo        # todas las expresiones de un personaje
python3 tools/animar.py textos             # regenera solo los .txt (título, descripción, fuentes)
python3 tools/marca.py                     # banner y foto de perfil del canal -> canal/
```
Cada short tarda menos de un minuto en renderizarse.

## Usar tu voz o ElevenLabs
1. `python3 tools/animar.py guion 01` imprime el texto, una frase por línea.
2. Grábalo tú o pégalo en ElevenLabs (texto a voz) y descarga el audio.
3. Guárdalo como `pon-aqui-tu-voz/01.mp3` (también vale `.wav` o `.m4a`) y vuelve a renderizar.

El motor reparte el audio entre las escenas usando los silencios, así que deja una pausa clara entre frases.
Con una sola voz no hay cambio de tono por personaje.

## Próximas ideas (datos comprobados)
| Idea | Personajes |
|---|---|
| El corazón de la gamba está en la cabeza | gamba ✅ |
| Las abejas bailan para decirse dónde hay flores | abeja ✅ |
| En el Sol cabrían más de un millón de Tierras | sol ✅, tierra ✅ |
| Tu cerebro gasta lo mismo que una bombilla de 20 vatios | bombilla ✅, cerebro 🆕 |
| El plátano es una baya y la fresa no | plátano ✅, fresa 🆕 |
| La Luna se aleja de la Tierra unos 4 cm al año | tierra ✅, luna 🆕 |
| Un rayo está más caliente que la superficie del Sol | sol ✅, rayo 🆕 |
| La Torre Eiffel crece unos centímetros en verano | torre 🆕 |
| Los wombats hacen caca en forma de cubo | wombat 🆕 |
| Las nutrias se dan la mano para no separarse al dormir | nutria 🆕 |

## Estructura
```
guiones/            un .json por short (escenas, personajes, rótulos, efectos)
tools/animar.py     motor: voz, música, sonidos, fondos, animación y render
tools/personajes.py todos los personajes y las caras
pon-aqui-tu-voz/    (opcional) tu audio NN.mp3 para sustituir la voz sintética
videos-listos/      vídeos terminados + portada + texto para publicar
salida/reparto.png  catálogo de personajes
canal/              kit del canal El Dato Oculto: guía, banner y foto de perfil
```
Fuentes tipográficas: Anton e Inter (licencia OFL). Música y efectos sintetizados por el propio motor.
