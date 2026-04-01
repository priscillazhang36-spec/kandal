from pydantic import BaseModel, Field


class PhoneAuthRequest(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{1,14}$")
