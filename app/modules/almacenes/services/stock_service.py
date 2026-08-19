"""El stock del almacén, que sale de las recepciones.

Hasta acá recibir mercadería y que existiera stock eran dos actos
independientes: la recepción registraba lo que llegó y los lotes se cargaban a
mano contra la guía, sin que nada conciliara los dos números. Este módulo cierra
esa distancia —la línea de recepción alimenta el lote— y expone lo que el
almacén tiene disponible.

El lote es la unidad de stock: guarda su cantidad en la **unidad de venta** del
producto y vive en un almacén. La ficha (`producto_almacen`) guarda el mínimo y
el máximo, y puede estar en otra unidad, así que la comparación entre lo que hay
y lo que debería haber se hace **en unidad mínima**, como el resto del módulo.

La salida es **FEFO**: vence primero, sale primero. Es lo único que evita la
merma en un market con frescos, y por eso la venta consume por vencimiento y no
por antigüedad de ingreso.

El lote también guarda **lo que costó**, y de ahí sale el precio de la tienda:
`precio_venta_tienda` es el que corresponde al lote más caro que quede con
existencias. Vender por debajo de eso sería perder plata sobre la partida que
todavía está en el almacén. Si no queda ningún lote con stock no hay máximo que
tomar, así que la ficha conserva el precio que tenía: la regla no produce un
valor nuevo, no borra el anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictoError
from app.modules.almacenes.models.producto_almacen import ProductoAlmacen
from app.modules.almacenes.models.producto_lote import ProductoLote
from app.modules.movimientos.models.recepcion import Recepcion
from app.modules.movimientos.models.recepcion_detalle import RecepcionDetalle
from app.modules.productos.models.producto import Producto
from app.modules.productos.services.calculo_precio import calcular_precio_venta
from app.modules.productos.services.unidad_de_venta import unidad_venta_de
from app.modules.unidades.services.conversion import (
    a_unidad,
    a_unidades_minimas,
    factor_de,
)

#: Los importes se guardan con dos decimales (`Numeric(12, 2)`).
_CENTIMOS = Decimal("0.01")

#: Con cuántos caracteres del id de la recepción se arma el código del lote
#: cuando la línea no trae uno. Corto a propósito: entra en los 30 de la
#: columna y sigue siendo reconocible al leerlo.
_LARGO_ID_EN_CODIGO = 8


def codigo_de_lote(codigo_linea: str | None, recepcion_id: UUID) -> str:
    """El código con el que la línea entra al stock.

    No toda mercadería viene loteada. Cuando la línea no trae código se deriva
    uno de la recepción, y tiene que salir siempre el mismo: es lo que permite
    volver a calcular el lote cuando la línea se edita, en vez de ir dejando
    filas huérfanas por el camino.
    """
    if codigo_linea:
        return codigo_linea
    return f"REC-{str(recepcion_id)[:_LARGO_ID_EN_CODIGO]}"


@dataclass(frozen=True)
class StockDeProducto:
    """Lo que hay de un producto en un almacén, contra lo que debería haber."""

    producto_id: UUID
    unidad_venta_id: UUID
    disponible: int
    stock_minimo: int | None
    stock_maximo: int | None
    bajo_minimo: bool
    #: `False` cuando el producto tiene stock pero nadie le creó la ficha en
    #: este almacén: hay mercadería sin un mínimo contra el cual medirla.
    tiene_ficha: bool


async def sincronizar_lote(
    db: AsyncSession,
    almacen_id: UUID,
    producto_id: UUID,
    codigo_lote: str,
    usuario_id: UUID | None = None,
) -> ProductoLote | None:
    """Deja el lote con lo que suman las líneas de recepción que lo alimentan.

    Recalcula en vez de sumar sobre lo que había: así editar una línea, darla
    de baja o cargar una segunda entrega del mismo lote llegan todas al mismo
    número, y no hay forma de que dos caminos dejen el stock distinto.

    Devuelve `None` si no hay líneas ni lote: no se crea una fila en cero.
    """
    lineas = (
        await db.execute(
            select(
                RecepcionDetalle.codigo_lote,
                RecepcionDetalle.unidad_medida_id,
                RecepcionDetalle.cantidad_ingresada,
                RecepcionDetalle.precio_unitario,
                Recepcion.id,
                Recepcion.fecha,
                Recepcion.guia_remision_id,
            )
            .join(Recepcion, Recepcion.id == RecepcionDetalle.recepcion_id)
            .where(
                Recepcion.almacen_id == almacen_id,
                RecepcionDetalle.producto_id == producto_id,
                RecepcionDetalle.is_active.is_(True),
                Recepcion.is_active.is_(True),
            )
        )
    ).all()

    unidad_venta = await unidad_venta_de(db, producto_id)
    cantidad = 0
    precio_compra = Decimal("0")
    fechas: list[date] = []
    guias: list[UUID] = []
    for linea in lineas:
        if codigo_de_lote(linea.codigo_lote, linea.id) != codigo_lote:
            continue
        # `cantidad_ingresada` es lo que se **aceptó**, no lo que el camión
        # trajo: lo rechazado y lo que nunca llegó ya están afuera, contados en
        # `cantidad_devuelta`. Restarla acá descontaría dos veces la misma
        # mercadería y dejaría el lote por debajo de lo que hay en el estante.
        neto = linea.cantidad_ingresada
        if neto > 0:
            cantidad += await a_unidad(db, neto, linea.unidad_medida_id, unidad_venta)
        # Si el mismo lote llegó en varias entregas a distinto precio, manda la
        # más cara: es la que no hay que vender por debajo.
        precio_compra = max(
            precio_compra,
            await precio_por_unidad_de_venta(
                db, linea.precio_unitario, linea.unidad_medida_id, unidad_venta
            ),
        )
        fechas.append(linea.fecha)
        if linea.guia_remision_id is not None:
            guias.append(linea.guia_remision_id)

    lote = await db.scalar(
        select(ProductoLote).where(
            ProductoLote.almacen_id == almacen_id,
            ProductoLote.producto_id == producto_id,
            ProductoLote.codigo_lote == codigo_lote,
        )
    )
    if lote is None:
        if not fechas:
            return None
        lote = ProductoLote(
            almacen_id=almacen_id,
            producto_id=producto_id,
            codigo_lote=codigo_lote,
            # La primera entrega es la que fecha el lote; la guía, la primera
            # que lo respalde. Una recepción contra orden directa no tiene, y
            # el lote se queda sin ella.
            fecha_ingreso=min(fechas),
            guia_remision_id=guias[0] if guias else None,
            cantidad=cantidad,
            precio_compra=precio_compra,
            created_by=usuario_id,
        )
        db.add(lote)
        # Hace falta el id antes de que termine la transacción que lo pidió.
        await db.flush()
        return lote

    lote.cantidad = cantidad
    lote.precio_compra = precio_compra
    lote.updated_by = usuario_id
    if fechas:
        lote.fecha_ingreso = min(fechas)
    await db.flush()
    return lote


async def sincronizar_desde_linea(
    db: AsyncSession,
    recepcion_id: UUID,
    producto_id: UUID,
    codigo_linea: str | None,
    usuario_id: UUID | None = None,
) -> None:
    """Recalcula el lote al que apunta una línea de recepción."""
    recepcion = await db.get(Recepcion, recepcion_id)
    if recepcion is None:
        return
    await sincronizar_lote(
        db,
        recepcion.almacen_id,
        producto_id,
        codigo_de_lote(codigo_linea, recepcion_id),
        usuario_id,
    )
    await sincronizar_precio_de_tienda(
        db, recepcion.almacen_id, producto_id, usuario_id
    )


async def stock_del_almacen(
    db: AsyncSession,
    almacen_id: UUID,
    solo_bajo_minimo: bool = False,
) -> list[StockDeProducto]:
    """Lo disponible por producto, contra el mínimo de su ficha.

    Solo cuentan los lotes `disponible`: lo agotado o inmovilizado está en el
    almacén pero no se puede vender, y darlo por stock sería prometer algo que
    no se puede entregar.
    """
    filas = (
        await db.execute(
            select(
                ProductoLote.producto_id,
                Producto.unidad_venta,
                func.coalesce(func.sum(ProductoLote.cantidad), 0),
                ProductoAlmacen.stock_minimo,
                ProductoAlmacen.stock_maximo,
                ProductoAlmacen.unidad_medida_id,
            )
            .join(Producto, Producto.id == ProductoLote.producto_id)
            .outerjoin(
                ProductoAlmacen,
                (ProductoAlmacen.producto_id == ProductoLote.producto_id)
                & (ProductoAlmacen.almacen_id == ProductoLote.almacen_id)
                & (ProductoAlmacen.is_active.is_(True)),
            )
            .where(
                ProductoLote.almacen_id == almacen_id,
                ProductoLote.estado == "disponible",
                ProductoLote.is_active.is_(True),
            )
            .group_by(
                ProductoLote.producto_id,
                Producto.unidad_venta,
                ProductoAlmacen.stock_minimo,
                ProductoAlmacen.stock_maximo,
                ProductoAlmacen.unidad_medida_id,
            )
            .order_by(ProductoLote.producto_id)
        )
    ).all()

    stock: list[StockDeProducto] = []
    for producto_id, unidad_venta, disponible, minimo, maximo, unidad_ficha in filas:
        # El disponible va en unidad de venta y el mínimo en la de la ficha,
        # que no tienen por qué ser la misma: se comparan en unidad mínima.
        bajo_minimo = False
        if minimo is not None:
            bajo_minimo = await a_unidades_minimas(
                db, disponible, unidad_venta
            ) < await a_unidades_minimas(db, minimo, unidad_ficha)

        if solo_bajo_minimo and not bajo_minimo:
            continue

        stock.append(
            StockDeProducto(
                producto_id=producto_id,
                unidad_venta_id=unidad_venta,
                disponible=disponible,
                stock_minimo=minimo,
                stock_maximo=maximo,
                bajo_minimo=bajo_minimo,
                tiene_ficha=minimo is not None,
            )
        )
    return stock


async def precio_por_unidad_de_venta(
    db: AsyncSession,
    precio_unitario: Decimal,
    unidad_linea: UUID,
    unidad_venta: UUID,
) -> Decimal:
    """Lo que la línea cobra, reexpresado por unidad de venta.

    La recepción cobra por su propia unidad: 120.00 la caja de 12 son 10.00 la
    unidad. Se divide por el factor y no se usa `a_unidad` porque acá el
    resultado sí puede no ser exacto —un precio partido en tres— y redondear
    céntimos es legítimo, mientras que partir mercadería no lo es.
    """
    if unidad_linea == unidad_venta:
        return precio_unitario
    factor_linea = await factor_de(db, unidad_linea)
    factor_venta = await factor_de(db, unidad_venta)
    return (precio_unitario * Decimal(factor_venta) / Decimal(factor_linea)).quantize(
        _CENTIMOS, rounding=ROUND_HALF_UP
    )


async def precio_de_tienda(
    db: AsyncSession, almacen_id: UUID, producto_id: UUID
) -> Decimal | None:
    """El precio que corresponde al lote más caro con existencias.

    `None` cuando no queda ninguno: sin stock no hay máximo que tomar, y eso
    no es lo mismo que un precio de cero.
    """
    mayor = await db.scalar(
        select(func.max(ProductoLote.precio_compra)).where(
            ProductoLote.almacen_id == almacen_id,
            ProductoLote.producto_id == producto_id,
            ProductoLote.cantidad > 0,
            ProductoLote.estado == "disponible",
            ProductoLote.is_active.is_(True),
        )
    )
    if mayor is None:
        return None
    return await calcular_precio_venta(db, producto_id, mayor)


async def asegurar_ficha(
    db: AsyncSession,
    almacen_id: UUID,
    producto_id: UUID,
    usuario_id: UUID | None = None,
) -> ProductoAlmacen:
    """La ficha del producto en ese almacén, creándola si no existe.

    Registrar un lote **es** decir que ese producto vive en ese almacén. Sin la
    ficha, el stock quedaba invisible para `stock_del_almacen` y sin precio con
    el que venderlo: había mercadería que no se podía ni consultar ni cobrar.

    Nace con `stock_minimo` en cero a propósito. Nadie decidió todavía cuánto
    hay que tener de ese producto acá, y un mínimo inventado haría que cada
    cosa recién recibida pidiera reposición apenas bajara de una unidad. En
    cero, el aviso se queda callado hasta que alguien fije el número de verdad.

    La unidad es la de venta del producto: es en la que están los lotes y en la
    que se calcula el precio de tienda, así que la ficha no puede estar en otra
    sin que los tres números dejen de ser comparables.
    """
    # Se busca sin filtrar por `is_active`: la unicidad de la tabla no
    # distingue las dadas de baja, así que insertar una segunda chocaría contra
    # el índice. Si la ficha estaba de baja y vuelve a entrar mercadería, se
    # reactiva: el producto volvió a vivir en este almacén.
    ficha = await db.scalar(
        select(ProductoAlmacen).where(
            ProductoAlmacen.almacen_id == almacen_id,
            ProductoAlmacen.producto_id == producto_id,
        )
    )
    if ficha is not None:
        if not ficha.is_active:
            ficha.is_active = True
            ficha.updated_by = usuario_id
            await db.flush()
        return ficha

    ficha = ProductoAlmacen(
        almacen_id=almacen_id,
        producto_id=producto_id,
        unidad_medida_id=await unidad_venta_de(db, producto_id),
        stock_minimo=0,
        precio_venta_tienda=Decimal("0"),
        created_by=usuario_id,
    )
    db.add(ficha)
    # Hace falta que exista antes de que el precio la busque.
    await db.flush()
    return ficha


async def sincronizar_precio_de_tienda(
    db: AsyncSession,
    almacen_id: UUID,
    producto_id: UUID,
    usuario_id: UUID | None = None,
) -> None:
    """Deja la ficha con el precio del lote más caro que quede en el almacén.

    Si el producto todavía no tiene ficha acá, se crea: registrar un lote es
    decir que ese producto vive en ese almacén, y sin ficha el stock existiría
    sin precio con el que venderlo ni mínimo contra el cual medirlo.

    No toca el precio si está fijado a mano, ni si no queda stock del que sacar
    un máximo. En ese último caso la ficha conserva lo que tenía: quedarse sin
    mercadería no es motivo para perder el precio con el que se venía
    vendiendo.
    """
    ficha = await asegurar_ficha(db, almacen_id, producto_id, usuario_id)
    if ficha.precio_manual:
        return

    precio = await precio_de_tienda(db, almacen_id, producto_id)
    if precio is None:
        return

    ficha.precio_venta_tienda = precio
    ficha.updated_by = usuario_id
    await db.flush()


async def lotes_para_vender(
    db: AsyncSession, almacen_id: UUID, producto_id: UUID
) -> list[ProductoLote]:
    """Los lotes con existencias, en el orden en que hay que sacarlos.

    Vence primero, sale primero. El que está por caducar se va antes que el
    que aguanta, que es lo único que evita la merma en un market con frescos;
    sacar por antigüedad de ingreso dejaría vencer mercadería que entró después
    y caduca antes.

    Los lotes sin fecha de vencimiento van al final: no corren riesgo, así que
    no hay apuro en moverlos. Entre dos que vencen el mismo día decide la
    fecha de ingreso, para que el orden sea siempre el mismo.
    """
    filas = await db.execute(
        select(ProductoLote)
        .where(
            ProductoLote.almacen_id == almacen_id,
            ProductoLote.producto_id == producto_id,
            ProductoLote.cantidad > 0,
            ProductoLote.estado == "disponible",
            ProductoLote.is_active.is_(True),
        )
        .order_by(
            ProductoLote.fecha_vencimiento.asc().nullslast(),
            ProductoLote.fecha_ingreso.asc(),
        )
    )
    return list(filas.scalars().all())


async def descontar_stock(
    db: AsyncSession,
    almacen_id: UUID,
    producto_id: UUID,
    cantidad: int,
    usuario_id: UUID | None = None,
) -> list[tuple[ProductoLote, int]]:
    """Saca `cantidad` del almacén y dice de qué lotes salió.

    Corta con un 409 si no alcanza, **sin tocar nada**: vender lo que no hay
    dejaría el stock en negativo y el comprobante emitido igual, y el descuadre
    no aparecería hasta un inventario.
    """
    lotes = await lotes_para_vender(db, almacen_id, producto_id)
    disponible = sum(lote.cantidad for lote in lotes)
    if disponible < cantidad:
        raise ConflictoError(
            f"No hay stock suficiente: se piden {cantidad} unidades y el "
            f"almacén tiene {disponible}."
        )

    consumido: list[tuple[ProductoLote, int]] = []
    por_sacar = cantidad
    for lote in lotes:
        if por_sacar == 0:
            break
        sale = min(lote.cantidad, por_sacar)
        lote.cantidad -= sale
        lote.updated_by = usuario_id
        consumido.append((lote, sale))
        por_sacar -= sale

    await db.flush()
    return consumido


async def devolver_stock(
    db: AsyncSession,
    producto_lote_id: UUID,
    cantidad: int,
    usuario_id: UUID | None = None,
) -> None:
    """Devuelve al lote del que salió, no al primero que haya.

    Anular una venta tiene que dejar el almacén como estaba. Devolver por FEFO
    pondría la mercadería en un lote con otro vencimiento y el stock cuadraría
    en total mientras miente en el detalle.
    """
    lote = await db.get(ProductoLote, producto_lote_id)
    if lote is None:
        return
    lote.cantidad += cantidad
    lote.updated_by = usuario_id
    await db.flush()
