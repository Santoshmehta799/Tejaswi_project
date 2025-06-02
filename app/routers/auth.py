import io
import json
import base64
from PIL import Image
from datetime import date
from jose import jwt, JWTError
from fastapi import Request
import qrcode
from io import BytesIO
from ..database import SessionLocal
from fastapi import Response, HTTPException
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from ..models import Colour, ProductType, Quality, StickerGenerator, StorageLocation, User
from ..schemas import AdminConfigRequest, AdminConfigResponse, ConfigItemCreate, InventoryRecordResponse, LoginSchema, \
    StickerGeneratorCreate, StickerGeneratorResponse, UserCreate
from ..utils import ACCESS_TOKEN_EXPIRE_MINUTES, authenticate_user, create_access_token, hash_password, verify_jwt_token, verify_password,create_refresh_token, \
    SECRET_KEY, ALGORITHM
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify JWT token dependency for FastAPI
    """
    token = credentials.credentials
    
    token_data = verify_jwt_token(token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data

@router.post("/users/")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = hash_password(user.password)
    
    db_user = User(
        username=user.username,
        password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "role": db_user.role.value}


@router.post("/login")
def login(user_credentials: LoginSchema, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Convert enum to string using .value
    access_token = create_access_token(data={
        "sub": str(user.id),
        "role": user.role.value  # ✅ Convert enum to string
    })
    
    refresh_token = create_refresh_token(data={
        "sub": str(user.id),
        "role": user.role.value  # ✅ Convert enum to string
    })
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


# @router.post("/login/")
# def login(payload: LoginSchema, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.username == payload.username).first()
#     if not user or not verify_password(payload.password, user.password):
#         raise HTTPException(status_code=401, detail="Invalid Credentials")
    
#     token_data = {"sub": user.username, "role": user.role.value}
#     access_token = create_access_token(token_data)
#     refresh_token = create_refresh_token(token_data)
    
#     return {
#         "access_token": access_token,
#         "refresh_token": refresh_token,
#         "token_type": "bearer"
#     }


@router.post("/refresh-token/")
def refresh_token(request: Request):
    refresh_token = request.headers.get("Authorization")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    
    token = refresh_token.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    new_access_token = create_access_token({"sub": username, "role": role})
    return {"access_token": new_access_token, "token_type": "bearer"}


def generate_qr_code(sticker_data: StickerGenerator) -> tuple[str, bytes, str]:
    """
    Generate QR code for sticker data
    Returns: (qr_data_string, qr_image_bytes, filename)
    """
    # Create QR code data (you can customize this structure)
    qr_data = {
        "id": sticker_data.id,
        "product_number": sticker_data.product_number,
        "serial_number": sticker_data.serial_number,
        "trading_name": sticker_data.trading_name,
        "production_date": sticker_data.production_date.isoformat(),
        "shift": sticker_data.shift,
        "quality_id": sticker_data.quality_id,
        "colour_id": sticker_data.colour_id,
        "product_type_id": sticker_data.product_type_id,
        "net_weight": float(sticker_data.net_weight),
        "gross_weight": float(sticker_data.gross_weight),
        "created_at": sticker_data.created_at.isoformat()
    }
    
    # Convert to JSON string
    qr_data_string = json.dumps(qr_data)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data_string)
    qr.make(fit=True)
    
    # Create QR code image
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    qr_image.save(img_buffer, format='PNG')
    img_bytes = img_buffer.getvalue()
    
    # Generate filename
    # filename = f"qr_sticker_{sticker_data.id}_{sticker_data.serial_number}.png"
    filename = f"qr_sticker_{sticker_data.product_number}_{sticker_data.id}.png"
    
    return qr_data_string, img_bytes, filename


def get_current_user(db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    """
    Get current user from database using token data
    """
    user_id = token_data["user_id"]
    
    # Replace 'User' with your actual user model
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

@router.post("/sticker-generator/", response_model=StickerGeneratorResponse)
def create_sticker(
    data: StickerGeneratorCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        # Generate product number first
        product_number = generate_product_number(db, data.shift, data.production_date)
        
        # Create sticker record with product number
        sticker_data = data.dict()
        sticker_data['product_number'] = product_number
        sticker_data['created_by'] = current_user.id
        
        new_sticker = StickerGenerator(**sticker_data)
        db.add(new_sticker)
        db.commit()
        db.refresh(new_sticker)
        
        # Generate QR code
        qr_data_string, qr_image_bytes, filename = generate_qr_code(new_sticker)
        
        # Update sticker with QR code data
        new_sticker.qr_code_data = qr_data_string
        new_sticker.qr_code_image = qr_image_bytes
        new_sticker.qr_code_filename = filename
        
        db.commit()
        db.refresh(new_sticker)
        
        return new_sticker
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating sticker: {str(e)}")

# VIEW
@router.get("/sticker-generator/{sticker_id}/qr-code")
def get_qr_code_image(sticker_id: int, db: Session = Depends(get_db)):
    sticker = db.query(StickerGenerator).filter(StickerGenerator.id == sticker_id).first()
    
    if not sticker:
        raise HTTPException(status_code=404, detail="Sticker not found")
    
    if not sticker.qr_code_image:
        raise HTTPException(status_code=404, detail="QR code not found for this sticker")
    
    return Response(
        content=sticker.qr_code_image,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={sticker.qr_code_filename}"}
    )


# DOWNLOAD
@router.get("/sticker-generator/{sticker_id}/qr-code/download")
def download_qr_code(sticker_id: int, db: Session = Depends(get_db)):
    sticker = db.query(StickerGenerator).filter(StickerGenerator.id == sticker_id).first()
    
    if not sticker:
        raise HTTPException(status_code=404, detail="Sticker not found")
    
    if not sticker.qr_code_image:
        raise HTTPException(status_code=404, detail="QR code not found for this sticker")
    
    return Response(
        content=sticker.qr_code_image,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename={sticker.qr_code_filename}"
        }
    )

# get product number
@router.get("/sticker-generator/preview-product-number")
def preview_product_number(shift: str, production_date: str, db: Session = Depends(get_db)):
    """Preview what the next product number would be for given shift and date"""
    try:
        from datetime import datetime
        date_obj = datetime.strptime(production_date, "%Y-%m-%d").date()
        product_number = generate_product_number(db, shift, date_obj)
        return {"product_number": product_number}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error generating preview: {str(e)}")


class AdminConfigService:
    def __init__(self):
        # Model mapping
        self.model_mapping = {
            "quality": Quality,
            "colour": Colour,
            "product_type": ProductType,
            "storage_location": StorageLocation
        }
        
        # Display names for better UX
        self.display_names = {
            "quality": "Quality",
            "colour": "Colour",
            "product_type": "Product Type",
            "storage_location": "Storage Location"
        }
    
    def get_model(self, config_type: str):
        """Get SQLAlchemy model based on config type"""
        if config_type not in self.model_mapping:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid config type. Available types: {list(self.model_mapping.keys())}"
            )
        return self.model_mapping[config_type]
    
    def create_item(self, config_type: str, name: str, db: Session):
        """Create new configuration item"""
        model = self.get_model(config_type)
        
        # Check if item already exists
        existing = db.query(model).filter(model.name.ilike(name.strip())).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"{self.display_names[config_type]} '{name}' already exists"
            )
        
        # Create new item
        new_item = model(name=name.strip())
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        
        return {
            "success": True,
            "message": f"{self.display_names[config_type]} '{name}' created successfully",
            "data": {"id": new_item.id, "name": new_item.name}
        }
    
    def update_item(self, config_type: str, item_id: int, name: str, db: Session):
        """Update existing configuration item"""
        model = self.get_model(config_type)
        
        # Find item
        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"{self.display_names[config_type]} not found"
            )
        
        # Check if new name already exists (excluding current item)
        existing = db.query(model).filter(
            model.name.ilike(name.strip()),
            model.id != item_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"{self.display_names[config_type]} '{name}' already exists"
            )
        
        # Update item
        old_name = item.name
        item.name = name.strip()
        db.commit()
        db.refresh(item)
        
        return {
            "success": True,
            "message": f"{self.display_names[config_type]} updated from '{old_name}' to '{name}'",
            "data": {"id": item.id, "name": item.name}
        }
    
    def delete_item(self, config_type: str, item_id: int, db: Session):
        """Delete configuration item"""
        model = self.get_model(config_type)
        
        # Find item
        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"{self.display_names[config_type]} not found"
            )
        
        # Check if item is being used (you may need to customize this based on your relationships)
        # For now, we'll allow deletion - add constraints as needed
        
        item_name = item.name
        db.delete(item)
        db.commit()
        
        return {
            "success": True,
            "message": f"{self.display_names[config_type]} '{item_name}' deleted successfully",
            "data": {"id": item_id, "name": item_name}
        }
    
    def get_item(self, config_type: str, item_id: int, db: Session):
        model = self.get_model(config_type)
        
        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"{self.display_names[config_type]} not found"
            )
        
        return {
            "success": True,
            "message": f"{self.display_names[config_type]} retrieved successfully",
            "data": {"id": item.id, "name": item.name}
        }
    
    def list_items(self, config_type: str, db: Session):
        """List all items of given type or all types"""
    
        # Define all models statically
        all_models = {
            "quality": Quality,
            "colour": Colour,
            "product_type": ProductType,
            "storage_location": StorageLocation
        }
        
        if config_type == "all" or not config_type:
            # Return data for all 4 models
            result = {
                "success": True,
                "message": "Retrieved all configuration items",
                "data": {},
                "total_count": 0
            }
            
            for model_name, model_class in all_models.items():
                items = db.query(model_class).order_by(model_class.name).all()
                result["data"][model_name] = [{"id": item.id, "name": item.name.capitalize(), "config_type": model_name} for item in items]
                result["total_count"] += len(items)
            
            return result
        
        else:
            # Return data for specific model (existing functionality)
            if config_type not in all_models:
                raise ValueError(f"Invalid config_type: {config_type}")
                
            model = all_models[config_type]
            items = db.query(model).order_by(model.name).all()
            
            return {
                "success": True,
                "message": f"Retrieved {len(items)} {config_type.replace('_', ' ')} items",
                "data": [{"id": item.id, "name": item.name} for item in items],
                "count": len(items)
            }

    
admin_service = AdminConfigService()

# from ..main import admin_service  

@router.post("/admin-config/manage", response_model=AdminConfigResponse)
def manage_config(
    request: AdminConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)

):
    """Dynamic admin configuration endpoint"""
    try:
        if request.action == "create":
            if not request.name:
                raise HTTPException(status_code=400, detail="Name is required for create action")
            return admin_service.create_item(request.config_type, request.name, db)
        
        elif request.action == "update":
            if not request.item_id or not request.name:
                raise HTTPException(status_code=400, detail="Both item_id and name are required for update action")
            return admin_service.update_item(request.config_type, request.item_id, request.name, db)
        
        elif request.action == "delete":
            if not request.item_id:
                raise HTTPException(status_code=400, detail="item_id is required for delete action")
            return admin_service.delete_item(request.config_type, request.item_id, db)
        
        elif request.action == "get":
            if not request.item_id:
                raise HTTPException(status_code=400, detail="item_id is required for get action")
            return admin_service.get_item(request.config_type, request.item_id, db)
        
        elif request.action == "list":
            return admin_service.list_items(request.config_type, db)
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    

@router.get("/master-names/")
def get_master_names(db: Session = Depends(get_db)):
    quality_list = db.query(Quality).all()
    colour_list = db.query(Colour).all()
    product_type_list = db.query(ProductType).all()
    storage_location_list = db.query(StorageLocation).all()

    return {
        "qualities": [{"id": q.id, "name": q.name} for q in quality_list],
        "colours": [{"id": c.id, "name": c.name} for c in colour_list],
        "product_types": [{"id": p.id, "name": p.name} for p in product_type_list],
        "storage_locations": [{"id": s.id, "name": s.name} for s in storage_location_list]
    }

# This is product number
def get_month_code(month: int) -> str:
    """Convert month number to month code (first and last letter of month name)"""
    month_names = [
        "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
        "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
    ]
    
    month_name = month_names[month - 1]
    return month_name[0] + month_name[-1]  # First and last letter

def get_shift_code(shift: str) -> str:
    """Convert shift string to shift code"""
    if shift == "8AM-8PM":
        return "A"
    elif shift == "8PM-8AM":
        return "B"
    else:
        raise ValueError(f"Invalid shift: {shift}")

def get_next_serial_number(db: Session, shift_code: str, day: str, month_code: str) -> str:
    """Get the next serial number for the given shift+date+month combination"""
    
    # Find the highest serial number for this shift+date+month combination
    prefix = f"{shift_code}{day}{month_code}"
    
    # Query for existing product numbers with this prefix
    existing_products = db.query(StickerGenerator.product_number).filter(
        StickerGenerator.product_number.like(f"{prefix}%")
    ).all()
    for i in existing_products:
        print("-========================>>>>",i)
    
    if not existing_products:
        return "001"
    
    # Extract serial numbers and find the maximum
    serial_numbers = []
    for (product_number,) in existing_products:
        if len(product_number) >= len(prefix) + 3:  # Ensure it has serial part
            serial_part = product_number[-3:]  # Last 3 digits
            try:
                serial_numbers.append(int(serial_part))
            except ValueError:
                continue  # Skip invalid serial numbers
    
    if not serial_numbers:
        return "001"
    
    next_serial = max(serial_numbers) + 1
    
    # Handle overflow (if somehow goes beyond 999, reset to 1)
    if next_serial > 999:
        next_serial = 1
    
    return f"{next_serial:03d}"  # Zero-pad to 3 digits

def generate_product_number(db: Session, shift: str, production_date: date) -> str:
    """Generate a complete product number based on shift and production date"""
    print("-------------------------yes this is call-------??")
    
    # Get shift code
    shift_code = get_shift_code(shift)
    
    # Get day (zero-padded to 2 digits)
    day = f"{production_date.day:02d}"
    
    # Get month code
    month_code = get_month_code(production_date.month)
    
    # Get next serial number
    serial = get_next_serial_number(db, shift_code, day, month_code)
    
    # Combine all parts
    product_number = f"{shift_code}{day}{month_code}{serial}"
    
    return product_number


from sqlalchemy import select
from typing import List

@router.get("/inventory/records", response_model=List[InventoryRecordResponse])
async def get_all_inventory_records(db: Session = Depends(get_db),current_user = Depends(get_current_user)):
    """
    Get all inventory records with only the fields shown in the inventory table:
    - Product Code (product_number)
    - Type (from product_type table)
    - Weight (net_weight)
    - Color (from colour table)
    - Quality (from quality table)
    """
    try:
        # Query with joins to get related data
        query = (
            select(
                StickerGenerator.product_number.label('product_code'),
                ProductType.name.label('type'),
                StickerGenerator.net_weight.label('weight'),
                Colour.name.label('color'),
                Quality.name.label('quality')
            )
            .join(ProductType, StickerGenerator.product_type_id == ProductType.id)
            .join(Colour, StickerGenerator.colour_id == Colour.id)
            .join(Quality, StickerGenerator.quality_id == Quality.id)
            .order_by(StickerGenerator.product_number)
        )
        
        result = db.execute(query)
        records = result.fetchall()
        
        # Convert to response format
        inventory_records = []
        for record in records:
            inventory_records.append(InventoryRecordResponse(
                product_code=record.product_code,
                type=record.type.capitalize(),
                weight=record.weight,
                color=record.color.capitalize(),
                quality=record.quality.capitalize()
            ))
        
        return inventory_records
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching inventory records: {str(e)}")