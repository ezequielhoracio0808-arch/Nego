# 🔑 Dato Oculto: canal de curiosidades con un vídeo nuevo cada día

**Cada mañana a las 9:17 (hora de España)** una tarea programada de Claude (en la conversación donde está conectado vidIQ):
1. **Investiga qué vídeos funcionan**: vídeos de curiosidades en español de los últimos 14 días, ordenados por
   visitas/día y por cuántas veces superan al tamaño de su canal (API de YouTube; si no hay clave, búsquedas web).
2. **Elige un tema** que no se haya hecho y **verifica cada dato** con dos fuentes como mínimo.
3. **Escribe el guion** del vídeo (8–10 min, en formato lista: «7 lugares donde…») y del Short (menos de 60 s).
   **Los domingos** hace una recopilación de 25–30 min con los 3 vídeos de la semana que más se han visto
   (`tools/recopilar.py`), para sumar horas de visualización: hacen falta 4.000 para monetizar.
4. **Busca imágenes** con licencia libre en Wikimedia Commons y anota la atribución.
5. **Pone la voz** (Piper, español de España), **hace el montaje** (zoom lento sobre cada foto, rótulos, subtítulos y música propia),
   la miniatura y la descripción con capítulos, fuentes y créditos.
6. **Te lo manda a la app** (video.mp4, short.mp4 y miniatura.jpg) y sube el guion y los textos a git.
7. **Lo sube a tu canal de YouTube con vidIQ**, programado (vídeo a las 18:00 y Short a las 13:00, hora de España).
   Antes te enseña los borradores y solo los programa cuando respondes «sí». Lo previsto queda en `publicaciones.json`.
8. **Aprende de las visitas**: cada dos días lee en YouTube Studio (a través de vidIQ) las visitas y el % visto de cada
   vídeo publicado (`rendimiento.json`), compara qué temas, ganchos, títulos y duraciones funcionan mejor y actualiza la
   receta de `aprendizajes.md`, que manda al escribir los siguientes Shorts. De cada 3 Shorts, 1 prueba algo nuevo.

El procedimiento detallado está en [`DIARIO.md`](DIARIO.md). La identidad del canal y cómo crearlo están en [`marca/`](marca/canal.md).

## Qué hay en cada vídeo (`salida/AAAA-MM-DD-tema/`)
| Archivo | Para qué |
|---|---|
| `video.mp4` | Vídeo 1920×1080 · *no está en git* (pesa ~100 MB): llega por la app y se regenera con `producir.py` |
| `short.mp4` | Short 1080×1920 de menos de 60 s · *no está en git* |
| `miniatura.jpg` | Miniatura 1280×720 |
| `portada-short.jpg` | Portada del Short |
| `descripcion.txt` | Título, descripción, capítulos, fuentes, créditos de las fotos, hashtags y etiquetas |
| `descripcion-short.txt` | Lo mismo para el Short |
| `subtitulos.srt`, `subtitulos-short.srt` | Subtítulos para subir a YouTube |

## Antes de subir cada vídeo
- **Escúchalo entero.** La voz es sintética y puede pronunciar mal algún nombre extranjero. Se corrige en `pron` dentro del guion.
- Mira las fuentes de la descripción si algún dato te sorprende.
- Sube los subtítulos `.srt`: ayudan al posicionamiento.

## Para que crezca (y se pueda monetizar)
- YouTube no monetiza el contenido **«repetitivo o producido en masa»**. Lo que lo diferencia aquí: guion propio
  verificado, fuentes en cada vídeo y un tema distinto cada día. Aún mejor si **grabas tú la voz** con el mismo guion.
  Lee la narración de `guiones/…json`, guárdala como `voz.wav` y dímelo: adapto el montaje a tu voz.
- Publica siempre a la misma hora. Responde a los comentarios de la primera hora y fija uno con una pregunta.
- Cada semana, mira en YouTube Studio qué vídeos retienen más (porcentaje visto) y cuéntamelo: ajusto el estilo de los guiones.

## Cómo hacerlo a mano
```bash
pip install piper-tts pillow numpy requests     # y ffmpeg
python3 tools/investigar.py                     # investigación del día
python3 tools/imagenes.py --buscar "polar bear" # buscar fotos en Commons
python3 tools/imagenes.py 2026-11-27            # descargar las fotos del guion
python3 tools/producir.py 2026-11-27            # voz + montaje + Short + miniaturas + textos
python3 tools/marca.py                          # foto de perfil, banner y marca de agua
```
El nombre, el color y las búsquedas de la investigación están en `config.json`.

### Lotes de Shorts sueltos
Un guion sin `escenas` (solo con `short`) produce únicamente el Short, su portada y su descripción.
Van en `guiones/shorts/` y salen en `salida/<id>/`:
```bash
for g in guiones/shorts/2026-11-27-s*.json; do python3 tools/imagenes.py $g && python3 tools/producir.py $g; done
```

## La clave de la API de YouTube (para investigar con datos reales)
Sin ella, la investigación se hace con búsquedas web, que son menos precisas. Para conseguirla (gratis, unos 5 minutos):
1. Entra en **console.cloud.google.com** y crea un proyecto (por ejemplo «dato-oculto»).
2. Ve a **APIs y servicios**, luego **Biblioteca**, busca **YouTube Data API v3** y pulsa **Habilitar**.
3. Ve a **APIs y servicios**, luego **Credenciales**, y pulsa **Crear credenciales** y después **Clave de API**. Cópiala.
4. Guárdala en el **formulario seguro** que te abre Claude, para el servidor `www.googleapis.com`.
   No la pegues en el chat ni en ningún archivo del repo.

La cuota gratuita (10.000 unidades al día) da de sobra: cada investigación gasta unas 850.

Fuentes tipográficas: Anton e Inter (licencia OFL). Música generada por el propio script. Fotos de Wikimedia Commons
con licencias CC BY, CC BY-SA, CC0 o dominio público, con su atribución en cada vídeo.
