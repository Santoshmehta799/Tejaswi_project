from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Format: postgresql://username:password@host:port/dbname
DATABASE_URL = "postgresql://postgres:root@127.0.0.1:5432/tejaswi"


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
