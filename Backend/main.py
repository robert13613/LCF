import os
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Buby Solidale API", version="1.0.0")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/impatto")
def get_impatto(db: Session = Depends(get_db)):
    """
    Restituisce le statistiche di impatto mensile leggendo la vista dal database.
    """
    query = text("SELECT * FROM solidale.v_impatto_mensile;")
    risultati = db.execute(query).mappings().all()
    
    return {
        "messaggio": "Dati estratti con successo da Supabase!",
        "dati_reali": risultati
    }