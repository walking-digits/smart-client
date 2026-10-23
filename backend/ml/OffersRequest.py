from pydantic import BaseModel, Field


class OffersRequest(BaseModel):
    inn: str = Field(pattern=r"^\d{10}$|^\d{12}$")
