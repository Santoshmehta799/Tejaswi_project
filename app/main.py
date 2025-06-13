from fastapi import FastAPI
from app.database import Base, engine
from app.routers import auth

Base.metadata.create_all(bind=engine)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://14b3-103-240-78-208.ngrok-free.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

app.include_router(auth.router, prefix="/auth", tags=["auth"])


