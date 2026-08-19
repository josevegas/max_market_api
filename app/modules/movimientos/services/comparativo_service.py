"""Comparativo de las cotizaciones de un pedido, para decidir cuál aprobar.

Un pedido aprobado genera una cotización por proveedor, y cada una cotiza solo
las líneas que ese proveedor distribuye. Elegir entre ellas mirando el monto
total es una trampa: quien cotiza la mitad del pedido siempre sale más barato.
Este módulo puntúa las cuatro cosas que de verdad deciden la compra y las pesa.

    precio               35%   más barato es mejor
    tiempo de entrega    25%   menos días es mejor
    stock atendido       20%   más cobertura del pedido es mejor
    condición de pago    20%   más días de crédito es mejor

**El precio se mide por unidad atendida**, no por monto total. Así el criterio
de precio mide caro/barato y el de stock atendido mide cobertura, cada uno una
cosa sola. Con el monto crudo los dos medirían en parte lo mismo y el de precio,
que pesa más, favorecería al proveedor que cotiza menos.

Las cantidades se comparan **en unidad mínima**, como en el resto del módulo: el
pedido puede estar en cajas y la cotización en unidades, y los números en crudo
darían por buena una cobertura que no es.

El puntaje de cada criterio es una razón contra el mejor valor del grupo, no una
posición en un ranking: una cotización 10% más cara saca 90 y no 0. Con una
escala por posiciones, dos cotizaciones casi iguales quedarían en 100 y 0, y el
comparativo diría que hay una diferencia grande donde no la hay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReferenciaInvalidaError
from app.modules.movimientos.constantes import CODIGO_RECHAZADO
from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.cotizacion_detalle import CotizacionDetalle
from app.modules.movimientos.models.estado import Estado
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.models.pedido_detalle import PedidoDetalle
from app.modules.proveedores.models.empresa import Empresa
from app.modules.unidades.services.conversion import a_unidades_minimas

#: Cuánto pesa cada criterio. Suman 100 y el comparativo lo verifica al arrancar
#: en vez de confiar: un peso mal tipeado daría puntajes que parecen buenos.
PESOS: dict[str, int] = {
    "precio": 35,
    "entrega": 25,
    "stock": 20,
    "pago": 20,
}

#: Criterios en los que **menos es mejor**. El resto son "más es mejor".
_MENOR_ES_MEJOR = frozenset({"precio", "entrega"})

#: Los puntajes se redondean a dos decimales: son para leer en pantalla, no para
#: encadenar cálculos.
_DOS = Decimal("0.01")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(_DOS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Criterio:
    """Un criterio ya evaluado para una cotización."""

    #: El valor crudo, en su propia unidad (soles por unidad, días, por ciento).
    #: `None` cuando no se puede medir: una cotización sin líneas no tiene
    #: precio por unidad, y eso no es lo mismo que tener precio cero.
    valor: Decimal | None
    #: 0 a 100, contra el mejor valor del grupo.
    puntaje: Decimal
    #: Lo que este criterio aporta al total: `puntaje * peso / 100`.
    aporte: Decimal


@dataclass
class CotizacionEvaluada:
    """Una cotización con sus cuatro criterios puntuados."""

    cotizacion_id: UUID
    proveedor_id: UUID
    proveedor: str
    estado_id: UUID
    estado: str
    #: Lo que dice el documento. Se devuelve para que la pantalla pueda mostrar
    #: el número real y no solo el normalizado.
    monto_total: Decimal
    tiempo_atencion: int
    condicion_pago_dias: int
    #: Unidades mínimas del pedido que esta cotización cubre.
    unidades_atendidas: int
    #: Soles por unidad mínima atendida. `None` si no atiende nada.
    precio_por_unidad: Decimal | None
    #: Qué porcentaje del pedido cubre, de 0 a 100.
    cobertura: Decimal
    #: Qué productos del pedido esta cotización **no** cotiza. Es la explicación
    #: de una cobertura baja, y sin ella el número no dice qué falta.
    productos_sin_cotizar: list[UUID] = field(default_factory=list)
    criterios: dict[str, Criterio] = field(default_factory=dict)
    puntaje_total: Decimal = Decimal("0")
    #: `True` en la de mayor puntaje. Si hay empate exacto lo llevan todas las
    #: empatadas: inventar un desempate escondería que el comparativo no las
    #: distingue.
    optimo: bool = False


@dataclass(frozen=True)
class Comparativo:
    """El cuadro completo, tal como lo consume la pantalla."""

    pedido_id: UUID
    requerimiento_id: UUID
    #: Unidades mínimas que pide el pedido: el denominador de la cobertura.
    unidades_pedidas: int
    pesos: dict[str, int]
    cotizaciones: list[CotizacionEvaluada]


async def _unidades_minimas_del_pedido(
    db: AsyncSession, pedido_id: UUID
) -> dict[UUID, int]:
    """Cuánto pide el pedido de cada producto, en unidad mínima."""
    lineas = (
        await db.execute(
            select(
                PedidoDetalle.producto_id,
                PedidoDetalle.cantidad,
                PedidoDetalle.unidad_medida_id,
            ).where(
                PedidoDetalle.pedido_id == pedido_id,
                PedidoDetalle.is_active.is_(True),
            )
        )
    ).all()

    pedido: dict[UUID, int] = {}
    for linea in lineas:
        minimas = await a_unidades_minimas(
            db, linea.cantidad, linea.unidad_medida_id
        )
        # Se acumula en vez de asignar: `pedido_detalle` no tiene única por
        # producto, así que dos líneas del mismo producto son válidas y las dos
        # cuentan.
        pedido[linea.producto_id] = pedido.get(linea.producto_id, 0) + minimas
    return pedido


async def _atendido_por_cotizacion(
    db: AsyncSession, cotizacion_id: UUID, pedido: dict[UUID, int]
) -> tuple[int, list[UUID]]:
    """Unidades mínimas del pedido que cubre esta cotización, y qué le falta.

    Cotizar **más** de lo pedido no sube la cobertura: se cuenta contra lo que
    el pedido pide, no contra lo que el proveedor ofrece. Sin ese tope, mandar
    el doble daría 200% y el criterio dejaría de medir cobertura.

    Un producto que el pedido no pide tampoco suma: es una línea que el
    proveedor agregó por su cuenta y no responde a lo que se necesita.
    """
    lineas = (
        await db.execute(
            select(
                CotizacionDetalle.producto_id,
                CotizacionDetalle.cantidad,
                CotizacionDetalle.unidad_medida_id,
            ).where(
                CotizacionDetalle.cotizacion_id == cotizacion_id,
                CotizacionDetalle.is_active.is_(True),
            )
        )
    ).all()

    cotizado: dict[UUID, int] = {}
    for linea in lineas:
        if linea.producto_id not in pedido:
            continue
        minimas = await a_unidades_minimas(
            db, linea.cantidad, linea.unidad_medida_id
        )
        cotizado[linea.producto_id] = cotizado.get(linea.producto_id, 0) + minimas

    atendido = sum(
        min(cantidad, pedido[producto_id])
        for producto_id, cantidad in cotizado.items()
    )
    faltan = [
        producto_id for producto_id in pedido if producto_id not in cotizado
    ]
    return atendido, faltan


def _puntuar(clave: str, valores: list[Decimal | None]) -> list[Decimal]:
    """Puntajes de 0 a 100 de un criterio, contra el mejor valor del grupo.

    Lo que no se puede medir saca 0: una cotización sin líneas no tiene precio
    por unidad, y dejarla fuera del criterio la haría competir por tres cuartos
    de los puntos en juego mientras las demás compiten por todos.
    """
    medibles = [v for v in valores if v is not None]
    if not medibles:
        return [Decimal("0")] * len(valores)

    menor_es_mejor = clave in _MENOR_ES_MEJOR
    mejor = min(medibles) if menor_es_mejor else max(medibles)

    # Nadie ofrece nada en un criterio de "más es mejor" —ninguno da crédito—:
    # el criterio no distingue y repartir puntos ahí sería inventar una
    # diferencia. Empatan todos los que sí se pueden medir.
    if mejor == 0 and not menor_es_mejor:
        return [Decimal("0") if v is None else Decimal("100") for v in valores]

    puntajes: list[Decimal] = []
    for valor in valores:
        if valor is None:
            puntajes.append(Decimal("0"))
        elif mejor == 0:
            # "Menos es mejor" con el mejor en cero (entrega inmediata, o gratis):
            # solo quien también está en cero lo iguala. La razón contra cero se
            # iría a infinito, así que se resuelve como un caso aparte.
            puntajes.append(Decimal("100") if valor == 0 else Decimal("0"))
        elif menor_es_mejor:
            puntajes.append(_redondear(Decimal("100") * mejor / valor))
        else:
            puntajes.append(_redondear(Decimal("100") * valor / mejor))
    return puntajes


async def comparar_cotizaciones(db: AsyncSession, pedido_id: UUID) -> Comparativo:
    """Las cotizaciones del pedido, puntuadas y con el óptimo marcado.

    Entran todas las activas, **incluidas las rechazadas**, pero una rechazada
    nunca queda marcada como óptima.

    Antes se las excluía, con el argumento de que una descartada no compite. Con
    la regla de que aprobar una rechaza a las demás eso dejaba el cuadro en una
    sola fila justo después de decidir, que es cuando más sirve: es el registro
    de contra qué se eligió a ese proveedor. Y como la escala no cambia al
    aprobar —el conjunto de cotizaciones es el mismo, solo cambian sus estados—,
    los números que justificaron la decisión siguen ahí después de tomarla.
    """
    if sum(PESOS.values()) != 100:
        raise ValueError(f"Los pesos del comparativo suman {sum(PESOS.values())}.")

    pedido = await db.get(Pedido, pedido_id)
    if pedido is None:
        raise ReferenciaInvalidaError(f"No existe el pedido {pedido_id}.")

    rechazado_id = await db.scalar(
        select(Estado.id).where(
            Estado.codigo == CODIGO_RECHAZADO, Estado.is_active.is_(True)
        )
    )

    filas = (
        await db.execute(
            select(Cotizacion, Empresa.razon_social, Estado.descripcion)
            .join(Empresa, Empresa.id == Cotizacion.proveedor_id)
            .join(Estado, Estado.id == Cotizacion.estado_id)
            .where(
                Cotizacion.pedido_id == pedido_id,
                Cotizacion.is_active.is_(True),
            )
            .order_by(Cotizacion.fecha, Empresa.razon_social)
        )
    ).all()

    pedido_por_producto = await _unidades_minimas_del_pedido(db, pedido_id)
    unidades_pedidas = sum(pedido_por_producto.values())

    evaluadas: list[CotizacionEvaluada] = []
    for cotizacion, proveedor, estado in filas:
        atendido, faltan = await _atendido_por_cotizacion(
            db, cotizacion.id, pedido_por_producto
        )
        # Un pedido sin líneas no tiene contra qué medir cobertura. Se informa
        # 0 y no 100: no se atendió nada porque no había nada que atender, y
        # decir "cubre todo" sería afirmar algo que no se comprobó.
        cobertura = (
            _redondear(Decimal(100) * Decimal(atendido) / Decimal(unidades_pedidas))
            if unidades_pedidas
            else Decimal("0")
        )
        precio_por_unidad = (
            _redondear(cotizacion.monto_total / Decimal(atendido))
            if atendido
            else None
        )
        evaluadas.append(
            CotizacionEvaluada(
                cotizacion_id=cotizacion.id,
                proveedor_id=cotizacion.proveedor_id,
                proveedor=proveedor,
                estado_id=cotizacion.estado_id,
                estado=estado,
                monto_total=cotizacion.monto_total,
                tiempo_atencion=cotizacion.tiempo_atencion,
                condicion_pago_dias=cotizacion.condicion_pago_dias,
                unidades_atendidas=atendido,
                precio_por_unidad=precio_por_unidad,
                cobertura=cobertura,
                productos_sin_cotizar=faltan,
            )
        )

    if not evaluadas:
        return Comparativo(
            pedido_id=pedido_id,
            requerimiento_id=pedido.requerimiento_id,
            unidades_pedidas=unidades_pedidas,
            pesos=dict(PESOS),
            cotizaciones=[],
        )

    valores: dict[str, list[Decimal | None]] = {
        "precio": [e.precio_por_unidad for e in evaluadas],
        "entrega": [Decimal(e.tiempo_atencion) for e in evaluadas],
        "stock": [e.cobertura for e in evaluadas],
        "pago": [Decimal(e.condicion_pago_dias) for e in evaluadas],
    }

    for clave, peso in PESOS.items():
        puntajes = _puntuar(clave, valores[clave])
        for i, (evaluada, puntaje) in enumerate(
            zip(evaluadas, puntajes, strict=True)
        ):
            evaluada.criterios[clave] = Criterio(
                valor=valores[clave][i],
                puntaje=puntaje,
                aporte=_redondear(puntaje * Decimal(peso) / Decimal(100)),
            )

    for evaluada in evaluadas:
        evaluada.puntaje_total = _redondear(
            sum((c.aporte for c in evaluada.criterios.values()), Decimal("0"))
        )

    # El óptimo se busca solo entre las que siguen en carrera: una rechazada
    # puede tener el mejor puntaje —se la descartó por algo que el cuadro no
    # mide— y sugerirla sería contradecir una decisión ya tomada.
    en_carrera = [e for e in evaluadas if e.estado_id != rechazado_id]
    if en_carrera:
        mejor = max(e.puntaje_total for e in en_carrera)
        for evaluada in en_carrera:
            evaluada.optimo = evaluada.puntaje_total == mejor

    # De mayor a menor puntaje: la pantalla muestra un cuadro de decisión, y el
    # orden en que se guardaron las cotizaciones no dice nada sobre cuál conviene.
    evaluadas.sort(key=lambda e: e.puntaje_total, reverse=True)

    return Comparativo(
        pedido_id=pedido_id,
        requerimiento_id=pedido.requerimiento_id,
        unidades_pedidas=unidades_pedidas,
        pesos=dict(PESOS),
        cotizaciones=evaluadas,
    )


async def comparativo_de_requerimiento(
    db: AsyncSession, requerimiento_id: UUID
) -> Comparativo:
    """Lo mismo, entrando por el requerimiento.

    Es la pregunta del usuario —"las cotizaciones de este requerimiento"— pero
    las cotizaciones cuelgan del pedido, no del requerimiento. Un requerimiento
    genera un solo pedido (`_ya_tiene_sucesor` lo garantiza), así que el salto
    es unívoco.
    """
    pedido_id = await db.scalar(
        select(Pedido.id).where(
            Pedido.requerimiento_id == requerimiento_id,
            Pedido.is_active.is_(True),
        )
    )
    if pedido_id is None:
        raise ReferenciaInvalidaError(
            f"El requerimiento {requerimiento_id} todavía no generó un pedido, "
            "así que no hay cotizaciones que comparar. Apruébelo primero."
        )
    return await comparar_cotizaciones(db, pedido_id)


async def contar_cotizaciones_del_pedido(db: AsyncSession, pedido_id: UUID) -> int:
    """Cuántas cotizaciones compiten. La pantalla lo usa para no ofrecer el
    comparativo cuando hay una sola: comparar una contra nada no informa."""
    return (
        await db.scalar(
            select(func.count(Cotizacion.id)).where(
                Cotizacion.pedido_id == pedido_id,
                Cotizacion.is_active.is_(True),
            )
        )
    ) or 0
