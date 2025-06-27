from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: UUID
    name: str
    email: EmailStr

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class ZooRead(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None

    class Config:
        orm_mode = True


class AnimalRead(BaseModel):
    id: UUID
    common_name: str

    class Config:
        orm_mode = True


class ZooVisitCreate(BaseModel):
    zoo_id: UUID
    visit_date: date
    notes: Optional[str] = None


class ZooVisitRead(BaseModel):
    id: UUID
    zoo_id: UUID
    visit_date: date
    notes: Optional[str] = None

    class Config:
        orm_mode = True


class AnimalSightingCreate(BaseModel):
    zoo_id: UUID
    animal_id: UUID
    sighting_datetime: datetime
    notes: Optional[str] = None


class AnimalSightingRead(BaseModel):
    id: UUID
    zoo_id: UUID
    animal_id: UUID
    sighting_datetime: datetime
    notes: Optional[str] = None
    photo_url: Optional[str] = None

    class Config:
        orm_mode = True
