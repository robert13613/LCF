from sqlalchemy import Column, Integer, String, Boolean
from CollegamentoDB.collegamentoDB import db

class Utente(db.Base):
    __tablename__ = "utente"
    __table_args__ = {"schema": "riservato"}

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    ruolo = Column(String, nullable=False)
    soggetto_id = Column(String)
    attivo = Column(Boolean, default=True)