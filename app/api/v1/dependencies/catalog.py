from app.infrastructure.external.b2b_catalog_client import B2BCatalogClient


async def get_b2b_catalog_client() -> B2BCatalogClient:
    return B2BCatalogClient()
