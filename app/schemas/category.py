from pydantic import BaseModel, Field


class CategoryTreeItem(BaseModel):
    id: str
    name: str
    parent_id: str | None
    children: list["CategoryTreeItem"] = Field(
        default_factory=list
    )


CategoryTreeItem.model_rebuild()


class CategoryTreeResponse(BaseModel):
    items: list[CategoryTreeItem]


class BreadcrumbItem(BaseModel):
    id: str
    slug: str
    name: str
    url: str
    level: int
    is_current: bool


class BreadcrumbMeta(BaseModel):
    resolved_via: str
    category_id: str


class BreadcrumbResponse(BaseModel):
    data: list[BreadcrumbItem]
    meta: BreadcrumbMeta