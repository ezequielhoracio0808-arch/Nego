# Canal "MODO LEONIDA" — cómo crearlo y qué poner

## 1. Crear la cuenta y el canal (lo tienes que hacer tú: Google pide tu teléfono)
1. Si no tienes cuenta de Google: **accounts.google.com/signup**.
2. Para que el canal se llame "Modo Leonida" y no con tu nombre personal: entra en **youtube.com** desde el ordenador,
   pulsa tu foto (arriba a la derecha), luego **Configuración**, después **Añadir o gestionar canales** y por último **Crear un canal**.
   Escribe el nombre **Modo Leonida**.
   Desde el móvil: app de YouTube, pulsa **Tú** y luego **Crear un canal**. Si te lo crea con tu nombre, cámbialo después en YouTube Studio.
3. Verifica el canal en **youtube.com/verify** con tu teléfono. Sin este paso **no puedes poner miniaturas personalizadas**.

## 2. Personalizarlo (YouTube Studio, Personalización)
**Imagen de marca**
| Campo | Archivo |
|---|---|
| Imagen de perfil | `perfil.png` (800×800) |
| Imagen del banner | `banner.png` (2560×1440; el texto ya está dentro de la zona segura) |
| Marca de agua del vídeo | `marca-de-agua.png` (150×150), mostrar "Durante todo el vídeo" |

**Información básica**
- **Nombre:** Modo Leonida
- **Identificador:** prueba en este orden, según cuál esté libre: `@ModoLeonida`, `@ModoLeonidaGTA`, `@ModoLeonidaES`
- **Descripción:** copia este texto:

```
Bienvenido a Modo Leonida, tu canal de GTA 6 en español.

Guías, consejos, trucos verificados y noticias de Grand Theft Auto VI desde el día de lanzamiento: el mapa de Leonida, Vice City, Jason y Lucía, cómo empezar con buen pie y todo lo que vaya saliendo.

Sin humo: solo publicamos trucos que hemos probado y te avisamos de las estafas.

📅 Vídeo nuevo cada día
🔔 Suscríbete y activa la campanita para no perderte nada

Canal no oficial, sin relación con Rockstar Games ni Take-Two Interactive. Grand Theft Auto es una marca de Take-Two Interactive.
```

- **Palabras clave del canal** (Configuración, Canal): `gta 6, gta vi, gta 6 español, guías gta 6, trucos gta 6, noticias gta 6, leonida, vice city`
- **País:** el tuyo · **Idioma del canal:** español

**Diseño**
- **Tráiler del canal** (para quien no está suscrito): vídeo **01 – GTA 6 ya está aquí**
- **Vídeo destacado** (para suscriptores): el último que publiques

## 3. Listas de reproducción
| Lista | Vídeos |
|---|---|
| GTA 6: Empieza aquí | 01, 02, 03, 06 |
| GTA 6: Guías y consejos | 05, 06, 07, 08 |
| GTA 6: Personajes, online e historia | 04, 09, 10 |

## 4. Para que yo pueda subir los vídeos
Cuando el canal exista, saca de nuevo el token en **developers.google.com/oauthplayground**
(permisos `youtube.upload` y `youtube`). Al iniciar sesión, **elige el canal "Modo Leonida"** en el selector de cuentas.
Copia el **Access token** (empieza por `ya29.`) y pégalo en el formulario seguro, sin la palabra "Bearer".
