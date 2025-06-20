import enum
from typing import Optional
from decimal import Decimal
from sqlalchemy import Enum
from datetime import date, datetime
from pydantic import BaseModel, Field
from .models import User, UserRole, Base
from typing import List, Optional, Literal
from typing import Union, List, Dict, Any, Optional



class LoginSchema(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str


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

class RelatedItem(BaseModel):
    id: int
    name: str
    
    class Config:
        orm_mode = True

class StickerGeneratorResponse(StickerGeneratorCreate):
    id: int
    product_number: str
    created_at: datetime
    created_by: int 
    qr_code_filename: Optional[str] = None

    colour: Optional[RelatedItem] = None
    quality: Optional[RelatedItem] = None
    product_type: Optional[RelatedItem] = None
    storage_location: Optional[RelatedItem] = None


    class Config:
        orm_mode = True

class InventoryRecordResponse(BaseModel):
    product_code: str
    type: str
    net_weight: Decimal
    length: Decimal
    width: Decimal
    gross_weight: Decimal
    gsm: int
    color: str
    quality: str
    colour_id: int
    quality_id: int
    product_type_id: int
    is_sold: Optional[bool] = False
    leminated: Optional[bool] = False

    
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
    action: Literal["create", "update", "delete", "get", "list","create_colour", "update_colour"]
    config_type: Literal["quality", "colour", "product_type", "storage_location", "all"]  # Added "all"
    # action: Literal["create", "update", "delete", "get", "list","create_colour", "update_colour", "create_client_name"]
    # config_type: Literal["quality", "colour", "product_type", "storage_location", "all", "clinet_name"]  # Added "all"
    name: Optional[str] = None
    item_id: Optional[int] = None
    id: Optional[int] = None
    is_white: Optional[bool] = None


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

class ProductDetailsResponse(BaseModel):
    product_number:str
    product_type: str
    quality: str
    colour: str
    net_weight: Optional[Decimal]
    gross_weight: Optional[Decimal]
    length: Optional[Decimal]
    width: Optional[Decimal]
    gsm: Optional[str]
    
    class Config:
        from_attributes = True

class ScannedItemSchema(BaseModel):
    product_number: str
    quality: str
    colour: str
    product_type: str
    weight: float
    gross_weight: float
    length: float
    width: float
    gsm: str

    
    class Config:
        from_attributes = True

class DispatchManagerResponse(BaseModel):
    id: int
    select_client: str
    vehicle_number: str
    driver_contact: str
    scanned_items: List[ScannedItemSchema]
    disptach_summary: Optional[dict] = None
    total_items: int
    total_weight: float
    created_at: datetime
    updated_at: datetime
    status: str
    
    class Config:
        from_attributes = True

class DispatchManagerCreate(BaseModel):
    select_client: str = Field(..., description="Client name")
    vehicle_number: str = Field(..., description="Vehicle number")
    driver_contact: str = Field(..., description="Driver contact number")
    scanned_items: List[str] = Field(..., description="List of scanned item strings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "select_client": "ABC Company",
                "vehicle_number": "ABC-1234",
                "driver_contact": "9876543210",
                "scanned_items": [
                    "[A24MY001] - Premium - White - Roll - 45.6kg",
                    "[A24MY002] - Premium - Blue - Roll - 42.2kg",
                    "[A24MY003] - Premium - White - Patti - 12.4kg"
                ]
            }
        }

class DispatchHistoryResponse(BaseModel):
    id: int
    select_client: str
    created_at: datetime
    total_items: int
    total_weight: float
    vehicle_number: str
    driver_contact: str
    scanned_items: List[dict]


class StickerUpdateRequest(BaseModel):
    # product_number: str
    product_type_id: Optional[int] = None
    colour_id: Optional[int] = None
    quality_id: Optional[int] = None
    net_weight: Optional[float] = None
    gross_weight: Optional[float] = None
    length: Optional[float] = None
    width: Optional[float] = None
    is_sold : Optional[bool] = None
    leminated: Optional[bool] = None

# Response model
class StickerUpdateResponse(BaseModel):
    id: int
    product_number: str
    product_type_id: int
    colour_id: int
    quality_id: int
    net_weight: float
    gross_weight: float
    length: float
    width: float
    is_sold: bool
    leminated: bool
    message: str
    
    class Config:
        orm_mode = True

class DeleteResponse(BaseModel):
    detail: str


class ColourResponse(BaseModel):
    # id: int
    name: str 
    
    class Config:
        from_attributes = True

class QualityResponse(BaseModel):
    # id: int
    name: str
    
    class Config:
        from_attributes = True

class ProductTypeResponse(BaseModel):
    # id: int
    name: str 
    
    class Config:
        from_attributes = True

class StickerResponse(BaseModel):
    colour: Optional[ColourResponse]
    quality: Optional[QualityResponse]
    product_type: Optional[ProductTypeResponse]
    serial_number: Optional[str]
    gsm: Optional[str]
    net_weight: Optional[Decimal]
    gross_weight: Optional[Decimal]
    length: Optional[Decimal]
    width: Optional[Decimal]
    trading_name: Optional[str]
    qr_code_base64: Optional[str]
    qr_code_filename: Optional[str]
    
    class Config:
        from_attributes = True