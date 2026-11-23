import os
import re
from datetime import date, datetime, timezone
from typing import List, Optional, Literal
from fastapi import FastAPI, APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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

app = FastAPI(title="Buby Solidale – API", version="0.2.0-bozza")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ApiError(Exception):
    def __init__(self, status_code: int, codice: str, messaggio: str):
        self.status_code = status_code
        self.codice = codice
        self.messaggio = messaggio

@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"errore": {"codice": exc.codice, "messaggio": exc.messaggio}}
    )

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    is_body = any(err["loc"][0] == "body" for err in errors if err.get("loc"))
    dettagli = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in errors])
    if is_body:
        return JSONResponse(
            status_code=422,
            content={"errore": {"codice": "dati_non_validi", "messaggio": dettagli}}
        )
    return JSONResponse(
        status_code=400,
        content={"errore": {"codice": "parametro_non_valido", "messaggio": dettagli}}
    )


class NuovaSostituzione(BaseModel):
    sostituto_id: str = Field(..., pattern=r"^V\d{3}$")

class NuovoFeedback(BaseModel):
    ruolo_autore: Literal["volontario", "beneficiario", "donatore", "visitatore"]
    punto_id: Optional[str] = Field(None, pattern=r"^PR\d{2}$")
    voto: int = Field(..., ge=1, le=5)
    commento: Optional[str] = Field(None, max_length=2000)

class RigaNuovaDonazione(BaseModel):
    categoria_id: int
    prodotto: str = Field(..., min_length=1, max_length=200)
    quantita: float = Field(..., gt=0)
    unita: Literal["kg", "pz"]

class NuovaDonazione(BaseModel):
    donatore_id: str = Field(..., pattern=r"^D\d{3}$")
    punto_id: str = Field(..., pattern=r"^PR\d{2}$")
    data: date
    righe: List[RigaNuovaDonazione] = Field(..., min_length=1)
    nota: Optional[str] = Field(None, max_length=1000)


def risolvi_settimana(db: Session, settimana: Optional[date]) -> date:
    if settimana is not None:
        if settimana.weekday() != 0:
            giorni_it = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
            giorno_nome = giorni_it[settimana.weekday()]
            raise ApiError(
                400,
                "parametro_non_valido",
                f"settimana deve essere un lunedì: {settimana.isoformat()} è un {giorno_nome}."
            )
        return settimana

    ultima = db.execute(text("""
        SELECT MAX(data_rilevazione)
        FROM solidale.giacenza
        WHERE EXTRACT(ISODOW FROM data_rilevazione) = 1;
    """)).scalar()
    if not ultima:
        oggi = date.today()
        return date.fromordinal(oggi.toordinal() - oggi.weekday())
    return ultima

def verifica_punto(db: Session, punto_id: str):
    esiste = db.execute(
        text("SELECT 1 FROM solidale.punto_ritiro WHERE id = :p;"),
        {"p": punto_id}
    ).scalar()
    if not esiste:
        raise ApiError(404, "non_trovato", f"Il punto {punto_id} non esiste.")

def anonimizza_testo(testo: Optional[str]) -> Optional[str]:
    if not testo:
        return testo

    testo = re.sub(
        r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b",
        "[CF]",
        testo,
        flags=re.IGNORECASE
    )

    testo = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "[EMAIL]",
        testo
    )

    testo = re.sub(
        r"(?:\+39\s?)?(?:0\d{1,3}[\s.-]?\d{5,8}|3\d{2}[\s.-]?\d{6,7})\b",
        "[TELEFONO]",
        testo
    )
    return testo

api = APIRouter(prefix="/api")

@api.get("/anagrafiche", tags=["Comuni"])
def leggi_anagrafiche(db: Session = Depends(get_db)):
    punti = db.execute(text("""
        SELECT id, nome, comune, frigorifero, capienza_kg
        FROM solidale.punto_ritiro
        ORDER BY id;
    """)).mappings().all()

    categorie = db.execute(text("""
        SELECT id, nome, macro, unita_standard, deperibile, richiede_frigo
        FROM solidale.categoria_prodotto
        ORDER BY id;
    """)).mappings().all()

    date_bounds = db.execute(text("""
        SELECT MIN(data_rilevazione) AS prima, MAX(data_rilevazione) AS ultima
        FROM solidale.giacenza
        WHERE EXTRACT(ISODOW FROM data_rilevazione) = 1;
    """)).mappings().first()

    return {
        "punti": [dict(p) for p in punti],
        "categorie": [dict(c) for c in categorie],
        "settimane": {
            "prima": date_bounds["prima"].isoformat() if date_bounds and date_bounds["prima"] else None,
            "ultima": date_bounds["ultima"].isoformat() if date_bounds and date_bounds["ultima"] else None
        }
    }

@api.get("/scadenze", tags=["Scadenze"])
def leggi_scadenze(
    punto: str = Query(..., pattern=r"^PR\d{2}$"),
    settimana: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    verifica_punto(db, punto)
    sett = risolvi_settimana(db, settimana)

    righe_raw = db.execute(text("""
        SELECT
            g.categoria_id,
            c.nome AS categoria,
            g.kg,
            g.kg_stimato,
            g.scadenza_piu_vicina,
            (g.scadenza_piu_vicina - :sett) AS giorni_alla_scadenza,
            c.richiede_frigo
        FROM solidale.giacenza g
        JOIN solidale.categoria_prodotto c ON c.id = g.categoria_id
        WHERE g.punto_id = :punto
          AND g.data_rilevazione = :sett
          AND g.kg > 0
        ORDER BY (g.scadenza_piu_vicina - :sett) ASC NULLS LAST;
    """), {"punto": punto, "sett": sett}).mappings().all()

    righe = []
    kg_in_giacenza = 0.0
    kg_urgenza_alta = 0.0
    kg_scaduti = 0.0

    for r in righe_raw:
        giorni = r["giorni_alla_scadenza"]
        kg_val = round(float(r["kg"]), 1)
        kg_in_giacenza += kg_val

        if giorni is None:
            urgenza = "nessuna"
        elif giorni < 0:
            urgenza = "scaduta"
            kg_scaduti += kg_val
        elif giorni <= 2:
            urgenza = "alta"
            kg_urgenza_alta += kg_val
        elif giorni <= 7:
            urgenza = "media"
        else:
            urgenza = "bassa"

        righe.append({
            "categoria_id": r["categoria_id"],
            "categoria": r["categoria"],
            "kg": kg_val,
            "kg_stimato": bool(r["kg_stimato"]),
            "scadenza_piu_vicina": r["scadenza_piu_vicina"].isoformat() if r["scadenza_piu_vicina"] else None,
            "giorni_alla_scadenza": giorni,
            "urgenza": urgenza,
            "richiede_frigo": bool(r["richiede_frigo"])
        })

    prev = db.execute(text("""
        SELECT donato_kg, distribuito_kg, modello
        FROM solidale.previsione
        WHERE punto_id = :punto AND settimana_riferimento = :sett
        LIMIT 1;
    """), {"punto": punto, "sett": sett}).mappings().first()

    return {
        "punto_id": punto,
        "settimana": sett.isoformat(),
        "righe": righe,
        "totali": {
            "kg_in_giacenza": round(kg_in_giacenza, 1),
            "kg_urgenza_alta": round(kg_urgenza_alta, 1),
            "kg_scaduti": round(kg_scaduti, 1)
        },
        "previsione_settimana_successiva": {
            "donato_kg": round(float(prev["donato_kg"]), 1),
            "distribuito_kg": round(float(prev["distribuito_kg"]), 1),
            "modello": prev["modello"]
        } if prev else None
    }

@api.get("/trasferimenti", tags=["Scadenze"])
def leggi_trasferimenti(
    punto: Optional[str] = Query(None, pattern=r"^PR\d{2}$"),
    settimana: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    if punto:
        verifica_punto(db, punto)
    sett = risolvi_settimana(db, settimana)

    query_str = """
        SELECT
            tr.id,
            tr.da_punto_id,
            tr.a_punto_id,
            tr.categoria_id,
            c.nome AS categoria,
            tr.kg,
            tr.scadenza_piu_vicina,
            tr.motivo,
            tr.messaggio_volontari,
            tr.volontari_suggeriti,
            tr.stato
        FROM solidale.trasferimento_suggerito tr
        JOIN solidale.categoria_prodotto c ON c.id = tr.categoria_id
        WHERE tr.settimana = :sett
    """
    params = {"sett": sett}
    if punto:
        query_str += " AND (tr.da_punto_id = :punto OR tr.a_punto_id = :punto)"
        params["punto"] = punto
    query_str += " ORDER BY tr.scadenza_piu_vicina ASC;"

    rows = db.execute(text(query_str), params).mappings().all()
    trasferimenti = []
    for r in rows:
        vol_list = r["volontari_suggeriti"] or []
        trasferimenti.append({
            "id": r["id"],
            "da_punto_id": r["da_punto_id"],
            "a_punto_id": r["a_punto_id"],
            "categoria_id": r["categoria_id"],
            "categoria": r["categoria"],
            "kg": round(float(r["kg"]), 1),
            "scadenza_piu_vicina": r["scadenza_piu_vicina"].isoformat() if r["scadenza_piu_vicina"] else None,
            "motivo": r["motivo"],
            "messaggio_volontari": r["messaggio_volontari"],
            "volontari_suggeriti": [{"volontario_id": vid, "nome": None} for vid in vol_list],
            "stato": r["stato"]
        })

    return {
        "settimana": sett.isoformat(),
        "trasferimenti": trasferimenti
    }

@api.get("/turni", tags=["Turni"])
def leggi_turni(
    punto: Optional[str] = Query(None, pattern=r"^PR\d{2}$"),
    settimana: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    if punto:
        verifica_punto(db, punto)
    sett = risolvi_settimana(db, settimana)
    fine_sett = date.fromordinal(sett.toordinal() + 6)

    query_turni = """
        SELECT
            t.id AS turno_id,
            t.punto_id,
            t.data,
            t.fascia,
            to_char(t.ora_inizio, 'HH24:MI') AS ora_inizio,
            to_char(t.ora_fine, 'HH24:MI') AS ora_fine,
            a.id AS assegnazione_id,
            a.volontario_id,
            a.stato,
            a.ore_pianificate,
            COALESCE(a.probabilita_scoperto, 0.0) AS probabilita_scoperto
        FROM solidale.turno t
        LEFT JOIN solidale.assegnazione a ON a.turno_id = t.id
        WHERE t.data BETWEEN :inizio AND :fine
    """
    params = {"inizio": sett, "fine": fine_sett}
    if punto:
        query_turni += " AND t.punto_id = :punto"
        params["punto"] = punto

    query_turni += " ORDER BY t.data ASC, t.ora_inizio ASC, a.id ASC;"
    rows = db.execute(text(query_turni), params).mappings().all()

    turni_map = {}
    tot_assegnazioni = 0
    cnt_alto = 0
    cnt_medio = 0

    for row in rows:
        tid = row["turno_id"]
        if tid not in turni_map:
            turni_map[tid] = {
                "turno_id": tid,
                "punto_id": row["punto_id"],
                "data": row["data"].isoformat(),
                "fascia": row["fascia"],
                "ora_inizio": row["ora_inizio"],
                "ora_fine": row["ora_fine"],
                "rischio_massimo": "basso",
                "assegnazioni": []
            }

        if row["assegnazione_id"]:
            tot_assegnazioni += 1
            prob = round(float(row["probabilita_scoperto"]), 2)
            if prob >= 0.30:
                rischio = "alto"
                cnt_alto += 1
                turni_map[tid]["rischio_massimo"] = "alto"
            elif prob >= 0.15:
                rischio = "medio"
                cnt_medio += 1
                if turni_map[tid]["rischio_massimo"] == "basso":
                    turni_map[tid]["rischio_massimo"] = "medio"
            else:
                rischio = "basso"

            turni_map[tid]["assegnazioni"].append({
                "assegnazione_id": row["assegnazione_id"],
                "volontario_id": row["volontario_id"],
                "nome": None,
                "stato": row["stato"],
                "ore_pianificate": round(float(row["ore_pianificate"]), 1),
                "probabilita_scoperto": prob,
                "rischio": rischio
            })

    lista_turni = list(turni_map.values())
    return {
        "settimana": sett.isoformat(),
        "riepilogo": {
            "turni": len(lista_turni),
            "assegnazioni": tot_assegnazioni,
            "rischio_alto": cnt_alto,
            "rischio_medio": cnt_medio
        },
        "turni": lista_turni
    }

@api.get("/assegnazioni/{assegnazione_id}/sostituti", tags=["Turni"])
def leggi_sostituti(
    assegnazione_id: str,
    db: Session = Depends(get_db)
):
    ass = db.execute(text("""
        SELECT
            a.id AS assegnazione_id,
            a.volontario_id,
            t.id AS turno_id,
            t.punto_id,
            t.data,
            t.fascia,
            to_char(t.ora_inizio, 'HH24:MI') AS ora_inizio,
            to_char(t.ora_fine, 'HH24:MI') AS ora_fine
        FROM solidale.assegnazione a
        JOIN solidale.turno t ON t.id = a.turno_id
        WHERE a.id = :aid;
    """), {"aid": assegnazione_id}).mappings().first()

    if not ass:
        raise ApiError(404, "non_trovato", f"L'assegnazione {assegnazione_id} non esiste.")

    sostituti_raw = db.execute(text("""
        SELECT posizione, volontario_id, punteggio, motivi
        FROM solidale.sostituto_suggerito
        WHERE assegnazione_id = :aid
        ORDER BY posizione ASC;
    """), {"aid": assegnazione_id}).mappings().all()

    return {
        "assegnazione_id": ass["assegnazione_id"],
        "volontario_id": ass["volontario_id"],
        "turno": {
            "turno_id": ass["turno_id"],
            "punto_id": ass["punto_id"],
            "data": ass["data"].isoformat(),
            "fascia": ass["fascia"],
            "ora_inizio": ass["ora_inizio"],
            "ora_fine": ass["ora_fine"]
        },
        "sostituti": [
            {
                "posizione": s["posizione"],
                "volontario_id": s["volontario_id"],
                "nome": None,
                "punteggio": round(float(s["punteggio"]), 2),
                "motivi": s["motivi"] or []
            }
            for s in sostituti_raw
        ]
    }

@api.post("/assegnazioni/{assegnazione_id}/sostituzione", tags=["Turni"])
def registra_sostituzione(
    assegnazione_id: str,
    body: NuovaSostituzione,
    db: Session = Depends(get_db)
):
    ass = db.execute(text("""
        SELECT
            a.id, a.turno_id, a.volontario_id, a.stato, a.sostituto_id,
            a.ore_pianificate, COALESCE(a.probabilita_scoperto, 0.0) AS probabilita_scoperto,
            t.data, t.fascia
        FROM solidale.assegnazione a
        JOIN solidale.turno t ON t.id = a.turno_id
        WHERE a.id = :aid;
    """), {"aid": assegnazione_id}).mappings().first()

    if not ass:
        raise ApiError(404, "non_trovato", f"L'assegnazione {assegnazione_id} non esiste.")

    if ass["stato"] == "sostituito" or ass["sostituto_id"] is not None:
        raise ApiError(
            409,
            "gia_sostituito",
            f"{assegnazione_id} è già stata sostituita da {ass['sostituto_id']}."
        )

    if body.sostituto_id == ass["volontario_id"]:
        raise ApiError(
            422,
            "sostituto_non_valido",
            "Il sostituto non può coincidere con il volontario già assegnato."
        )

    vol = db.execute(text("""
        SELECT attivo FROM solidale.volontario WHERE id = :vid;
    """), {"vid": body.sostituto_id}).mappings().first()

    if not vol or not vol["attivo"]:
        raise ApiError(
            422,
            "sostituto_non_valido",
            f"Il volontario {body.sostituto_id} non esiste o non è attivo."
        )

    impegnato = db.execute(text("""
        SELECT 1
        FROM solidale.assegnazione a2
        JOIN solidale.turno t2 ON t2.id = a2.turno_id
        WHERE t2.data = :data
          AND t2.fascia = :fascia
          AND (a2.volontario_id = :vid OR a2.sostituto_id = :vid);
    """), {"data": ass["data"], "fascia": ass["fascia"], "vid": body.sostituto_id}).scalar()

    if impegnato:
        raise ApiError(
            422,
            "sostituto_non_valido",
            f"{body.sostituto_id} è già assegnato a un turno nella stessa fascia."
        )

    db.execute(text("""
        UPDATE solidale.assegnazione
        SET stato = 'sostituito', sostituto_id = :vid
        WHERE id = :aid;
    """), {"vid": body.sostituto_id, "aid": assegnazione_id})
    db.commit()

    prob = round(float(ass["probabilita_scoperto"]), 2)
    rischio = "alto" if prob >= 0.30 else ("medio" if prob >= 0.15 else "basso")

    return {
        "assegnazione_id": ass["id"],
        "volontario_id": ass["volontario_id"],
        "nome": None,
        "stato": "sostituito",
        "sostituto_id": body.sostituto_id,
        "ore_pianificate": round(float(ass["ore_pianificate"]), 1),
        "probabilita_scoperto": prob,
        "rischio": rischio
    }

@api.get("/impatto", tags=["Impatto"])
def leggi_impatto(
    da: str = Query("2025-09", pattern=r"^\d{4}-\d{2}$"),
    a: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    punto: Optional[str] = Query(None, pattern=r"^PR\d{2}$"),
    db: Session = Depends(get_db)
):
    if punto:
        verifica_punto(db, punto)

    query_str = "SELECT * FROM solidale.v_impatto_mensile WHERE mese >= :da"
    params = {"da": da}
    if a:
        query_str += " AND mese <= :a"
        params["a"] = a
    if punto:
        query_str += " AND punto_id = :punto"
        params["punto"] = punto
    query_str += " ORDER BY mese ASC;"

    righe = db.execute(text(query_str), params).mappings().all()

    mensile = []
    tot_rec = tot_dist = tot_scart = tot_ore = 0.0
    tot_pasti = 0
    tassi_scop = []

    for r in righe:
        rec = round(float(r.get("kg_recuperati") or 0), 1)
        dist = round(float(r.get("kg_distribuiti_stimati") or 0), 1)
        scart = round(float(r.get("kg_scartati") or 0), 1)
        pasti = int(r.get("pasti_equivalenti") or 0)
        ore = round(float(r.get("ore_volontariato") or 0), 1)
        tasso_scop = round(float(r.get("tasso_scopertura_turni") or 0), 3)

        tot_rec += rec
        tot_dist += dist
        tot_scart += scart
        tot_pasti += pasti
        tot_ore += ore
        tassi_scop.append(tasso_scop)

        mensile.append({
            "mese": r["mese"],
            "kg_recuperati": rec,
            "kg_distribuiti_stimati": dist,
            "kg_scartati": scart,
            "pasti_equivalenti": pasti,
            "ore_volontariato": ore,
            "tasso_scopertura_turni": tasso_scop
        })

    ben_query = """
        SELECT
            COUNT(*) AS nuclei_attivi,
            COALESCE(SUM(componenti), 0) AS persone_raggiunte,
            COALESCE(SUM(minori), 0) AS minori_raggiunti
        FROM solidale.beneficiario
        WHERE attivo = true
    """
    ben_params = {}
    if punto:
        ben_query += " AND punto_id = :punto"
        ben_params["punto"] = punto

    ben_row = db.execute(text(ben_query), ben_params).mappings().first()

    ultimo_mese = mensile[-1]["mese"] if mensile else (a or da)
    tasso_spreco = round(tot_scart / tot_rec, 3) if tot_rec > 0 else 0.0
    tasso_scop_medio = round(sum(tassi_scop) / len(tassi_scop), 3) if tassi_scop else 0.0

    return {
        "periodo": {"da": da, "a": ultimo_mese},
        "punto_id": punto,
        "totali": {
            "kg_recuperati": round(tot_rec, 1),
            "kg_distribuiti_stimati": round(tot_dist, 1),
            "kg_scartati": round(tot_scart, 1),
            "tasso_spreco": tasso_spreco,
            "pasti_equivalenti": tot_pasti,
            "ore_volontariato": round(tot_ore, 1),
            "tasso_scopertura_turni": tasso_scop_medio,
            "nuclei_attivi": int(ben_row["nuclei_attivi"]) if ben_row else 0,
            "persone_raggiunte": int(ben_row["persone_raggiunte"]) if ben_row else 0,
            "minori_raggiunti": int(ben_row["minori_raggiunti"]) if ben_row else 0
        },
        "mensile": mensile,
        "ipotesi": {
            "kg_per_pasto": 0.5,
            "note": [
                "Le distribuzioni sono stimate con il bilancio di magazzino (giacenza iniziale + donato − scartato − giacenza finale).",
                "Gli scarti sono una stima minima: alcuni punti li registrano meno degli altri.",
                "I pezzi sono convertiti in kg con un peso medio per categoria."
            ]
        }
    }

@api.get("/messaggi", tags=["Messaggi"])
def leggi_messaggi(
    categoria: Optional[str] = Query(None),
    fonte: Optional[str] = Query(None),
    punto: Optional[str] = Query(None, pattern=r"^PR\d{2}$"),
    da: Optional[date] = Query(None),
    a: Optional[date] = Query(None),
    pagina: int = Query(1, ge=1),
    per_pagina: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    if punto:
        verifica_punto(db, punto)

    where_base = ["fonte != 'nota_operatore'"]
    params = {}

    if punto:
        where_base.append("punto_id = :punto")
        params["punto"] = punto
    if da:
        where_base.append("ricevuto_il::date >= :da")
        params["da"] = da
    if a:
        where_base.append("ricevuto_il::date <= :a")
        params["a"] = a

    base_sql = " AND ".join(where_base)

    conteggi = db.execute(text(f"""
        SELECT categoria_predetta AS categoria, COUNT(*) AS n
        FROM solidale.messaggio
        WHERE {base_sql} AND categoria_predetta IS NOT NULL
        GROUP BY categoria_predetta
        ORDER BY n DESC;
    """), params).mappings().all()

    sodd_where = ["fonte IN ('recensione', 'feedback_app')"]
    if punto:
        sodd_where.append("punto_id = :punto")
    if da:
        sodd_where.append("ricevuto_il::date >= :da")
    if a:
        sodd_where.append("ricevuto_il::date <= :a")
    sodd_sql = " AND ".join(sodd_where)

    sodd_tot = db.execute(text(f"""
        SELECT
            ROUND(AVG(voto)::numeric, 1) AS voto_medio,
            COUNT(voto) AS n_voti,
            COUNT(*) FILTER (WHERE sentiment = 'negativo') AS neg,
            COUNT(*) FILTER (WHERE sentiment = 'neutro') AS neu,
            COUNT(*) FILTER (WHERE sentiment = 'positivo') AS pos
        FROM solidale.messaggio
        WHERE {sodd_sql};
    """), params).mappings().first()

    sodd_mensile = db.execute(text(f"""
        SELECT
            to_char(ricevuto_il, 'YYYY-MM') AS mese,
            ROUND(AVG(voto)::numeric, 1) AS voto_medio,
            COUNT(voto) AS n_voti
        FROM solidale.messaggio
        WHERE {sodd_sql} AND voto IS NOT NULL
        GROUP BY to_char(ricevuto_il, 'YYYY-MM')
        ORDER BY mese ASC;
    """), params).mappings().all()

    where_lista = list(where_base)
    if categoria:
        where_lista.append("categoria_predetta = :categoria")
        params["categoria"] = categoria
    if fonte:
        where_lista.append("fonte = :fonte")
        params["fonte"] = fonte

    lista_sql = " AND ".join(where_lista)
    totale = db.execute(text(f"SELECT COUNT(*) FROM solidale.messaggio WHERE {lista_sql};"), params).scalar() or 0

    params["limit"] = per_pagina
    params["offset"] = (pagina - 1) * per_pagina

    rows = db.execute(text(f"""
        SELECT
            id, fonte, ricevuto_il, autore_ruolo, punto_id, voto,
            oggetto, testo_anonimizzato, categoria_predetta, confidenza,
            sentiment, sentiment_punteggio, entita_estratte
        FROM solidale.messaggio
        WHERE {lista_sql}
        ORDER BY ricevuto_il DESC
        LIMIT :limit OFFSET :offset;
    """), params).mappings().all()

    messaggi = []
    for r in rows:
        item = dict(r)
        if item["ricevuto_il"]:
            item["ricevuto_il"] = item["ricevuto_il"].isoformat()
        messaggi.append(item)

    return {
        "totale": totale,
        "pagina": pagina,
        "per_pagina": per_pagina,
        "conteggi_per_categoria": [dict(c) for c in conteggi],
        "soddisfazione": {
            "voto_medio": float(sodd_tot["voto_medio"]) if sodd_tot and sodd_tot["voto_medio"] is not None else None,
            "n_voti": int(sodd_tot["n_voti"]) if sodd_tot else 0,
            "sentiment": {
                "negativo": int(sodd_tot["neg"]) if sodd_tot else 0,
                "neutro": int(sodd_tot["neu"]) if sodd_tot else 0,
                "positivo": int(sodd_tot["pos"]) if sodd_tot else 0
            },
            "mensile": [
                {
                    "mese": m["mese"],
                    "voto_medio": float(m["voto_medio"]),
                    "n_voti": int(m["n_voti"])
                }
                for m in sodd_mensile
            ]
        },
        "messaggi": messaggi
    }

@api.post("/feedback", status_code=201, tags=["Messaggi"])
def invia_feedback(
    body: NuovoFeedback,
    db: Session = Depends(get_db)
):
    if body.punto_id:
        esiste = db.execute(
            text("SELECT 1 FROM solidale.punto_ritiro WHERE id = :p;"),
            {"p": body.punto_id}
        ).scalar()
        if not esiste:
            raise ApiError(422, "dati_non_validi", f"Il punto {body.punto_id} non esiste.")

    testo_pulito = anonimizza_testo(body.commento)
    ora_ricezione = datetime.now(timezone.utc).astimezone()

    new_id = db.execute(text("""
        INSERT INTO solidale.messaggio (
            fonte, ricevuto_il, autore_ruolo, punto_id, voto, testo_anonimizzato
        )
        VALUES (
            'feedback_app', :ricevuto_il, :ruolo, :punto, :voto, :testo
        )
        RETURNING id;
    """), {
        "ricevuto_il": ora_ricezione,
        "ruolo": body.ruolo_autore,
        "punto": body.punto_id,
        "voto": body.voto,
        "testo": testo_pulito
    }).scalar()
    db.commit()

    return {
        "id": new_id,
        "ricevuto_il": ora_ricezione.isoformat()
    }

@api.post("/donazioni", status_code=201, tags=["Donazioni"])
def crea_donazione(
    body: NuovaDonazione,
    db: Session = Depends(get_db)
):
    punto_ok = db.execute(
        text("SELECT 1 FROM solidale.punto_ritiro WHERE id = :p;"),
        {"p": body.punto_id}
    ).scalar()
    if not punto_ok:
        raise ApiError(422, "dati_non_validi", f"Il punto {body.punto_id} non esiste.")

    don_ok = db.execute(
        text("SELECT 1 FROM solidale.donatore WHERE id = :d;"),
        {"d": body.donatore_id}
    ).scalar()
    if not don_ok:
        raise ApiError(422, "dati_non_validi", f"Il donatore {body.donatore_id} non esiste.")

    categorie_db = {
        row["id"]: row
        for row in db.execute(text("""
            SELECT id, nome, peso_medio_kg FROM solidale.categoria_prodotto;
        """)).mappings().all()
    }

    righe_calcolate = []
    kg_totali = 0.0

    for r in body.righe:
        cat = categorie_db.get(r.categoria_id)
        if not cat:
            raise ApiError(422, "dati_non_validi", f"La categoria {r.categoria_id} non esiste.")

        if r.unita == "kg":
            kg_riga = round(float(r.quantita), 1)
            kg_stimato = False
        else:
            peso_medio = float(cat["peso_medio_kg"] or 0.5)
            kg_riga = round(float(r.quantita) * peso_medio, 1)
            kg_stimato = True

        kg_totali += kg_riga
        righe_calcolate.append({
            "categoria_id": r.categoria_id,
            "categoria": cat["nome"],
            "prodotto": r.prodotto,
            "quantita": r.quantita,
            "unita": r.unita,
            "kg": kg_riga,
            "kg_stimato": kg_stimato
        })

    ultimo_num = db.execute(text("""
        SELECT COALESCE(MAX(CAST(SUBSTRING(id FROM 5) AS INTEGER)), 10000)
        FROM solidale.donazione
        WHERE id ~ '^DON-\\d+$';
    """)).scalar()
    donazione_id = f"DON-{ultimo_num + 1}"

    db.execute(text("""
        INSERT INTO solidale.donazione (
            id, data, donatore_id, punto_id, canale, stato_corrente, nota
        )
        VALUES (
            :id, :data, :donatore, :punto, 'app', 'offerta', :nota
        );
    """), {
        "id": donazione_id,
        "data": body.data,
        "donatore": body.donatore_id,
        "punto": body.punto_id,
        "nota": body.nota
    })

    for rc in righe_calcolate:
        db.execute(text("""
            INSERT INTO solidale.riga_donazione (
                donazione_id, categoria_id, prodotto, quantita, unita, kg, kg_stimato
            )
            VALUES (
                :did, :cid, :prod, :qta, :unita, :kg, :stim
            );
        """), {
            "did": donazione_id,
            "cid": rc["categoria_id"],
            "prod": rc["prodotto"],
            "qta": rc["quantita"],
            "unita": rc["unita"],
            "kg": rc["kg"],
            "stim": rc["kg_stimato"]
        })

    db.execute(text("""
        INSERT INTO solidale.storico_stato_donazione (donazione_id, stato, cambiato_il)
        VALUES (:did, 'offerta', NOW());
    """), {"did": donazione_id})

    db.commit()

    return {
        "id": donazione_id,
        "data": body.data.isoformat(),
        "donatore_id": body.donatore_id,
        "punto_id": body.punto_id,
        "canale": "app",
        "stato_corrente": "offerta",
        "kg_totali": round(kg_totali, 1),
        "righe": righe_calcolate
    }

@api.post("/caricamenti", status_code=202, tags=["Caricamenti"])
async def carica_file(
    tipo: Literal["giacenze", "scarti"] = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise ApiError(422, "file_non_valido", "Il file deve essere un Excel .xlsx.")

    contenuto = await file.read()
    if len(contenuto) > 5 * 1024 * 1024:
        raise ApiError(422, "file_non_valido", "Il file supera la dimensione massima di 5 MB.")

    os.makedirs("staging", exist_ok=True)
    ora_caricamento = datetime.now(timezone.utc).astimezone()
    nome_sicuro = os.path.basename(file.filename)
    percorso_file = os.path.join("staging", f"{int(ora_caricamento.timestamp())}_{nome_sicuro}")

    with open(percorso_file, "wb") as f:
        f.write(contenuto)

    new_id = db.execute(text("""
        INSERT INTO solidale.caricamento (
            tipo, nome_file, percorso_staging, caricato_il, stato
        )
        VALUES (
            :tipo, :nome, :percorso, :caricato_il, 'in_attesa'
        )
        RETURNING id;
    """), {
        "tipo": tipo,
        "nome": nome_sicuro,
        "percorso": percorso_file,
        "caricato_il": ora_caricamento
    }).scalar()
    db.commit()

    return {
        "id": new_id,
        "tipo": tipo,
        "nome_file": nome_sicuro,
        "caricato_il": ora_caricamento.isoformat(),
        "stato": "in_attesa",
        "elaborato_il": None,
        "righe_lette": None,
        "righe_caricate": None,
        "righe_scartate": None,
        "errori": []
    }

@api.get("/caricamenti", tags=["Caricamenti"])
def leggi_caricamenti(
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    ultimo_agg = db.execute(text("""
        SELECT MAX(elaborato_il)
        FROM solidale.caricamento
        WHERE stato IN ('completato', 'completato_con_scarti');
    """)).scalar()

    rows = db.execute(text("""
        SELECT
            id, tipo, nome_file, caricato_il, stato, elaborato_il,
            righe_lette, righe_caricate, righe_scartate, errori
        FROM solidale.caricamento
        ORDER BY caricato_il DESC
        LIMIT :limite;
    """), {"limite": limite}).mappings().all()

    lista = []
    for r in rows:
        lista.append({
            "id": r["id"],
            "tipo": r["tipo"],
            "nome_file": r["nome_file"],
            "caricato_il": r["caricato_il"].isoformat() if r["caricato_il"] else None,
            "stato": r["stato"],
            "elaborato_il": r["elaborato_il"].isoformat() if r["elaborato_il"] else None,
            "righe_lette": r["righe_lette"],
            "righe_caricate": r["righe_caricate"],
            "righe_scartate": r["righe_scartate"],
            "errori": r["errori"] or []
        })

    return {
        "ultimo_aggiornamento": ultimo_agg.isoformat() if ultimo_agg else None,
        "caricamenti": lista
    }

app.include_router(api)