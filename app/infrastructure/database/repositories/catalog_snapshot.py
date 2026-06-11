from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.catalog_snapshot import CatalogSnapshotModel


class SQLAlchemyCatalogSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        product_id: str,
        category_id: str | None,
        title: str,
        characteristics: list[dict[str, Any]],
        min_price: int,
        has_stock: bool,
    ) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            insert(CatalogSnapshotModel)
            .values(
                product_id=product_id,
                category_id=category_id,
                title=title,
                characteristics=characteristics,
                min_price=min_price,
                has_stock=has_stock,
                is_active=True,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["product_id"],
                set_={
                    "category_id": category_id,
                    "title": title,
                    "characteristics": characteristics,
                    "min_price": min_price,
                    "has_stock": has_stock,
                    "is_active": True,
                    "updated_at": now,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def deactivate(self, product_id: str) -> None:
        stmt = (
            update(CatalogSnapshotModel)
            .where(CatalogSnapshotModel.product_id == product_id)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def set_stock(self, *, product_id: str, has_stock: bool) -> None:
        stmt = (
            update(CatalogSnapshotModel)
            .where(CatalogSnapshotModel.product_id == product_id)
            .values(has_stock=has_stock, updated_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_facets(
        self,
        *,
        category_id: str | None,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        where_clauses = ["cs.is_active = TRUE"]
        params: dict[str, Any] = {}

        if category_id:
            where_clauses.append("cs.category_id = :category_id")
            params["category_id"] = category_id

        for i, (name, values) in enumerate(filters.items()):
            if isinstance(values, str):
                values = [values]
            name_key = f"fn_{i}"
            params[name_key] = name
            if len(values) == 1:
                val_key = f"fv_{i}_0"
                params[val_key] = values[0]
                where_clauses.append(
                    f"EXISTS (SELECT 1 FROM jsonb_array_elements(cs.characteristics) AS fc "
                    f"WHERE fc->>'name' = :{name_key} AND fc->>'value' = :{val_key})"
                )
            else:
                value_conditions = []
                for j, v in enumerate(values):
                    val_key = f"fv_{i}_{j}"
                    params[val_key] = v
                    value_conditions.append(f"fc->>'value' = :{val_key}")
                val_or = " OR ".join(value_conditions)
                where_clauses.append(
                    f"EXISTS (SELECT 1 FROM jsonb_array_elements(cs.characteristics) AS fc "
                    f"WHERE fc->>'name' = :{name_key} AND ({val_or}))"
                )

        where_sql = " AND ".join(where_clauses)
        sql = text(
            f"""
            SELECT
                elem->>'name'  AS name,
                elem->>'value' AS value,
                COUNT(*)       AS count
            FROM catalog_snapshots cs,
                 jsonb_array_elements(cs.characteristics) AS elem
            WHERE {where_sql}
              AND elem->>'name'  IS NOT NULL
              AND elem->>'value' IS NOT NULL
            GROUP BY name, value
            ORDER BY name, count DESC
            """
        )

        result = await self._session.execute(sql, params)
        rows = result.fetchall()

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row.name, []).append(
                {"value": row.value, "count": row.count}
            )

        return [{"name": name, "values": vals} for name, vals in grouped.items()]
