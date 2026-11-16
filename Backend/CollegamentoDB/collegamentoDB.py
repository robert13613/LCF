import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

class DatabaseManager:
    def __init__(self):
        # Carica le variabili d'ambiente
        load_dotenv()
        
        # Recupera le credenziali
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.host = os.getenv("DB_HOST")
        self.port = os.getenv("DB_PORT")
        self.name = os.getenv("DB_NAME")
        
        # Costruisce la stringa di connessione
        self.database_url = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        
        # Crea il motore di SQLAlchemy e la fabbrica di sessioni
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.Base = declarative_base()

    def testa_connessione(self):
        """Metodo per verificare se tutto è andato a posto."""
        try:
            with self.engine.connect() as connection:
                print("✅ Collegamento al database PostgreSQL riuscito con successo!")
        except Exception as e:
            print(f"❌ Errore durante il collegamento: {e}")

    def get_session(self):
        """Metodo per ottenere l'oggetto che userai per fare le chiamate (query)."""
        return self.SessionLocal()

# Creiamo l'istanza principale (l'oggetto) che userai in tutto il progetto
db = DatabaseManager()

# Se esegui direttamente questo file (python collegamentoDB.py), fa il test
if __name__ == "__main__":
    db.testa_connessione()