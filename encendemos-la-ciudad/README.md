# 🌃 Encendemos la ciudad

**La idea:** una ciudad de noche con exactamente **100.000 ventanas**, todas apagadas. **Cada seguidor enciende una.**
Cuando se encienda la última, **amanece**.

La ciudad y el orden de encendido son siempre los mismos: la ventana nº 4.218 siempre está en el mismo sitio.
Así cada seguidor puede tener su ventana. Es una idea propia: comparte el formato «llenamos algo entre todos» con
@llenamoslanave, pero no su tema, su nombre ni su estilo visual.

## Perfil (TikTok + Instagram)
| Campo | Qué poner |
|---|---|
| Nombre | **Encendemos la ciudad 🌃** |
| Usuario | `@encendemoslaciudad`; si está cogido: `@encendamoslaciudad`, `@laciudadapagada`, `@100milventanas` |
| Foto | `salida/perfil.png` |
| Categoría (Instagram) | Creador(a) digital |
| Enlace | el perfil de la otra red (TikTok ↔ Instagram) |

**Bio de Instagram** (máx. 150 caracteres):
```
🌃 Una ciudad. 100.000 ventanas apagadas.
Cada seguidor enciende una.
Cuando se encienda la última, amanece.
```
**Bio de TikTok** (máx. 80 caracteres):
```
🌃 100.000 ventanas apagadas. Cada seguidor enciende una.
```
> No pongas "Cuenta oficial" como en la cuenta de ejemplo: una cuenta nueva no es oficial de nada.

## Primera publicación
- **Vídeo:** `salida/01-intro.mp4` (21 s, vertical 1080×1920)
- **Portada:** `salida/01-portada.png`
- **Texto:**
```
Esta ciudad tiene 100.000 ventanas. Todas apagadas. Hasta hoy. 🌃
Cada seguidor enciende una luz. Cuando se encienda la última, amanece.
¿Encendemos la ciudad?
#encendemoslaciudad #100000 #ciudad #noche #reto #parati #fyp
```
- **Comentario fijado:** `Comenta 💡 y te enseño cuál es tu ventana.`
- El vídeo trae música propia. En TikTok puedes añadir un sonido en tendencia con volumen bajo.

## Cómo hacerla crecer
1. **Cada día:** vídeo de actualización con las luces nuevas y una historia con el estado.
2. **Responde a los 💡 con la ventana de cada persona** (en TikTok, "responder con vídeo"). Es lo que más engancha: la gente comparte "su" luz.
3. **Hitos con publicación especial:** 1.000 · 10.000 · 25.000 · 50.000 · 75.000 · 90.000 · 99.000 ("falta muy poco") · **100.000 = amanece**.
4. Nada de seguidores comprados ni de premios que no vayas a dar: se nota y se pierde la confianza.

## Generar los vídeos e imágenes
Necesita Python 3, numpy, Pillow y ffmpeg. Desde esta carpeta:
```bash
python3 tools/ciudad.py intro                      # vídeo de presentación + portada
python3 tools/ciudad.py perfil                     # foto de perfil
python3 tools/ciudad.py actualizacion 1000 2500    # vídeo: de 1.000 a 2.500 luces (9 s)
python3 tools/ciudad.py estado 2500                # imagen para historia: 2.500 luces
python3 tools/ciudad.py ventana 4218 @usuario      # "esta es tu luz" para un seguidor
python3 tools/ciudad.py estado 100000              # el amanecer final
```
Todo sale en `salida/`. El número de cada persona es el número de seguidores que tenía la cuenta cuando siguió.
Fuentes tipográficas: Anton e Inter (licencia OFL).
