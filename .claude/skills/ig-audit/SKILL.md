---
name: ig-audit
description: Audita el rendimiento de la cuenta de Instagram con las métricas del usuario — qué funciona, qué no, y qué cambiar. Úsala cuando pida analizar estadísticas, auditar la cuenta, revisar resultados del mes o «/ig-audit».
---

# /ig-audit — Auditoría de la cuenta

Sigue `instagram/reglas.md`. Lee `instagram/marca.md` y auditorías anteriores en `instagram/borradores/` (para comparar).

## Entrada
Métricas de sus últimas 10–30 publicaciones (capturas del panel de estadísticas, CSV o lista): fecha, formato, tema/gancho, alcance o reproducciones, % de no seguidores, likes, comentarios, compartidos, guardados, seguimientos, retención/tiempo medio de reproducción en reels. Y seguidores totales al inicio y final del periodo. Trabaja con lo que haya; di qué falta.

## Análisis
1. **Tasas por publicación** (sobre alcance, no sobre seguidores):
   - Compartidos/alcance y guardados/alcance (señales más fuertes).
   - Comentarios/alcance, seguimientos/alcance.
   - Retención de reels: % que pasa de 3 s, tiempo medio vs duración.
2. **Top 3 y bottom 3** con hipótesis de por qué (gancho, tema, formato, duración, hora).
3. **Por dimensión**: rendimiento medio por formato, por pilar, por fórmula de gancho (`hooks.json`), por día/hora.
4. **Crecimiento**: seguidores netos, qué publicaciones trajeron más seguimientos.
5. **Perfil**: si hay visitas al perfil altas pero pocos seguimientos, recomienda `/ig-profile`.

## Entrega
- Resumen en 5 líneas (lo más importante primero).
- Tablas con los números calculados (muestra la fórmula, no inventes datos que no te dieron).
- **Hacer más / Hacer menos / Probar** — 3 puntos cada uno, concretos.
- 1 experimento para las próximas 2 semanas con métrica de éxito.
- Si hay auditoría previa, comparación con ella.
Guarda en `instagram/borradores/AAAA-MM-DD-ig-audit.md`.
