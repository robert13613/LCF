from sqlalchemy import Column, Integer, String, Boolean
from collegamentoDB import db

class Utente(db.Base):
    __tablename__ = "utente"
    __table_args__ = {"schema": "riservato"}
    
    id = Column(Integer, primary_key=True)
    email = Column(String)
    password_hash = Column(String)
    ruolo = Column(String)
    soggetto_id = Column(String)
    attivo = Column(Boolean)

sessione = db.get_session()

try:
    lista_utenti = sessione.query(Utente).all()
    
    if not lista_utenti:
        print("Nessun utente trovato nel database.")
    else:
        for utente in lista_utenti:
            print(f"✅ Trovato utente: ID={utente.id} | Email={utente.email} | Ruolo={utente.ruolo} | Soggetto={utente.soggetto_id}")

finally:
    sessione.close()