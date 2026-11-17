# File: test_chiamata.py

from sqlalchemy import Column, Integer, String
from collegamentoDB import db

# 1. Definiamo la struttura della tabella (Modello)
class Volontario(db.Base):
    __tablename__ = "volontari" # Il nome esatto della tabella su PostgreSQL
    
    id = Column(Integer, primary_key=True)
    nome = Column(String)
    cognome = Column(String)

# 2. Apriamo la connessione per fare la chiamata
sessione = db.get_session()

try:
    # 3. LA CHIAMATA: "Cerca tutti i volontari"
    # In SQL sarebbe: SELECT * FROM volontari;
    lista_volontari = sessione.query(Volontario).all()
    
    # 4. Usiamo i dati estratti
    if not lista_volontari:
        print("Nessun volontario trovato nel database.")
    else:
        for persona in lista_volontari:
            print(f"Trovato volontario: {persona.nome} {persona.cognome}")

finally:
    # 5. Chiudiamo sempre la sessione alla fine per liberare memoria
    sessione.close()
