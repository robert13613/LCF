from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Il CORS è fondamentale: permette al tuo frontend (JS) di fare richieste 
# al backend (Python) senza essere bloccato dal browser per motivi di sicurezza.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In produzione si inserisce l'URL esatto del frontend
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definiamo la struttura dei dati che ci aspettiamo dal JavaScript
class Numeri(BaseModel):
    numero1: float
    numero2: float

# Creiamo il punto di accesso (endpoint) che riceve i dati ed esegue l'addizione
@app.post("/api/somma")
def fai_addizione(dati: Numeri):
    totale = dati.numero1 + dati.numero2
    return {"risultato": totale} # Restituisce un JSON al frontend