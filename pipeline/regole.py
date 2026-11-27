import pandas as pd


def data(valore, allow_null=False):
    """Converte la data usando formati espliciti (restituisce stringa YYYY-MM-DD)."""
    if pd.isna(valore):
        if allow_null:
            return None
        raise ValueError("Data mancante (NaN)")
    if isinstance(valore, pd.Timestamp):
        return valore.strftime("%Y-%m-%d")

    s = str(valore).strip()
    if " " in s:
        s = s.split(" ")[0]

    formati_espliciti = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%y", "%d-%m-%Y", "%d/%m/%y")
    for fmt in formati_espliciti:
        try:
            return pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Formato data non riconosciuto: {valore}")


CATEGORIE_CANONICHE = [
    (1,  "Verdura fresca",                 "kg", None),
    (2,  "Carne e affettati confezionati", "kg", None),
    (3,  "Latticini freschi",              "kg", None),
    (4,  "Pane e prodotti da forno",       "kg", None),
    (5,  "Frutta fresca",                  "kg", None),
    (6,  "Latte UHT",                      "pz", 1.00),
    (7,  "Pomodori pelati e passata",      "pz", 0.50),
    (8,  "Legumi in scatola",              "pz", 0.40),
    (9,  "Pasta secca",                    "kg", None),
    (10, "Riso",                           "kg", None),
    (11, "Igiene personale",               "pz", 0.30),
    (12, "Olio di semi",                   "pz", 0.92),
    (13, "Biscotti e merendine",           "kg", None),
    (14, "Detersivi e prodotti casa",      "pz", 1.00),
]

CAT_TO_ID = {nome: cid for cid, nome, _, _ in CATEGORIE_CANONICHE}
CAT_TO_PESO_PZ = {nome: peso for _, nome, _, peso in CATEGORIE_CANONICHE}

MAPPA_CATEGORIE = {
    "Verdura fresca": "Verdura fresca",
    "Verdura": "Verdura fresca",
    "verdure": "Verdura fresca",
    "Ortaggi": "Verdura fresca",
    "Carne e affettati confezionati": "Carne e affettati confezionati",
    "Carne confezionata": "Carne e affettati confezionati",
    "Salumi": "Carne e affettati confezionati",
    "affettati": "Carne e affettati confezionati",
    "Latticini freschi": "Latticini freschi",
    "latticini": "Latticini freschi",
    "Formaggi/yogurt": "Latticini freschi",
    "Yogurt": "Latticini freschi",
    "Pane e prodotti da forno": "Pane e prodotti da forno",
    "Pane": "Pane e prodotti da forno",
    "pane": "Pane e prodotti da forno",
    "Prodotti da forno": "Pane e prodotti da forno",
    "Frutta fresca": "Frutta fresca",
    "Frutta": "Frutta fresca",
    "frutta": "Frutta fresca",
    "Latte UHT": "Latte UHT",
    "latte uht": "Latte UHT",
    "Latte": "Latte UHT",
    "Pomodori pelati e passata": "Pomodori pelati e passata",
    "Passata di pomodoro": "Pomodori pelati e passata",
    "Pelati": "Pomodori pelati e passata",
    "pomodoro": "Pomodori pelati e passata",
    "Legumi in scatola": "Legumi in scatola",
    "legumi scatola": "Legumi in scatola",
    "Legumi": "Legumi in scatola",
    "Fagioli/ceci": "Legumi in scatola",
    "Pasta secca": "Pasta secca",
    "Pasta secca (kg)": "Pasta secca",
    "Pasta": "Pasta secca",
    "pasta": "Pasta secca",
    "Riso": "Riso",
    "Riso confezionato": "Riso",
    "riso": "Riso",
    "Igiene personale": "Igiene personale",
    "igiene persona": "Igiene personale",
    "Igiene": "Igiene personale",
    "Saponi/shampoo": "Igiene personale",
    "Olio di semi": "Olio di semi",
    "Olio": "Olio di semi",
    "olio": "Olio di semi",
    "Biscotti e merendine": "Biscotti e merendine",
    "Biscotti/merende": "Biscotti e merendine",
    "Biscotti": "Biscotti e merendine",
    "merendine": "Biscotti e merendine",
    "Detersivi e prodotti casa": "Detersivi e prodotti casa",
    "Detersivi": "Detersivi e prodotti casa",
    "Prodotti pulizia": "Detersivi e prodotti casa",
}

MAPPA_PUNTI = {
    "PR01": "PR01",
    "Barriera": "PR01",
    "Punto Barriera": "PR01",
    "Torino Barriera": "PR01",
    "PR02": "PR02",
    "Mirafiori": "PR02",
    "Punto Mirafiori": "PR02",
    "Torino Mirafiori": "PR02",
    "PR03": "PR03",
    "Moncalieri": "PR03",
    "Punto Moncalieri": "PR03",
    "PR04": "PR04",
    "Collegno": "PR04",
    "Punto Collegno": "PR04",
    "PR05": "PR05",
    "Chieri": "PR05",
    "Punto Chieri": "PR05",
    "PR06": "PR06",
    "Nichelino": "PR06",
    "Punto Nichelino": "PR06",
    "PR07": "PR07",
    "Venaria": "PR07",
    "Punto Venaria": "PR07",
    "Venaria Reale": "PR07",
}

MAPPA_CAUSALI_SCARTO = {
    "scaduto": "scaduto",
    "Scaduto": "scaduto",
    "scad.": "scaduto",
    "danneggiato": "danneggiato",
    "Danneggiato": "danneggiato",
    "rotto": "danneggiato",
    "non idoneo": "non_idoneo",
    "Non idoneo": "non_idoneo",
    "da scartare": "non_idoneo",
}

MAPPA_STATI_TURNO = {
    "coperto": "coperto",
    "Coperto": "coperto",
    "COPERTO": "coperto",
    "scoperto": "scoperto",
    "Scoperto": "scoperto",
    "parziale": "parziale",
    "Parziale": "parziale",
    "sostituito": "sostituito",
    "Sostituito": "sostituito",
}