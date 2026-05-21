from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.config.settings import settings

# Si se usa un Connection Pooler (como el de Supabase), desactivamos el pool de SQLAlchemy en el cliente
# con NullPool para evitar conflictos y no agotar el límite de conexiones.
if "pooler" in settings.DATABASE_URL or "supabase.co" in settings.DATABASE_URL:
    engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
else:
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()