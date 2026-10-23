from pydantic import BaseModel, Field

from .OffersRequest import OffersRequest


class Offer(BaseModel):
    product_type: str
    amount: int = Field(gt=0)
    term_months: int = Field(gt=0)
    rate: float = Field(gt=0)
    collateral_value: int = Field(default=0, ge=0)
    collateral_type: str | None = None
    collateral_subtype: str | None = None


class ApprovalRequest(OffersRequest):
    offer: Offer
