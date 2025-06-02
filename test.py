from enum import Enum
from pydantic import BaseModel

class TradingName(str, Enum):
    bharat = "bharat"
    green = "green"

class StickerGeneratorCreate(BaseModel):
    quality_id: int
    colour_id: int
    product_type_id: int
    storage_location_id: int
    trading_name: TradingName

print(StickerGeneratorCreate.schema_json(indent=2))
