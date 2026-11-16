# Canal GTA 6 — "MODO LEONIDA"

10 vídeos listos para subir el **jueves 19 de noviembre de 2026** (día de lanzamiento de GTA 6).
Cada carpeta de `salida/` trae: `video.mp4` (1080p, 30 fps, voz + música + subtítulos quemados),
`miniatura.jpg` (1280×720), `subtitulos.srt` y `descripcion.txt` (título, descripción, capítulos, hashtags y etiquetas).

## Qué va a buscar la gente (y qué vídeo lo cubre)

| # | Búsqueda / intención | Vídeo |
|---|---|---|
| 01 | "gta 6 todo lo que sabemos", resumen rápido | Todo lo que tienes que saber |
| 02 | "a qué hora sale gta 6", precarga, cuánto ocupa | ¿A qué hora sale? |
| 03 | "gta 6 pc" (pregunta nº 1 de los jugadores de PC) | ¿GTA 6 en PC? |
| 04 | "gta 6 personajes", Jason y Lucía | Jason y Lucía (sin spoilers) |
| 05 | "gta 6 mapa", Leonida, Vice City | El mapa explicado |
| 06 | "gta 6 consejos / guía principiantes" | 8 consejos para empezar |
| 07 | "gta 6 dinero infinito / money glitch" (lo más buscado en cada GTA) | ¿Dinero infinito? Cuidado con las estafas |
| 08 | "trucos gta 6 / cheats" | Trucos: qué hay de verdad |
| 09 | "gta 6 online", qué pasa con GTA Online | GTA 6 Online |
| 10 | "gta 6 retrasos / historia" | De 2013 a 2026 |

Fuentes de la investigación: The Ringer ("The Six Biggest Questions About GTA VI"), Google Year in Search 2025
(GTA 6 entre los juegos más buscados), recopilatorios de preguntas frecuentes (Vandal, Driffle, Tom's Guide, GamesRadar, PCGamesN).

## Orden de publicación recomendado (jueves 19)
1. **01** a medianoche / primera hora · 2. **02** · 3. **03** · 4. **07** · 5. **05** · 6. **06** · 7. **04** · 8. **08** · 9. **09** · 10. **10**
(o 3–4 el jueves y el resto programados uno al día para mantener el canal activo).

## Antes de subir — revisa
- **Escucha cada vídeo entero.** La voz es sintética (Piper, español de España); puede pronunciar raro algún nombre.
- **Datos que pueden cambiar el mismo día:** hora exacta de desbloqueo, tamaño de descarga, trucos, online. Los guiones
  evitan cifras no confirmadas a propósito, pero si Rockstar anuncia algo, actualiza el guion y vuelve a renderizar.
- **Sin material de Rockstar:** todo el arte, la música y la voz son originales/generados, así que no hay riesgo de
  reclamaciones de copyright. El nombre "GTA 6" se usa solo para referirse al juego, y cada descripción incluye el aviso de canal no oficial.
- Para crecer de verdad, a partir del jueves añade **gameplay propio** grabado en tu consola.

## Volver a generar / editar
```bash
pip install piper-tts pillow numpy           # + ffmpeg
# voz: https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-es_ES-davefx-medium.tar.bz2
export PIPER_VOICE=/ruta/es_ES-davefx-medium.onnx
export CANAL="MODO LEONIDA"                  # cambia el nombre del canal aquí
python3 tools/render.py          # todos
python3 tools/render.py 03 07    # solo algunos
```
Los guiones están en `guiones/videos.json` (`t` = titular en pantalla, `s` = subtítulo, `n` = narración).
Fuentes tipográficas: Anton e Inter (licencia OFL).
