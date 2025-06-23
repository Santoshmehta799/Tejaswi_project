import re
import io
import json
import qrcode
import base64
from PIL import Image
from io import BytesIO
from typing import List
from datetime import date
from fastapi import Request
from typing import Optional
from datetime import datetime
from sqlalchemy import select
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy.orm import Session
from collections import defaultdict
from ..database import SessionLocal
from sqlalchemy.orm import joinedload
from fastapi import Response, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..models import (
    Colour,
    DispatchManager,
    ProductType,
    Quality,
    ScannedProduct,
    StickerGenerator,
    StorageLocation,
    User,
)
from ..schemas import (
    AdminConfigRequest,
    AdminConfigResponse,
    ConfigItemCreate,
    DeleteResponse,
    DispatchHistoryResponse,
    DispatchManagerCreate,
    DispatchManagerResponse,
    InventoryRecordResponse,
    LoginSchema,
    ProductDetailsResponse,
    ScannedItemSchema,
    StickerGeneratorCreate,
    StickerGeneratorResponse,
    StickerResponse,
    StickerUpdateRequest,
    StickerUpdateResponse,
    UserCreate,
)
from ..utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    hash_password,
    verify_jwt_token,
    create_refresh_token,
    SECRET_KEY,
    ALGORITHM,
)


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

    db_user = User(username=user.username, password=hashed_password, role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "role": db_user.role}


@router.post("/login")
def login(user_credentials: LoginSchema, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )

    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "role": user.role}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": user.role,
    }


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
        "created_at": sticker_data.created_at.isoformat(),
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
    qr_image.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    # Generate filename
    filename = f"qr_sticker_{sticker_data.product_number}_{sticker_data.id}.png"

    return qr_data_string, img_bytes, filename


def get_current_user(
    db: Session = Depends(get_db), token_data: dict = Depends(verify_token)
):
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
    current_user=Depends(get_current_user),
):
    try:

        if hasattr(data, "serial_number") and data.serial_number:
            serial_number = data.serial_number
        else:
            # Generate next serial number if not provided
            serial_number = get_next_serial_number_from_model(
                db, data.shift, data.production_date
            )

        # Generate product number first
        product_number = generate_product_number(
            data.shift, data.production_date, serial_number
        )

        # Create sticker record with product number
        sticker_data = data.dict()
        if "serial_number" in sticker_data:
            del sticker_data["serial_number"]

        sticker_data["product_number"] = product_number
        sticker_data["serial_number"] = serial_number
        sticker_data["created_by"] = current_user.id

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
    sticker = (
        db.query(StickerGenerator).filter(StickerGenerator.id == sticker_id).first()
    )

    if not sticker:
        raise HTTPException(status_code=404, detail="Sticker not found")

    if not sticker.qr_code_image:
        raise HTTPException(
            status_code=404, detail="QR code not found for this sticker"
        )

    return Response(
        content=sticker.qr_code_image,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={sticker.qr_code_filename}"},
    )


# get product number
@router.get("/sticker-generator/preview-product-number")
def preview_product_number(
    shift: str, production_date: str, db: Session = Depends(get_db)
):
    """Preview what the next product number would be for given shift and date"""
    try:
        from datetime import datetime

        date_obj = datetime.strptime(production_date, "%Y-%m-%d").date()
        product_number = generate_product_number(db, shift, date_obj)
        return {"product_number": product_number}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error generating preview: {str(e)}"
        )


class AdminConfigService:
    def __init__(self):
        # Model mapping
        self.model_mapping = {
            "quality": Quality,
            "colour": Colour,
            "product_type": ProductType,
            "storage_location": StorageLocation,
            # "clinet_name": DispatchManager
        }

        # Display names for better UX
        self.display_names = {
            "quality": "Quality",
            "colour": "Colour",
            "product_type": "Product Type",
            "storage_location": "Storage Location",
            # "clinet_name": "Client Name"
        }

    def get_model(self, config_type: str):
        """Get SQLAlchemy model based on config type"""
        if config_type not in self.model_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid config type. Available types: {list(self.model_mapping.keys())}",
            )
        return self.model_mapping[config_type]

    def create_colour_item(
        self, config_type: str, name: str, db: Session, is_white: Optional[bool] = None
    ):
        """Create new configuration item"""
        model = self.get_model(config_type)

        # Check if item already exists
        existing = db.query(model).filter(model.name.ilike(name.strip())).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"{self.display_names[config_type]} '{name}' already exists",
            )

        # Create new item with different logic for colour type
        if config_type == "colour":
            # For colour type, include is_white field
            if is_white is None:
                raise HTTPException(
                    status_code=400,
                    detail="is_white field is required for colour configuration",
                )
            new_item = model(name=name.strip(), is_white=is_white)
        else:
            # For other types, create normally
            new_item = model(name=name.strip())

        db.add(new_item)
        db.commit()
        db.refresh(new_item)

        # Prepare response data
        response_data = {"id": new_item.id, "name": new_item.name}
        if config_type == "colour":
            response_data["is_white"] = new_item.is_white

        return {
            "success": True,
            "message": f"{self.display_names[config_type]} '{name}' created successfully",
            "data": response_data,
        }

    def update_colour_item(
        self, config_type: str, item_id: int, is_white: bool, db: Session
    ):
        """Update is_white field for colour configuration item"""
        model = self.get_model(config_type)

        # Find the colour item by ID
        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"{self.display_names[config_type]} with ID {item_id} not found",
            )

        # Update the is_white field
        item.is_white = is_white

        try:
            db.commit()
            db.refresh(item)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update {self.display_names[config_type]}: {str(e)}",
            )

        # Prepare response data
        response_data = {
            "id": item.id,
            "name": item.name,
            "config_type": config_type,
            "is_white": item.is_white,
        }

        return {
            "success": True,
            "message": f"{self.display_names[config_type]} '{item.name}' updated successfully",
            "data": response_data,
        }

    def create_item(self, config_type: str, name: str, db: Session):
        """Create new configuration item"""
        model = self.get_model(config_type)

        # Check if item already exists
        existing = db.query(model).filter(model.name.ilike(name.strip())).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"{self.display_names[config_type]} '{name}' already exists",
            )

        # Create new item
        new_item = model(name=name.strip())
        db.add(new_item)
        db.commit()
        db.refresh(new_item)

        return {
            "success": True,
            "message": f"{self.display_names[config_type]} '{name}' created successfully",
            "data": {"id": new_item.id, "name": new_item.name},
        }

    # def client_name(self, config_type: str, select_client: str, db: Session):
    #     print("---------------------------------------------------")
    #     """Create new configuration item"""
    #     model = self.get_model(config_type)
    #     print("-=-=-111=-=-=>>>",model)
    #     # Check if item already exists
    #     existing = db.query(model).filter(model.select_client.ilike(select_client.strip())).first()
    #     print("--==-=-existing=-=--=>>>>>",existing)
    #     if existing:
    #         raise HTTPException(
    #             status_code=400,
    #             detail=f"{self.display_names[config_type]} '{select_client}' already exists"
    #         )

    #     # Create new item
    #     new_item = model(select_client=select_client.strip())
    #     db.add(new_item)
    #     db.commit()
    #     db.refresh(new_item)

    #     return {
    #         "success": True,
    #         "message": f"{self.display_names[config_type]} '{select_client}' created successfully",
    #         # "data": {"id": new_item.id, "name": new_item.name}
    #     }

    def update_item(self, config_type: str, item_id: int, name: str, db: Session):
        """Update existing configuration item"""
        model = self.get_model(config_type)

        # Find item
        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404, detail=f"{self.display_names[config_type]} not found"
            )

        # Check if new name already exists (excluding current item)
        existing = (
            db.query(model)
            .filter(model.name.ilike(name.strip()), model.id != item_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"{self.display_names[config_type]} '{name}' already exists",
            )

        # Update item
        old_name = item.name
        item.name = name.strip()
        db.commit()
        db.refresh(item)

        return {
            "success": True,
            "message": f"{self.display_names[config_type]} updated from '{old_name}' to '{name}'",
            "data": {"id": item.id, "name": item.name},
        }

    def delete_item(self, config_type: str, item_id: int, db: Session):
        """Delete configuration item"""
        model = self.get_model(config_type)

        # Find item
        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404, detail=f"{self.display_names[config_type]} not found"
            )

        # Check if item is being used (you may need to customize this based on your relationships)
        # For now, we'll allow deletion - add constraints as needed

        item_name = item.name
        db.delete(item)
        db.commit()

        return {
            "success": True,
            "message": f"{self.display_names[config_type]} '{item_name}' deleted successfully",
            "data": {"id": item_id, "name": item_name},
        }

    def get_item(self, config_type: str, item_id: int, db: Session):
        model = self.get_model(config_type)

        item = db.query(model).filter(model.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=404, detail=f"{self.display_names[config_type]} not found"
            )

        return {
            "success": True,
            "message": f"{self.display_names[config_type]} retrieved successfully",
            "data": {"id": item.id, "name": item.name},
        }

    def list_items(self, config_type: str, db: Session):
        """List all items of given type or all types"""

        # Define all models statically
        all_models = {
            "quality": Quality,
            "colour": Colour,
            "product_type": ProductType,
            "storage_location": StorageLocation,
        }

        if config_type == "all" or not config_type:
            # Return data for all 4 models
            result = {
                "success": True,
                "message": "Retrieved all configuration items",
                "data": {},
                "total_count": 0,
            }

            for model_name, model_class in all_models.items():
                items = db.query(model_class).order_by(model_class.name).all()
                if model_name == "colour":
                    result["data"][model_name] = [
                        {
                            "id": item.id,
                            "name": item.name.capitalize(),
                            "config_type": model_name,
                            "is_white": item.is_white,
                        }
                        for item in items
                    ]
                else:
                    result["data"][model_name] = [
                        {
                            "id": item.id,
                            "name": item.name.capitalize(),
                            "config_type": model_name,
                        }
                        for item in items
                    ]

                result["total_count"] += len(items)

                # result["data"][model_name] = [{"id": item.id, "name": item.name.capitalize(), "config_type": model_name} for item in items]
                # result["total_count"] += len(items)

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
                "count": len(items),
            }


admin_service = AdminConfigService()


@router.post("/admin-config/manage", response_model=AdminConfigResponse)
def manage_config(
    request: AdminConfigRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dynamic admin configuration endpoint"""
    try:
        if request.action == "create":
            if not request.name:
                raise HTTPException(
                    status_code=400, detail="Name is required for create action"
                )
            return admin_service.create_item(request.config_type, request.name, db)

        elif request.action == "create_colour":
            if not request.name:
                raise HTTPException(
                    status_code=400, detail="Name is required for create action"
                )
            return admin_service.create_colour_item(
                config_type=request.config_type,
                name=request.name,
                db=db,
                is_white=request.is_white,
            )

        # elif request.action == "create_client_name":
        #     if not request.name:
        #         raise HTTPException(status_code=400, detail="Name is required for create action")
        #     return admin_service.client_name(
        #         config_type=request.config_type,
        #         select_client=request.name,
        #         db=db,
        #     )

        elif request.action == "update_colour":
            if not request.id:
                raise HTTPException(
                    status_code=400, detail="ID is required for update action"
                )
            if request.is_white is None:
                raise HTTPException(
                    status_code=400,
                    detail="is_white field is required for update action",
                )
            return admin_service.update_colour_item(
                config_type=request.config_type,
                item_id=request.id,
                is_white=request.is_white,
                db=db,
            )

        elif request.action == "update":
            if not request.item_id or not request.name:
                raise HTTPException(
                    status_code=400,
                    detail="Both item_id and name are required for update action",
                )
            return admin_service.update_item(
                request.config_type, request.item_id, request.name, db
            )

        elif request.action == "delete":
            if not request.item_id:
                raise HTTPException(
                    status_code=400, detail="item_id is required for delete action"
                )
            return admin_service.delete_item(request.config_type, request.item_id, db)

        elif request.action == "get":
            if not request.item_id:
                raise HTTPException(
                    status_code=400, detail="item_id is required for get action"
                )
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
        "storage_locations": [
            {"id": s.id, "name": s.name} for s in storage_location_list
        ],
    }


# This is product number
def get_month_code(month: int) -> str:
    """Convert month number to month code (first and last letter of month name)"""
    month_names = [
        "JANUARY",
        "FEBRUARY",
        "MARCH",
        "APRIL",
        "MAY",
        "JUNE",
        "JULY",
        "AUGUST",
        "SEPTEMBER",
        "OCTOBER",
        "NOVEMBER",
        "DECEMBER",
    ]

    month_name = month_names[month - 1]
    return month_name[0] + month_name[-1]


def get_shift_code(shift: str) -> str:
    """Convert shift string to shift code"""
    if shift == "8AM-8PM":
        return "A"
    elif shift == "8PM-8AM":
        return "B"
    else:
        raise ValueError(f"Invalid shift: {shift}")


def get_next_serial_number_from_model(
    db: Session, shift: str, production_date: date
) -> str:
    """Get the next serial number by querying the serial_number field directly from the model"""

    # Query for existing serial numbers for this shift and production date
    existing_serials = (
        db.query(StickerGenerator.serial_number)
        .filter(
            StickerGenerator.shift == shift,
            StickerGenerator.production_date == production_date,
        )
        .all()
    )

    if not existing_serials:
        return "001"

    # Extract serial numbers and find the maximum
    serial_numbers = []
    for (serial_number,) in existing_serials:
        if serial_number:  # Check if serial_number is not None
            try:
                serial_numbers.append(int(serial_number))
            except ValueError:
                continue  # Skip invalid serial numbers

    if not serial_numbers:
        return "001"

    next_serial = max(serial_numbers) + 1

    # Handle overflow (if somehow goes beyond 999, reset to 1)
    if next_serial > 999:
        next_serial = 1

    return f"{next_serial:03d}"


# def generate_product_number(db: Session, shift: str, production_date: date) -> str:
def generate_product_number(
    shift: str, production_date: date, serial_number: str
) -> str:
    """Generate a complete product number based on shift, production date, and serial number"""
    print("-------------------------yes this is call-------??")

    # Get shift code
    shift_code = get_shift_code(shift)

    # Get day (zero-padded to 2 digits)
    day = f"{production_date.day:02d}"

    # Get month code
    month_code = get_month_code(production_date.month)

    # Ensure serial_number is 3 digits
    if isinstance(serial_number, str):
        # If it's already a string, try to format it as 3 digits
        try:
            serial_int = int(serial_number)
            formatted_serial = f"{serial_int:03d}"
        except ValueError:
            formatted_serial = serial_number  # Use as is if can't convert
    else:
        formatted_serial = f"{serial_number:03d}"

    # Combine all parts using the provided serial number
    product_number = f"{shift_code}{day}{month_code}{serial_number}"

    return product_number


@router.get("/inventory/records", response_model=List[InventoryRecordResponse])
def get_all_inventory_records(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
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
                StickerGenerator.product_number.label("product_code"),
                ProductType.name.label("type"),
                StickerGenerator.net_weight.label("net_weight"),
                StickerGenerator.gross_weight.label("gross_weight"),
                StickerGenerator.width.label("width"),
                StickerGenerator.length.label("length"),
                StickerGenerator.gsm.label("gsm"),
                Colour.name.label("color"),
                Quality.name.label("quality"),
                StickerGenerator.is_sold.label("is_sold"),
                StickerGenerator.quality_id.label("quality_id"),
                StickerGenerator.colour_id.label("colour_id"),
                StickerGenerator.product_type_id.label("product_type_id"),
                StickerGenerator.leminated.label("leminated"),
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
            inventory_records.append(
                InventoryRecordResponse(
                    product_code=record.product_code,
                    type=record.type.capitalize(),
                    net_weight=record.net_weight,
                    gross_weight=record.gross_weight,
                    width=record.width,
                    length=record.length,
                    gsm=record.gsm,
                    color=record.color.capitalize(),
                    quality_id=record.quality_id,
                    colour_id=record.colour_id,
                    product_type_id=record.product_type_id,
                    quality=record.quality.capitalize(),
                    is_sold=record.is_sold,
                    leminated=record.leminated,
                )
            )

        return inventory_records

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching inventory records: {str(e)}"
        )


@router.get("/inventroy-data/{product_number}/qr-code", response_model=StickerResponse)
def get_sticker_by_product_number(
    product_number: str,
    db: Session = Depends(get_db),
    # current_user = Depends(get_current_user)
):
    """
    Get sticker data by product number
    """
    sticker = (
        db.query(StickerGenerator)
        .filter(StickerGenerator.product_number == product_number)
        .options(
            # Eager load relationships to avoid N+1 queries
            joinedload(StickerGenerator.colour),
            joinedload(StickerGenerator.quality),
            joinedload(StickerGenerator.product_type),
        )
        .first()
    )

    if not sticker:
        raise HTTPException(
            status_code=404,
            detail=f"Sticker with product number '{product_number}' not found",
        )
    if sticker.qr_code_image:
        sticker.qr_code_base64 = base64.b64encode(sticker.qr_code_image).decode("utf-8")
    else:
        sticker.qr_code_base64 = None

    return sticker


@router.get("/scan-qr-code/", response_model=List[ProductDetailsResponse])
def get_sticker_by_product_number(
    product_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get sticker data and maintain history for user
    """
    try:
        # 1. Get the product detail
        result = (
            db.query(
                ProductType.name.label("product_type"),
                Quality.name.label("quality"),
                Colour.name.label("colour"),
                StickerGenerator.net_weight,
                StickerGenerator.gross_weight,
                StickerGenerator.length,
                StickerGenerator.width,
                StickerGenerator.gsm,
            )
            .join(ProductType, StickerGenerator.product_type_id == ProductType.id)
            .join(Quality, StickerGenerator.quality_id == Quality.id)
            .join(Colour, StickerGenerator.colour_id == Colour.id)
            .filter(StickerGenerator.product_number == product_number)
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Product with number '{product_number}' not found",
            )

        # 2. Check if already stored for user
        existing = (
            db.query(ScannedProduct)
            .filter_by(user_id=current_user.id, product_number=product_number)
            .first()
        )

        if not existing:
            # 3. Save to scanned history
            scanned = ScannedProduct(
                user_id=current_user.id,
                product_number=product_number,
                product_type=result.product_type.capitalize(),
                quality=result.quality.capitalize(),
                colour=result.colour.capitalize(),
                net_weight=str(result.net_weight),
                gross_weight=result.gross_weight,
                length=result.length,
                width=result.width,
                gsm=result.gsm,
            )
            db.add(scanned)
            db.commit()

        # 4. Return all scanned product data for this user
        scanned_products = (
            db.query(ScannedProduct)
            .filter_by(user_id=current_user.id)
            .order_by(ScannedProduct.created_at.asc())
            .all()
        )

        return [
            ProductDetailsResponse(
                product_number=sp.product_number,
                product_type=sp.product_type,
                quality=sp.quality,
                colour=sp.colour,
                net_weight=sp.net_weight,
                gross_weight=sp.gross_weight,
                length=sp.length,
                width=sp.width,
                gsm=sp.gsm,
            )
            for sp in scanned_products
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving product: {str(e)}"
        )


@router.get("/scanned-products/", response_model=List[ProductDetailsResponse])
def get_all_scanned_products(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Get all scanned products for the current user
    """
    try:
        # Get all scanned products for this user
        scanned_products = (
            db.query(ScannedProduct)
            .filter_by(user_id=current_user.id)
            .order_by(ScannedProduct.created_at.desc())
            .all()
        )

        return [
            ProductDetailsResponse(
                product_number=sp.product_number,
                product_type=sp.product_type,
                quality=sp.quality,
                colour=sp.colour,
                net_weight=sp.net_weight,
                gross_weight=sp.gross_weight,
                length=sp.length,
                width=sp.width,
                gsm=sp.gsm,
            )
            for sp in scanned_products
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving scanned products: {str(e)}"
        )


# DELETE endpoint to delete product by product_number
@router.delete("/scanned-products/{product_number}")
def delete_scanned_product(
    product_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Find the product by product_number
    product = (
        db.query(ScannedProduct)
        .filter(ScannedProduct.product_number == product_number)
        .first()
    )

    # Check if product exists
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with number '{product_number}' not found",
        )

    # Delete the product
    db.delete(product)
    db.commit()

    return {
        "message": f"Product with number '{product_number}' has been successfully deleted",
        "deleted_product": {
            "id": product.id,
            "product_number": product.product_number,
            "product_type": product.product_type,
            "user_id": product.user_id,
        },
    }


@router.delete("/delete-sticker/{product_number}", response_model=DeleteResponse)
def delete_sticker_by_product_number(
    product_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sticker = (
        db.query(StickerGenerator)
        .filter(StickerGenerator.product_number == product_number)
        .first()
    )

    if not sticker:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(sticker)
    db.commit()

    return {
        "detail": f"Product with product_number '{product_number}' has been deleted successfully"
    }


def parse_scanned_item(item_string: str) -> ScannedItemSchema:
    """
    Parse scanned item string like: [A24MY001] - Premium - White - Roll - 45.6kg
    """
    # pattern = r'\[([^\]]+)\]\s*-\s*([^-]+)\s*-\s*([^-]+)\s*-\s*([^-]+)\s*-\s*([\d.]+)kg'
    pattern = (
        r"\[([^\]]+)\]\s*-\s*"  # product_number
        r"([^-]+)\s*-\s*"  # quality
        r"([^-]+)\s*-\s*"  # colour
        r"([^-]+)\s*-\s*"  # product_type
        r"([\d.]+)kg\s*-\s*"  # weight
        r"([\d.]+)gw\s*-\s*"  # gross_weight
        r"([\d.]+)l\s*-\s*"  # length
        r"([\d.]+)w\s*-\s*"  # width
        r"(\d+)gsm"  # gsm
    )
    match = re.match(pattern, item_string.strip())

    if not match:
        raise ValueError(f"Invalid scanned item format: {item_string}")

    # product_number, quality, colour, product_type, weight = match.groups()
    (
        product_number,
        quality,
        colour,
        product_type,
        weight,
        gross_weight,
        length,
        width,
        gsm,
    ) = match.groups()

    return ScannedItemSchema(
        product_number=product_number.strip(),
        quality=quality.strip(),
        colour=colour.strip(),
        product_type=product_type.strip(),
        weight=float(weight),
        gross_weight=float(gross_weight),
        length=float(length),
        width=float(width),
        gsm=gsm.strip(),
    )


def group_and_summarize_scanned_items(scanned_items_dict):
    """
    Group scanned items by color -> quality -> product_type and create summary
    """
    # Create nested structure: color -> quality -> product_type
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # Group the data
    for item in scanned_items_dict:
        color = item.get("colour", "Unknown")
        quality = item.get("quality", "Unknown")
        product_type = item.get("product_type", "Unknown")

        grouped[color][quality][product_type].append(item)

    # Create the hierarchical output structure
    result = {}

    for color, qualities in grouped.items():
        result[color] = {}

        for quality, product_types in qualities.items():
            result[color][quality] = []

            for product_type, items in product_types.items():
                # Calculate totals for this product type
                total_weight = sum(item.get("weight", 0) for item in items)
                count = len(items)

                result[color][quality].append(
                    {
                        "type": product_type,
                        "pieces": count,
                        "total_weight_kg": round(total_weight, 2),
                    }
                )

    return result


@router.post("/dispatch-manager/", response_model=DispatchManagerResponse)
def create_dispatch(
    dispatch_data: DispatchManagerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a new dispatch manager entry
    """
    try:
        # Parse scanned items
        parsed_items = []
        for item_string in dispatch_data.scanned_items:
            parsed_item = parse_scanned_item(item_string)
            parsed_items.append(parsed_item)

        # Calculate totals
        total_weight = sum(item.weight for item in parsed_items)
        total_items = len(parsed_items)

        # Convert parsed items to dict for JSON storage
        scanned_items_dict = [item.dict() for item in parsed_items]

        # Generate dispatch summary using the grouping logic
        dispatch_summary = group_and_summarize_scanned_items(scanned_items_dict)

        # Create database entry
        db_dispatch = DispatchManager(
            select_client=dispatch_data.select_client,
            vehicle_number=dispatch_data.vehicle_number,
            driver_contact=dispatch_data.driver_contact,
            scanned_items=scanned_items_dict,
            disptach_summary=dispatch_summary,
            total_items=total_items,
            total_weight=total_weight,
        )
        db.add(db_dispatch)
        db.commit()
        db.refresh(db_dispatch)

        # Get all scanned products for current user before deletion
        scanned_products = (
            db.query(ScannedProduct).filter_by(user_id=current_user.id).all()
        )

        # Extract product numbers from scanned products
        product_numbers = [product.product_number for product in scanned_products]

        # Mark corresponding StickerGenerator records as sold
        # if product_numbers:
        #     db.query(StickerGenerator).filter(
        #         StickerGenerator.product_number.in_(product_numbers)
        #     ).update({"is_sold": True}, synchronize_session=False)

        if product_numbers:
            deleted_count = (
                db.query(StickerGenerator)
                .filter(StickerGenerator.product_number.in_(product_numbers))
                .delete(synchronize_session=False)
            )
            print(
                f"Deleted ===================>>>{deleted_count} StickerGenerator records"
            )

        # Clean up scanned products for current user
        db.query(ScannedProduct).filter_by(user_id=current_user.id).delete()
        db.commit()

        # Return response
        return DispatchManagerResponse(
            id=db_dispatch.id,
            select_client=dispatch_data.select_client,
            vehicle_number=dispatch_data.vehicle_number,
            driver_contact=dispatch_data.driver_contact,
            scanned_items=parsed_items,
            dispatch_summary=dispatch_summary,
            total_items=total_items,
            total_weight=total_weight,
            created_at=db_dispatch.created_at,
            updated_at=db_dispatch.updated_at,
            status="pending",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/dispatch-manager/history", response_model=List[DispatchHistoryResponse])
def get_dispatch_history(
    start_date: Optional[date] = Query(
        None, description="Start date filter (YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get all dispatch history - simple version
    """
    try:
        # Start with base query
        query = db.query(DispatchManager)

        # Apply date filters if provided
        if start_date:
            # Convert date to datetime for comparison (start of day)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(DispatchManager.created_at >= start_datetime)

        if end_date:
            # Convert date to datetime for comparison (end of day)
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(DispatchManager.created_at <= end_datetime)

        # Order by created_at descending and execute query
        dispatches = query.order_by(DispatchManager.created_at.desc()).all()

        return dispatches

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/dispatch-managers/{dispatch_id}", response_model=DispatchManagerResponse)
def get_dispatch_manager(
    dispatch_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    # Query the database for the dispatch manager
    dispatch_manager = (
        db.query(DispatchManager).filter(DispatchManager.id == dispatch_id).first()
    )

    # Check if dispatch manager exists
    if not dispatch_manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispatch manager with ID {dispatch_id} not found",
        )

    return dispatch_manager


@router.put(
    "/sticker-generator/update/{product_number}", response_model=StickerUpdateResponse
)
def update_sticker(
    product_number: str,
    update_data: StickerUpdateRequest,
    db: Session = Depends(get_db),
    # current_user = Depends(get_current_user)
):
    """
    Update specific fields of a sticker by product number
    """
    try:
        sticker = (
            db.query(StickerGenerator)
            .filter(StickerGenerator.product_number == product_number)
            .first()
        )

        if not sticker:
            raise HTTPException(
                status_code=404,
                detail=f"Product with number '{product_number}' not found",
            )

        # Check if sticker is already sold
        if sticker.is_sold:
            raise HTTPException(status_code=400, detail="Cannot update sold product")

        # Validate foreign key references before updating
        if update_data.product_type_id:
            product_type = (
                db.query(ProductType)
                .filter(ProductType.id == update_data.product_type_id)
                .first()
            )
            if not product_type:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product type with ID {update_data.product_type_id} not found",
                )

        if update_data.colour_id:
            colour = db.query(Colour).filter(Colour.id == update_data.colour_id).first()
            if not colour:
                raise HTTPException(
                    status_code=404,
                    detail=f"Colour with ID {update_data.colour_id} not found",
                )

        if update_data.quality_id:
            quality = (
                db.query(Quality).filter(Quality.id == update_data.quality_id).first()
            )
            if not quality:
                raise HTTPException(
                    status_code=404,
                    detail=f"Quality with ID {update_data.quality_id} not found",
                )

        # Update only the provided fields
        updated_fields = []

        if update_data.product_type_id is not None:
            sticker.product_type_id = update_data.product_type_id
            updated_fields.append("product_type_id")

        if update_data.colour_id is not None:
            sticker.colour_id = update_data.colour_id
            updated_fields.append("colour_id")

        if update_data.quality_id is not None:
            sticker.quality_id = update_data.quality_id
            updated_fields.append("quality_id")

        if update_data.net_weight is not None:
            sticker.net_weight = update_data.net_weight
            updated_fields.append("net_weight")

        if update_data.gross_weight is not None:
            sticker.gross_weight = update_data.gross_weight
            updated_fields.append("gross_weight")

        if update_data.length is not None:
            sticker.length = update_data.length
            updated_fields.append("length")

        if update_data.width is not None:
            sticker.width = update_data.width
            updated_fields.append("width")

        if update_data.is_sold is not None:
            sticker.is_sold = update_data.is_sold
            updated_fields.append("is_sold")

        if update_data.leminated is not None:
            sticker.leminated = update_data.leminated
            updated_fields.append("leminated")

        if not updated_fields:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # Commit the changes
        db.commit()
        db.refresh(sticker)

        # Prepare response
        response_data = {
            "id": sticker.id,
            "product_number": sticker.product_number,
            "product_type_id": sticker.product_type_id,
            "colour_id": sticker.colour_id,
            "quality_id": sticker.quality_id,
            "net_weight": float(sticker.net_weight),
            "gross_weight": float(sticker.gross_weight),
            "length": float(sticker.length),
            "width": float(sticker.width),
            "is_sold": sticker.is_sold,
            "leminated": sticker.leminated,
            "message": f"Successfully updated fields: {', '.join(updated_fields)}",
        }

        return StickerUpdateResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating sticker: {str(e)}")
