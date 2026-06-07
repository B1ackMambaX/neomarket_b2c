from pydantic import BaseModel, ConfigDict, Field

DEFAULT_SUBSCRIPTION_EVENTS = ("BACK_IN_STOCK", "PRICE_DROP")


class ProductSubscriptionRequest(BaseModel):
    events: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SUBSCRIPTION_EVENTS),
        json_schema_extra={
            "default": list(DEFAULT_SUBSCRIPTION_EVENTS),
            "items": {
                "type": "string",
                "enum": list(DEFAULT_SUBSCRIPTION_EVENTS),
            },
        },
    )

    model_config = ConfigDict(extra="ignore")
