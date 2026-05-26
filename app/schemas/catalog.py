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


class CatalogSku(BaseModel):
    id: str
    name: str | None = None
    sku_code: str | None = None
    price: int
    old_price: int | None = None
    available_quantity: int = 0
    attributes: dict[str, object] = Field(default_factory=dict)
    images: list[ImageRef] = Field(default_factory=list)

    # Extra buyer-safe fields from the canonical flow and B2B public endpoint.
    discount: int = 0
    image: str | None = None
    active_quantity: int = 0
    in_stock: bool = False
    characteristics: list[dict[str, object]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_flow_aliases(self) -> "CatalogSku":
        self.active_quantity = self.available_quantity
        self.in_stock = self.available_quantity > 0
        if self.images and self.image is None:
            self.image = self.images[0].url
        return self


class CatalogProductDetail(CatalogProductCard):
    description: str
    attributes: dict[str, object] = Field(default_factory=dict)
    skus: list[CatalogSku] = Field(default_factory=list)

    # Extra buyer-safe fields from the canonical flow.
    status: str | None = None
    characteristics: list[dict[str, object]] = Field(default_factory=list)


class PaginatedCatalogProducts(BaseModel):
    items: list[CatalogProductCard]
    total_count: int
    limit: int
    offset: int


class FacetValue(BaseModel):
    value: str
    count: int


class Facet(BaseModel):
    name: str
    values: list[FacetValue]


class FacetsResponse(BaseModel):
    category_id: str | None = None
    facets: list[Facet]
