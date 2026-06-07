from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    slug: str
    parent_id: Optional[str]
    description: str | None = None
    is_active: bool = True