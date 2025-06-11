import enum
from .database import Base
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Date, DateTime, DECIMAL, \
    CheckConstraint, Text, LargeBinary, UniqueConstraint, JSON, Float, Boolean


class UserRole(enum.Enum):
    ADMIN_USER = "admin_user"
    STICKER_GUYS = "sticker_guys"
    DISPATCH_GUYS = "dispatch_guys"

class ShiftType(enum.Enum):
    A = "A (8AM-8PM)"
    B = "B (8PM-8AM)"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)



class TradingName(enum.Enum):
    BHARAT = "bharat"
    GREEN = "green"

class Quality(Base):
    __tablename__ = "quality"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))

class Colour(Base):
    __tablename__ = "colour"

    name = Column(String(100))
    id = Column(Integer, primary_key=True, index=True)
    is_white = Column(Boolean, nullable=False) 

class ProductType(Base):
    __tablename__ = "product_type"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))

class StorageLocation(Base):
    __tablename__ = "storage_location"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))


class StickerGenerator(Base):
    __tablename__ = "stickergenerator"

    id = Column(Integer, primary_key=True, index=True)
    product_number = Column(String(50), unique=True, nullable=False, index=True)
    quality_id = Column(Integer, ForeignKey("quality.id"))
    colour_id = Column(Integer, ForeignKey("colour.id"))
    product_type_id = Column(Integer, ForeignKey("product_type.id"))
    storage_location_id = Column(Integer, ForeignKey("storage_location.id"))
    trading_name = Column(String(20))
    shift = Column(String(20))
    production_date = Column(Date)
    serial_number = Column(String(100))
    gsm = Column(String(10))
    net_weight = Column(DECIMAL(10, 2))
    gross_weight = Column(DECIMAL(10, 2))
    length = Column(DECIMAL(10, 2))
    width = Column(DECIMAL(10, 2))

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    qr_code_data = Column(Text)  
    qr_code_image = Column(LargeBinary)  
    qr_code_filename = Column(String(255)) 
    is_sold = Column(Boolean, default=False)
    leminated = Column(Boolean, default=False)

    colour = relationship("Colour")
    product_type = relationship("ProductType")
    storage_location = relationship("StorageLocation")
    quality = relationship("Quality")

    __table_args__ = (
    CheckConstraint("trading_name IN ('bharat', 'green')", name="check_trading_name_valid"),
    CheckConstraint("shift IN ('8AM-8PM', '8PM-8AM')", name="check_shift_valid"), 
    UniqueConstraint('product_number', name='uq_product_number'),
    )  


class ScannedProduct(Base):
    __tablename__ = "scanned_products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_number = Column(String, index=True)
    product_type = Column(String)
    quality = Column(String)
    colour = Column(String)
    net_weight = Column(String)
    gross_weight = Column(DECIMAL(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow) 


class DispatchManager(Base):
    __tablename__ = "dispatch_managers"

    id = Column(Integer, primary_key=True, index=True)
    select_client = Column(String, nullable=False)
    vehicle_number = Column(String, nullable=False)
    driver_contact = Column(String, nullable=False)
    scanned_items = Column(JSON)
    disptach_summary = Column(JSON)
    total_items = Column(Integer, default=0)
    total_weight = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="pending")
