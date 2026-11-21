# Nego — Instagram con Claude

13 skills de Claude Code para escribir, planificar y analizar tu Instagram en español. **Nada se publica solo**: cada skill deja un borrador en `instagram/borradores/` y tú decides qué publicar.

| Skill | Qué hace |
|---|---|
| `/ig-reel` | Guion de reel con 26 fórmulas de gancho y puntuación 0–100 |
| `/ig-viral` | Analiza reels que funcionan en tu nicho y los convierte en guiones originales |
| `/ig-caption` | Captions en 3 largos con CTA y hashtags |
| `/ig-carousel` | Carrusel slide a slide listo para Canva |
| `/ig-story` | Secuencias de stories con stickers |
| `/ig-profile` | Puntúa tu perfil y reescribe la bio |
| `/ig-plan` | Plan semanal: qué, cuándo y con quién interactuar |
| `/ig-human` | Quita el tono de IA y aplica tu voz |
| `/ig-comment` | Comentarios con valor para posts de otros |
| `/ig-reply` | Respuestas a tus comentarios (incluye críticas y trolls) |
| `/ig-dm` | Mensajes directos: palabra clave, leads, colaboraciones |
| `/ig-repurpose` | Una pieza → varias en otros formatos |
| `/ig-audit` | Auditoría de métricas: hacer más / menos / probar |

## Cómo empezar

1. Abre Claude Code en esta carpeta (`claude` en la terminal, o la app/web con este repo).
2. Rellena `instagram/marca.md` (o escribe `/ig-profile` y deja que Claude te pregunte).
3. Prueba: `/ig-reel errores al empezar en Instagram`.

## Estructura

```
.claude/skills/ig-*/SKILL.md   las 13 skills
instagram/marca.md             tu nicho, público y voz (rellénalo)
instagram/reglas.md            reglas comunes de todas las skills
instagram/hooks.json           26 fórmulas de gancho + rúbrica de puntuación
instagram/borradores/          aquí se guarda todo lo generado
```

Las skills buscan `instagram/` en la carpeta del proyecto. Si las copias a `~/.claude/skills/` para usarlas en cualquier sitio, copia también la carpeta `instagram/` al proyecto donde trabajes.

## Buenas prácticas

Las skills están pensadas para respetar las normas de Instagram: no automatizan likes, comentarios ni DMs, y no copian el contenido de otros, solo el mecanismo de lo que funciona.
