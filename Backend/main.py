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