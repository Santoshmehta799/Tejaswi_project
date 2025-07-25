from fastapi import FastAPI
from app.routers import auth
from app.database import Base, engine

Base.metadata.create_all(bind=engine)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = ["http://localhost:3000", "http://77.37.47.74"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Working api====>"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
