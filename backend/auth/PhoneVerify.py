from pydantic import Field

from backend.auth.PhoneRequest import PhoneRequest


class PhoneVerify(PhoneRequest):
    code: str = Field(min_length=6, max_length=6)
