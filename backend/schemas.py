from datetime import date
from typing import Literal
from pydantic import BaseModel, EmailStr, Field

BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
Lat = Field(ge=-90, le=90)
Lon = Field(ge=-180, le=180)

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone: str | None = Field(None, pattern=r"^\+?[0-9 \-]{7,20}$")
    role: Literal["donor", "requester"]

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class DonorIn(BaseModel):
    blood_group: BloodGroup
    latitude: float = Lat
    longitude: float = Lon
    availability: bool = True
    max_distance: float = Field(10, ge=1, le=100)
    last_donation_date: date | None = None

class RequestIn(BaseModel):
    blood_group: BloodGroup
    units_required: int = Field(ge=1, le=10)
    latitude: float = Lat
    longitude: float = Lon
    hospital_name: str = Field(min_length=2, max_length=200)
    emergency_level: Literal["critical", "urgent", "normal"] = "urgent"
    description: str | None = Field(None, max_length=1000)
    radius_km: float = Field(10, ge=1, le=100)

class RespondIn(BaseModel):
    accept: bool
