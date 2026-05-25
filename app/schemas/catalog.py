from pydantic import BaseModel, Field, model_validator


class ImageRef(BaseModel):
    id: str
    url: str
    alt: str | None = None
    ordering: int = 0
    is_main: bool = False


class CategoryRef(BaseModel):
    id: str
    name: str | None = None
    parent_id: str | None = None
    level: int | None = None
    path: list[str] = Field(default_factory=list)


class SellerRef(BaseModel):
    id: str | None = None
    display_name: str | None = None


class CatalogProductCard(BaseModel):
    id: str
    name: str
    slug: str | None = None
    category: CategoryRef | None = None
    min_price: int
    old_price: int | None = None
    has_stock: bool = True
    rating: float | None = None
    reviews_count: int = 0
    images: list[ImageRef] = Field(default_factory=list)
    seller: SellerRef | None = None

    # Extra fields from the canonical flow, kept in sync with canonical counterparts.
    title: str = ""
    image: str | None = None
    price: int = 0
    in_stock: bool = True
    is_in_cart: bool = False

    @model_validator(mode="after")
    def _sync_flow_aliases(self) -> "CatalogProductCard":
        self.title = self.name
        self.price = self.min_price
        self.in_stock = self.has_stock
        return self


class PaginatedCatalogProducts(BaseModel):
    items: list[CatalogProductCard]
    total_count: int
    limit: int
    offset: int
