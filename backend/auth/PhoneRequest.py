from pydantic import BaseModel, Field


class PhoneRequest(BaseModel):
    phone: str = Field(pattern=r"^(\+7|8)\d{10}$")
