# Qué funciona en Dato Oculto

Se actualiza cada vez que se analizan las visitas (paso 1b de `DIARIO.md`) y **manda al escribir los guiones** (paso 3).
Datos de cada vídeo en `rendimiento.json`. Para verlos: `python3 tools/rendimiento.py informe`.

## Cómo se decide
- Se compara cada Short con los demás por **visitas por hora** (a partir de 48 h publicado) y por **% visto**
  (porcentaje medio del Short que se ve; por encima del 100 % significa que lo repiten).
- Una regla solo se cambia si el patrón se repite: **al menos 2 vídeos en cada lado y una diferencia de un 30 % o más**.
  Si no, se apunta como *indicio* y se sigue probando.
- **De cada 3 Shorts, 2 siguen la receta ganadora y 1 prueba una sola cosa nueva** (otro tipo de gancho, otra categoría,
  otra duración...). Así se aprende sin perder visitas.

## Receta actual de los Shorts
*Estado: hipótesis sacadas de la investigación de vidIQ del 27/11. Aún no hay datos del canal.*
1. **Gancho:** el dato más sorprendente en la primera frase, en menos de 3 segundos y sin presentarse.
   Por ejemplo: «En este pueblo de España se prohibió morir».
2. **Duración:** de 28 a 35 segundos. Los Shorts de misterios que más superan a su canal duran unos 28 s.
3. **Título:** «El lugar / pueblo / isla donde…», con 1 a 3 palabras en MAYÚSCULAS y 1 emoji al final, más `#shorts`.
4. **Tema:** lugares prohibidos o extraños. La búsqueda «lugares prohibidos» tiene 112.000 al mes y
   «… que no puedes visitar» sube un 81 %.
5. **Final:** una pregunta corta para que comenten («¿Irías?», «¿Vivirías aquí?»).

## Receta actual de los vídeos largos
*Estado: hipótesis sacadas de vidIQ (27/11) y del vídeo de Duodedos sobre monetizar sin mostrar la cara.*
1. **Duración:** 8–10 minutos al día. A partir de 8 min caben anuncios a mitad del vídeo, y las 4.000 horas solo cuentan en vídeos largos.
2. **Formato:** una lista de 5–7 elementos del mismo tema, de menos a más, con un capítulo por elemento.
3. **Título:** «N LUGARES / ANIMALES … que …», con la búsqueda principal dentro («lugares prohibidos del mundo»).
4. **Domingo:** recopilación de 25–30 min con los 3 vídeos de la semana con más visitas por hora.
5. **Miniatura:** 2 líneas que complementen el título (no lo repitan) y una foto con un sujeto claro.

## Pruebas pendientes (una cada 3 Shorts)
- [ ] Animales con «¿Sabías que…?» (lo que más crece ahora en curiosidades).
- [ ] Gancho en forma de pregunta frente a afirmación.
- [ ] Shorts más cortos (unos 25 s) frente a 35 s.
- [ ] Serie numerada: «Lugares prohibidos del mundo #1, #2…».
- [ ] Título sin emoji.

## Historial de análisis
| Fecha | Vídeos con datos | Qué se vio | Qué se cambió |
|---|---|---|---|
| 27/11/2026 | 0 | Primeros vídeos programados para el 28/11 | Receta inicial (hipótesis) |
