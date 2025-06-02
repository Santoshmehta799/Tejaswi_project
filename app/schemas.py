from decimal import Decimal
import enum
from sqlalchemy import Enum
from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field
from .models import User, UserRole, Base
from typing import List, Optional, Literal


class LoginSchema(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole


class TradingName(str, enum.Enum):
    bharat = "bharat"
    green = "green"

class ShiftType(str, enum.Enum):
    day = "8AM-8PM"
    night = "8PM-8AM"

class StickerGeneratorCreate(BaseModel):
    quality_id: int
    colour_id: int
    product_type_id: int
    storage_location_id: int
    shift: ShiftType
    trading_name:TradingName
    production_date: date
    serial_number: str
    gsm: str
    net_weight: float
    gross_weight: float
    length: float
    width: float

class StickerGeneratorResponse(StickerGeneratorCreate):
    id: int
    product_number: str
    created_at: datetime
    created_by: int 
    qr_code_filename: Optional[str] = None


    class Config:
        orm_mode = True

class InventoryRecordResponse(BaseModel):
    product_code: str
    type: str
    weight: Decimal
    color: str
    quality: str
    
    class Config:
        from_attributes = True

class ProductNumberPreview(BaseModel):
    product_number: str

class ConfigItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class ConfigItemUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class ConfigItemResponse(BaseModel):
    id: int
    name: str
    
    class Config:
        orm_mode = True


class AdminConfigRequest(BaseModel):
    action: Literal["create", "update", "delete", "get", "list"]
    config_type: Literal["quality", "colour", "product_type", "storage_location", "all"]  # Added "all"
    name: Optional[str] = None
    item_id: Optional[int] = None

# class AdminConfigRequest(BaseModel):
#     config_type: Literal["quality", "colour", "product_type", "storage_location"]
#     action: Literal["create", "update", "delete", "list", "get"]
#     name: Optional[str] = None
#     item_id: Optional[int] = None
from typing import Union, List, Dict, Any, Optional

# class AdminConfigResponse(BaseModel):
#     success: bool
#     message: str
#     data: Optional[dict] = None
#     items: Optional[List[ConfigItemResponse]] = None

class AdminConfigResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    count: Optional[int] = None
    total_count: Optional[int] = None

class NameSchema(BaseModel):
    name: str

    class Config:
        orm_mode = True