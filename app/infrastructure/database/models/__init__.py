# Импортируй сюда все модели, чтобы Alembic autogenerate их видел
# from app.infrastructure.database.models import order, company, user
from app.infrastructure.database.models.cart import CartItemModel
from app.infrastructure.database.models.collection import (
    CollectionModel,
    CollectionProductModel,
)
from app.infrastructure.database.models.favorite import FavoriteModel
from app.infrastructure.database.models.order import OrderItemModel, OrderModel
from app.infrastructure.database.models.subscription import ProductSubscriptionModel

__all__ = [
    "CartItemModel",
    "CollectionModel",
    "CollectionProductModel",
    "FavoriteModel",
    "OrderItemModel",
    "OrderModel",
    "ProductSubscriptionModel",
]
