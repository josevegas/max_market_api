# El flujo del negocio

Cómo se conectan los módulos de `max_market_api` y qué regla hace cumplir cada
uno. El *por qué* de cada decisión concreta vive en el docstring del módulo que
la implementa; acá está el mapa que ninguno de ellos puede dar por sí solo.

## Qué cubre el sistema hoy

Cubre el ciclo completo de la mercadería en un market: desde que un almacén la
pide hasta que sale por caja.

```
    requerimiento → pedido → cotización → orden → guía → recepción
                                                              │
                                                              ↓
                                                     lote (stock + costo)
                                                              │
                                            precio de tienda ←┴→ venta (FEFO)
```

El stock **sube por recepción y baja por venta**. Los dos movimientos pasan por
el lote, que es la unidad de stock.

## La cadena de compras

Seis documentos. Cada uno **solo nace del anterior aprobado**, y aprobar uno
genera el siguiente con sus líneas ya copiadas.

| # | Documento | Lo emite | Qué decide |
|---|-----------|----------|------------|
| 1 | Requerimiento | El almacén | Qué falta y **para qué almacén** |
| 2 | Pedido | Compras | Que se va a comprar |
| 3 | Cotización | Un proveedor | A qué precio y en cuántos días |
| 4 | Orden de compra | Compras | A quién se le compra |
| 5 | Guía de remisión | El proveedor | Qué dice que trae |
| 6 | Recepción | El almacén | Qué entró de verdad |

### Los estados

`estados` es un catálogo abierto, pero seis códigos deciden si la cadena
avanza (`movimientos/constantes.py`):

| Código | Significado | ¿Habilita el siguiente? |
|--------|-------------|-------------------------|
| `PEN` | Pendiente, recién creado | No |
| `APR` | Aprobado | **Sí, el único** |
| `OBS` | Observado: falta algo, puede volver | No |
| `RCH` | Rechazado, no se espera que vuelva | No |
| `REC` | La mercadería entró al almacén | — |
| `ATE` | Ya cumplió su función: lo que pedía llegó | — |

Se reconocen por `codigo` y no por `descripcion` porque la descripción se edita
desde la API: con "Aprobado" / "APROBADO" / "Aprobada" la regla dejaría de
aplicar sin que nadie tocara una línea de código.

Todo documento **nace en `PEN`** sin que el cliente tenga que conocer el id del
catálogo (`NaceEnPendiente`). La recepción es la excepción: nace `RECEPCIONADO`,
porque registrarla *es* recepcionar.

### Aprobar genera el siguiente

`GeneraSucesorAlAprobar` copia el detalle al sucesor en la misma transacción que
la aprobación. Si la generación falla, la aprobación no queda hecha.

Un caso se sale del molde: **aprobar un pedido abre una cotización por
proveedor**, cada una con las líneas que ese proveedor distribuye —según
`proveedor_productos`—. Cotizar es pedir precio a varios; una sola cotización
sería elegir por el comprador.

### Elegir entre cotizaciones

`GET /pedidos/{id}/comparativo-cotizaciones` puntúa cuatro criterios:

| Criterio | Peso | Mejor es |
|----------|------|----------|
| Precio | 35% | más barato **por unidad atendida** |
| Tiempo de entrega | 25% | menos días |
| Stock atendido | 20% | más cobertura del pedido |
| Condición de pago | 20% | más días de crédito |

El precio se mide **por unidad atendida** y no por monto total: quien cotiza la
mitad del pedido siempre saldría más barato, y el criterio de precio —que pesa
más— terminaría premiando al que menos cubre.

## Del papel al stock

Recibir mercadería **es** lo que crea stock. Antes eran dos actos sueltos y nada
obligaba a que dijeran lo mismo.

```
  recepción_detalle          producto_lote              producto_almacen
  ─────────────────          ─────────────              ────────────────
  cantidad_ingresada   ──→   cantidad            ──→    precio_venta_tienda
  − cantidad_devuelta        (unidad de venta)          (del lote más caro)
  precio_unitario      ──→   precio_compra
  codigo_lote          ──→   codigo_lote
  (de la recepción)    ──→   almacen_id
```

Tres reglas sostienen esto:

**Se recibe donde se pidió.** El almacén de la recepción tiene que ser el del
requerimiento que arrancó la cadena. `requerimiento.almacen_id` es el único
lugar donde el destino está declarado: ni el pedido, ni la cotización, ni la
orden, ni la guía lo llevan.

**El lote se recalcula, no se acumula.** Editar una línea, darla de baja o
cargar una segunda entrega del mismo lote llegan todas al mismo número. Con
acumulación, corregir un dato dejaría el stock sumando el valor viejo y el
nuevo.

**Nada entra sin respaldo.** La suma de lotes no puede superar lo que declara la
guía, y lo recibido no puede superar lo declarado. Sin eso el almacén acabaría
con más stock del que respalda el documento, y el descuadre no aparecería hasta
un inventario.

### La ficha nace con el lote

Registrar un lote **es** decir que ese producto vive en ese almacén, así que la
ficha (`producto_almacen`) se crea sola si no existe. Sin ella el stock quedaba
invisible para la consulta y sin precio con el que venderlo: había mercadería
que no se podía ni mirar ni cobrar.

- Nace con `stock_minimo` en **cero**: nadie decidió todavía cuánto hay que
  tener, y un mínimo inventado haría que cada cosa recién recibida pidiera
  reposición apenas bajara de una unidad. En cero, el aviso se queda callado
  hasta que alguien fije el número de verdad.
- Queda en la **unidad de venta del producto**: es en la que están los lotes y
  en la que se calcula el precio de tienda. En otra, los tres números dejarían
  de ser comparables.
- Si la ficha estaba dada de baja, se reactiva en vez de crear otra: la
  unicidad de la tabla no distingue las inactivas, y una segunda chocaría
  contra el índice.

Vale para las dos puertas de entrada: la recepción y el alta manual del lote.

### Consultar el stock

`GET /almacenes/{id}/stock` — lo disponible por producto, con su mínimo y su
máximo. Con `?bajo_minimo=true`, solo lo que hay que reponer.

Cuentan **solo los lotes `disponible`**: lo agotado o inmovilizado está en el
almacén pero no se puede vender, y darlo por stock sería prometer algo que no se
puede entregar.

## Unidades: todo se compara en unidad mínima

El proveedor factura cajas y el market vende unidades. Comparar los números en
crudo daría por buena una guía de 4 cajas contra 4 unidades sueltas.

- `tabla_equivalencia.factor_conversion` dice cuántas unidades mínimas vale una
  unidad: `UND` → 1, `CAJA12` → 12. El factor es global por unidad, así que el
  catálogo distingue el empaque: `CAJA12` y `CAJA24` son unidades distintas.
- Sin equivalencia registrada se corta con un **400**, no se asume 1.
- El lote va siempre en la **unidad de venta del producto**; la guía, en la de
  compra. Los dos lados se llevan a unidad mínima antes de compararse.
- Convertir entre dos unidades corta con **409 si no da exacto**: 5 unidades
  sueltas no son media caja de 12, y redondear haría aparecer o desaparecer
  mercadería en silencio.

## Precios

Hay **dos** precios de venta, y salen de bases distintas.

### El del catálogo — `precio_producto.precio_venta`

Lo calcula el servidor a partir del de compra. No se envía; mandarlo se ignora.

```
precio_venta = (precio_compra / IGV × (1 + margen/100) + monto_POS) × IGV
```

- El precio de compra viene **con IGV**: es lo que factura el proveedor, así que
  primero se le saca para trabajar sobre el valor.
- El **margen** sale de la categoría del producto (`categoria.margen_ganancia`)
  y es un porcentaje: `18.50` es 18.5%.
- El **`monto_POS`** entra antes del IGV: también tributa.
- `IGV` y `monto_POS` viven en `Settings`, no en el código: la tasa cambia por
  ley y el recargo es una decisión comercial de cada instalación.
- Se redondea **una sola vez, al final**, con `ROUND_HALF_UP`.

### El de la tienda — `producto_almacen.precio_venta_tienda`

Sale del **lote más caro que quede con existencias**. Vender por debajo de eso
sería perder plata sobre la partida que todavía está en el almacén.

- Se recalcula en cada recepción.
- Sin ningún lote con stock no hay máximo que tomar: la ficha **conserva** el
  precio que tenía. Quedarse sin mercadería no es motivo para perderlo.
- Con `precio_manual` la tienda lo fija a mano —una promoción— y la
  sincronización deja de pisarlo. Quitar la marca lo devuelve al calculado.

## La factura del proveedor

Es el documento del proveedor, no uno nuestro: lleva **su** serie y **su**
correlativo, únicos por proveedor.

- Se factura una orden **aprobada o ya atendida**. Exigir solo `APR` habría
  bloqueado el caso más común: la factura llega con la mercadería o después, y
  recepcionar deja la orden en `ATE`.
- Factura únicamente el proveedor de la orden, que se resuelve por
  `orden → cotización → proveedor_id`: la orden no lo lleva.
- El monto **no** se compara para bloquear —entregas parciales, fletes y ajustes
  hacen que casi nunca coincida— pero la respuesta trae `monto_orden` y
  `difiere_de_la_orden` para que quien revisa lo vea sin comparar a ojo.

## La venta

Emitir el comprobante y descontar la mercadería son el mismo hecho. La venta
sale de un **almacén**: es donde están los lotes que se descuentan y la ficha
que fija el precio. El market se deduce subiendo (`almacen → market`); al revés
no se podría, porque un market puede tener más de un almacén.

**Vence primero, sale primero (FEFO).** La línea de venta consume los lotes
ordenados por fecha de vencimiento, y los que no vencen van al final. Sacar por
antigüedad de ingreso dejaría vencer mercadería que entró después y caduca
antes, que es justo la merma que un market intenta evitar.

**Cada línea deja anotado de qué lote salió** (`venta_lote`). Una línea puede
consumir varios lotes —se venden 30 y el que vence antes solo tiene 12—, así
que la correspondencia no cabe en la línea. Sin esa anotación no se podría
devolver el stock exactamente a donde estaba al anular la venta, ni responder a
quién se le vendió un lote que hay que retirar.

**Sin stock no hay línea**, y no se toca nada: vender lo que no hay dejaría el
stock en negativo con el comprobante emitido igual.

**El precio sale de la ficha** (`producto_almacen.precio_venta_tienda`), que a
su vez sale del lote más caro con existencias. La caja no lo envía. Un producto
sin ficha en ese almacén no se puede vender: sin ella no hay precio, y uno
inventado es peor que un 400.

**Corregir una cantidad devuelve todo y vuelve a sacar.** Ajustar la diferencia
tendría que decidir a qué lotes devolver, y esa decisión ya la tomó el FEFO
cuando salieron.

**La factura exige RUC; la boleta no.** Lo decide el `codigo` del tipo de
comprobante.

## Convenciones que atraviesan todo

**Baja lógica.** Nada se borra: `is_active = false`. Una orden histórica puede
referirse a la fila.

**El importe lo calcula el servidor.** `monto_total`, `precio_venta` y
`precio_venta_tienda` se derivan; mandarlos se ignora. Que el cliente pueda
imponer un total es que el total no signifique nada.

**Los errores de la base se traducen.** Un SKU repetido sale como 409 y una FK
inexistente como 400, mirando el **SQLSTATE** y no el texto: PostgreSQL traduce
sus mensajes al idioma del servidor.

**Los importes viajan como texto.** `Decimal`, nunca `float`: los importes no
pueden arrastrar error de redondeo.

## Lo que falta para operar un market

El ciclo de la mercadería —entrada, stock, precio, salida— está cerrado. Alrededor quedan huecos.

**Faltan las otras salidas.** La venta ya descuenta stock, pero no hay mermas,
traslados entre almacenes ni ajuste por inventario físico. Todo lo que se pierde
o se mueve sin pasar por caja queda sin registrar.

**No hay usuarios ni autenticación.** `app/modules/usuarios/` está vacío y el
router CRUD llama a `crear(datos)` sin `usuario_id`, así que `created_by` y
`updated_by` son siempre `NULL`. La API está abierta y la auditoría, en blanco.

**Los perecibles no avisan por adelantado.** El FEFO ya saca primero lo que
vence antes, pero `producto_lote.dias_alerta_vencimiento` se guarda y nadie lo
consulta: no hay forma de ver qué está por caducar antes de que caduque.

**Los estados del lote no los mueve nadie.** `disponible` / `agotado` /
`inmovilizado` se quedan en lo que puso el alta.

**No hay cuentas por pagar.** `facturas.monto_pago` se edita a mano y los
módulos `bancos` y `cuentas` no están ligados a ningún pago.

**Los dos precios de venta pueden discrepar.** El del catálogo sale del precio
de compra que alguien carga; el de la tienda, del lote más caro en stock. Nada
los concilia ni avisa cuando se separan.
