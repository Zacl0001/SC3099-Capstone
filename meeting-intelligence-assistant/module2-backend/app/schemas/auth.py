# Define:
#
# RegisterRequest
# LoginRequest
# TokenResponse
# UserResponse

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from typing import Literal

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime