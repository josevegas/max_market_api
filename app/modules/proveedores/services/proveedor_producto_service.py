"""Qué productos distribuye cada proveedor y en cuánto tiempo los atiende.

El `tiempo_atencion` se cuenta en días **desde que se hace el pedido**, y es el
dato con el que Compras decide a quién comprar cuando varios proveedores
ofrecen el mismo producto.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import CRUDService
from app.core.exceptions import NoEncontradoError, ReferenciaInvalidaError
from app.modules.productos.models.producto import Producto
from app.modules.proveedores.models.empresa import Empresa
from app.modules.proveedores.models.proveedor_producto import ProveedorProducto
from app.modules.proveedores.schemas.proveedor_producto import (
    AsignacionProducto,
    ProveedorProductoCreate,
)


class ProveedorProductoService(CRUDService[ProveedorProducto]):
    modelo = ProveedorProducto
    entidad = "Producto del proveedor"

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    # ── Asignación ──────────────────────────────────────────────────────────

    async def asignar(
        self,
        empresa_id: UUID,
        producto_id: UUID,
        tiempo_atencion: int,
        usuario_id: UUID | None = None,
    ) -> ProveedorProducto:
        """Asigna un producto a un proveedor, o actualiza su tiempo si ya estaba.

        Es idempotente a propósito: volver a asignar algo que ya se distribuye
        es corregir el plazo, no un error. Sin esto, quien mantiene el catálogo
        tendría que consultar antes de cada alta para saber si va POST o PATCH.
        """
        await self._validar_proveedor(empresa_id)
        await self._validar_producto(producto_id)

        existente = await self.buscar(empresa_id, producto_id)
        if existente is not None:
            existente.tiempo_atencion = tiempo_atencion
            existente.is_active = True  # reactiva una asignación dada de baja
            existente.updated_by = usuario_id
            await self._guardar(existente)
            return existente

        return await self.crear(
            ProveedorProductoCreate(
                empresa_id=empresa_id,
                producto_id=producto_id,
                tiempo_atencion=tiempo_atencion,
            ),
            usuario_id=usuario_id,
        )

    async def asignar_varios(
        self,
        empresa_id: UUID,
        asignaciones: list[AsignacionProducto],
        usuario_id: UUID | None = None,
    ) -> list[ProveedorProducto]:
        """Alta masiva: es como se carga un catálogo de proveedor de verdad.

        Se valida el proveedor una sola vez y se recorre; si un producto no
        existe, se corta sin dejar la carga a medias (todo en la misma
        transacción).
        """
        await self._validar_proveedor(empresa_id)
        for asignacion in asignaciones:
            await self._validar_producto(asignacion.producto_id)

        resultado = []
        for asignacion in asignaciones:
            resultado.append(
                await self.asignar(
                    empresa_id,
                    asignacion.producto_id,
                    asignacion.tiempo_atencion,
                    usuario_id,
                )
            )
        return resultado

    async def quitar(
        self, empresa_id: UUID, producto_id: UUID, usuario_id: UUID | None = None
    ) -> ProveedorProducto:
        """Baja lógica: el proveedor deja de distribuir el producto.

        No se borra la fila porque una orden de compra histórica puede
        referirse a ella.
        """
        asignacion = await self.buscar(empresa_id, producto_id)
        if asignacion is None:
            raise NoEncontradoError(
                self.entidad, f"empresa={empresa_id} producto={producto_id}"
            )
        return await self.desactivar(asignacion.id, usuario_id)

    # ── Consultas ───────────────────────────────────────────────────────────

    async def buscar(
        self, empresa_id: UUID, producto_id: UUID
    ) -> ProveedorProducto | None:
        """La asignación de ese par, activa o no."""
        return (
            await self.db.execute(
                select(ProveedorProducto).where(
                    ProveedorProducto.empresa_id == empresa_id,
                    ProveedorProducto.producto_id == producto_id,
                )
            )
        ).scalar_one_or_none()

    async def productos_de(
        self, empresa_id: UUID, limite: int = 50, desplazamiento: int = 0
    ) -> list[dict]:
        """Catálogo de un proveedor, con el producto ya resuelto.

        Se ordena por tiempo de atención: lo primero que se quiere ver es lo
        que llega antes. El catálogo de un mayorista puede ser largo, así
        que va troceado como el resto de listados.
        """
        await self._validar_proveedor(empresa_id)
        filas = await self.db.execute(
            select(
                ProveedorProducto.id,
                ProveedorProducto.producto_id,
                Producto.sku,
                Producto.descripcion_corta,
                ProveedorProducto.tiempo_atencion,
            )
            .join(Producto, Producto.id == ProveedorProducto.producto_id)
            .where(
                ProveedorProducto.empresa_id == empresa_id,
                ProveedorProducto.is_active.is_(True),
            )
            .order_by(ProveedorProducto.tiempo_atencion, Producto.sku)
            .limit(limite)
            .offset(desplazamiento)
        )
        return [
            {
                "id": id_,
                "producto_id": producto_id,
                "sku": sku,
                "descripcion_corta": descripcion,
                "tiempo_atencion": tiempo,
            }
            for id_, producto_id, sku, descripcion, tiempo in filas
        ]

    async def proveedores_de(
        self, producto_id: UUID, limite: int = 50, desplazamiento: int = 0
    ) -> list[dict]:
        """Quiénes proveen un producto, del más rápido al más lento.

        Es la consulta que hace Compras antes de emitir una orden.
        """
        await self._validar_producto(producto_id)
        filas = await self.db.execute(
            select(
                ProveedorProducto.id,
                ProveedorProducto.empresa_id,
                Empresa.razon_social,
                Empresa.ruc,
                ProveedorProducto.tiempo_atencion,
            )
            .join(Empresa, Empresa.id == ProveedorProducto.empresa_id)
            .where(
                ProveedorProducto.producto_id == producto_id,
                ProveedorProducto.is_active.is_(True),
                Empresa.is_active.is_(True),
            )
            .order_by(ProveedorProducto.tiempo_atencion, Empresa.razon_social)
            .limit(limite)
            .offset(desplazamiento)
        )
        return [
            {
                "id": id_,
                "empresa_id": empresa_id,
                "razon_social": razon_social,
                "ruc": ruc,
                "tiempo_atencion": tiempo,
            }
            for id_, empresa_id, razon_social, ruc, tiempo in filas
        ]

    async def contar_productos_de(self, empresa_id: UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(ProveedorProducto)
                .where(
                    ProveedorProducto.empresa_id == empresa_id,
                    ProveedorProducto.is_active.is_(True),
                )
            )
            or 0
        )

    async def contar_proveedores_de(self, producto_id: UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(ProveedorProducto)
                .join(Empresa, Empresa.id == ProveedorProducto.empresa_id)
                .where(
                    ProveedorProducto.producto_id == producto_id,
                    ProveedorProducto.is_active.is_(True),
                    Empresa.is_active.is_(True),
                )
            )
            or 0
        )

    async def proveedor_mas_rapido(self, producto_id: UUID) -> dict | None:
        """El de menor tiempo de atención, o None si nadie lo provee."""
        proveedores = await self.proveedores_de(producto_id)
        return proveedores[0] if proveedores else None

    # ── Validaciones ────────────────────────────────────────────────────────

    async def _validar_proveedor(self, empresa_id: UUID) -> Empresa:
        """La empresa debe existir y estar marcada como proveedora.

        Sin esto se le podrían asignar productos a un cliente, y el catálogo
        de compras quedaría con datos que nadie puede usar.
        """
        empresa = await self.db.get(Empresa, empresa_id)
        if empresa is None:
            raise NoEncontradoError("Empresa", empresa_id)
        if not empresa.es_proveedor:
            raise ReferenciaInvalidaError(
                f"La empresa {empresa.razon_social} no está marcada como proveedora."
            )
        return empresa

    async def _validar_producto(self, producto_id: UUID) -> Producto:
        producto = await self.db.get(Producto, producto_id)
        if producto is None:
            raise NoEncontradoError("Producto", producto_id)
        return producto
