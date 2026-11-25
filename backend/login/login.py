import bcrypt
from CollegamentoDB.collegamentoDB import db
from models.utente import Utente

def esegui_login(email: str, password: str) -> dict:
    sessione = db.get_session()
    try:
        utente = sessione.query(Utente).filter(Utente.email == email).first()
        
        # Controllo esistenza utente e verifica password criptata
        if not utente or not bcrypt.checkpw(
            password.encode("utf-8"),
            utente.password_hash.encode("utf-8")
        ):
            return {
                "successo": False,
                "messaggio": "Email o password errate."
            }
            
        if not utente.attivo:
            return {
                "successo": False,
                "messaggio": "Account disattivato."
            }
            
        return {
            "successo": True,
            "messaggio": "Login effettuato con successo!",
            "id": utente.id,
            "ruolo": utente.ruolo,
            "soggetto_id": utente.soggetto_id
        }
        
    finally:
        sessione.close()