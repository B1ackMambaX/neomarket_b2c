# Импортируй сюда все модели, чтобы Alembic autogenerate их видел
# from app.infrastructure.database.models import order, company, user
from app.infrastructure.database.models.cart import CartItemModel
from app.infrastructure.database.models.order import OrderItemModel, OrderModel

__all__ = ["CartItemModel", "OrderItemModel", "OrderModel"]
