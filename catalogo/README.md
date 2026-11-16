# Catálogo a tu puerta

Catálogo web con pedido por WhatsApp y **10% de descuento al llevar 10 productos o más**.

## Archivos

| Archivo | Qué tiene |
| --- | --- |
| `index.html` | La página: diseño, buscador, filtros, pedido y armado del mensaje de WhatsApp. |
| `productos.js` | **Lo que se edita**: número de WhatsApp, descuento, categorías, productos, precios, opciones y notas de perfumes. |
| `fotos/` | Una foto por producto, con el `id` del producto como nombre de archivo. |

## Cómo está organizado

7 categorías (226 productos), cada una con sus secciones:

- **Perfumes** (124): Árabes · Diseñador · Nicho y lujo. Se filtran también por *Para él / Para ella / Unisex* y por aroma (dulces, frescos, intensos, florales, amaderados, frutales).
- **Decants** (44)
- **Victoria's Secret** (9)
- **Audio** (15): Auriculares · Parlantes · Micrófonos
- **Accesorios iPhone** (19): Fundas · Vidrios y protectores · Cargadores y cables · Extras
- **Mate y termos** (5)
- **Otros** (10): Joysticks · Iluminación · Tecnología y cuidado personal

## Descuento por cantidad

En `productos.js`:

```js
descuento: { desde: 10, porcentaje: 10 },
```

- Se cuentan **todas las unidades** del pedido (2 Khamrah + 8 fundas = 10).
- Al llegar a `desde`, se descuenta `porcentaje` % del precio de cada producto (redondeado a $10).
- Cada tarjeta muestra el precio con descuento ("Llevando 10+: $41.400"), y la barra del pedido tiene 10 casilleros que se llenan con cada producto.
- El mensaje de WhatsApp detalla subtotal, descuento y total.

Para cambiarlo a, por ejemplo, 15% desde 12 productos: `descuento: { desde: 12, porcentaje: 15 }`.

## Cambiar un precio o sumar un producto

Cada producto es una línea en `productos.js`:

```js
{ id: "khamrah", cat: "perfumes", sec: "arabes", nombre: "Khamrah", detalle: "Perfume 100 ml", precio: 46000, para: "unisex", aroma: "dulce", foto: "khamrah.webp", destacado: 1 },
```

- `precio`: número sin puntos.
- Para sumar uno, copiá una línea de la misma sección y cambiá `id` (único), `nombre`, `detalle` y `precio`. La foto va en `fotos/` y se nombra en `foto`.
- `destacado` (1, 2, 3…) lo pone en "Recomendados" y al frente de su categoría; `nuevo: true` le pone la etiqueta "Nuevo".
- `opciones` apunta a una lista de `opciones` (modelos de iPhone, colores, ficha del cable).

## Links

- `…#perfumes`, `…#audio`, etc. abren directo esa categoría.
- `…#5491122334455` manda los pedidos a ese WhatsApp (para revendedores). Se puede combinar: `…#5491122334455-perfumes`.
