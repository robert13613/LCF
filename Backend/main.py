from fastapi import FastAPI

app = FastAPI(title="Buby Solidale API", version="1.0.0")

@app.get("/scadenze")
def get_scadenze():
    return {
        "punto_ritiro": "Centro Sociale",
        "lista_fefo": [
            {"prodotto": "Pane fresco", "scadenza": "2026-11-18", "urgenza": "alta"},
            {"prodotto": "Mele", "scadenza": "2026-11-20", "urgenza": "media"}
        ],
        "trasferimenti_suggeriti": []
    }

@app.get("/impatto")
def get_impatto():
   
    return {
        "mese": "Novembre 2026",
        "punto_ritiro": "Centro Sociale",
        "dati": {
            "kg_recuperati": 1250.5,
            "kg_distribuiti": 1100.0,
            "kg_scartati": 50.0,
            "pasti_equivalenti": 2200
        }
    }

@app.get("/turni")
def get_turni():
   
    return {
        "data_riferimento": "2026-11-17",
        "turni_critici": [
            {"data": "2026-11-18", "fascia": "mattina", "stato": "scoperto", "ore_mancanti": 4},
            {"data": "2026-11-19", "fascia": "pomeriggio", "stato": "parziale", "ore_mancanti": 2}
        ]
    }

@app.get("/messaggi")
def get_messaggi():
    
    return {
        "segnalazioni_aperte": 2,
        "ultimi_messaggi": [
            {"fonte": "recensione", "voto": 5, "testo": "Servizio eccellente e volontari gentili."},
            {"fonte": "app", "priorita": "alta", "categoria": "frigo_guasto", "stato": "aperta"}
        ]
    }