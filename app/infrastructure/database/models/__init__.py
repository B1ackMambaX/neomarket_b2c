# Импортируй сюда все модели, чтобы Alembic autogenerate их видел
# from app.infrastructure.database.models import order, company, user
from app.infrastructure.database.models.cart import CartItemModel

__all__ = ["CartItemModel"]
