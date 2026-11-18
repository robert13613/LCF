import re
import pandas as pd

# 1. DIZIONARIO DI MAPPATURA: 51 nomi grezzi -> 14 categorie canoniche
MAPPA_CATEGORIE = {
    # 1. Verdura fresca (in kg)
    "Verdura fresca": "Verdura fresca",
    "Verdura": "Verdura fresca",
    "verdure": "Verdura fresca",
    "Ortaggi": "Verdura fresca",
    # 2. Carne e affettati confezionati (in kg)
    "Carne e affettati confezionati": "Carne e affettati confezionati",
    "Carne confezionata": "Carne e affettati confezionati",
    "Salumi": "Carne e affettati confezionati",
    "affettati": "Carne e affettati confezionati",
    # 3. Latticini freschi (in kg)
    "Latticini freschi": "Latticini freschi",
    "latticini": "Latticini freschi",
    "Formaggi/yogurt": "Latticini freschi",
    "Yogurt": "Latticini freschi",
    # 4. Pane e prodotti da forno (in kg)
    "Pane e prodotti da forno": "Pane e prodotti da forno",
    "Pane": "Pane e prodotti da forno",
    "pane": "Pane e prodotti da forno",
    "Prodotti da forno": "Pane e prodotti da forno",
    # 5. Frutta fresca (in kg)
    "Frutta fresca": "Frutta fresca",
    "Frutta": "Frutta fresca",
    "frutta": "Frutta fresca",
    # 6. Latte UHT (in pz)
    "Latte UHT": "Latte UHT",
    "latte uht": "Latte UHT",
    "Latte": "Latte UHT",
    # 7. Pomodori pelati e passata (in pz)
    "Pomodori pelati e passata": "Pomodori pelati e passata",
    "Passata di pomodoro": "Pomodori pelati e passata",
    "Pelati": "Pomodori pelati e passata",
    "pomodoro": "Pomodori pelati e passata",
    # 8. Legumi in scatola (in pz)
    "Legumi in scatola": "Legumi in scatola",
    "legumi scatola": "Legumi in scatola",
    "Legumi": "Legumi in scatola",
    "Fagioli/ceci": "Legumi in scatola",
    # 9. Pasta secca (in kg)
    "Pasta secca": "Pasta secca",
    "Pasta secca (kg)": "Pasta secca",
    "Pasta": "Pasta secca",
    "pasta": "Pasta secca",
    # 10. Riso (in kg)
    "Riso": "Riso",
    "Riso confezionato": "Riso",
    "riso": "Riso",
    # 11. Igiene personale (in pz)
    "Igiene personale": "Igiene personale",
    "igiene persona": "Igiene personale",
    "Igiene": "Igiene personale",
    "Saponi/shampoo": "Igiene personale",
    # 12. Olio di semi (in pz)
    "Olio di semi": "Olio di semi",
    "Olio": "Olio di semi",
    "olio": "Olio di semi",
    # 13. Biscotti e merendine (in kg)
    "Biscotti e merendine": "Biscotti e merendine",
    "Biscotti/merende": "Biscotti e merendine",
    "Biscotti": "Biscotti e merendine",
    "merendine": "Biscotti e merendine",
    # 14. Detersivi e prodotti casa (in pz)
    "Detersivi e prodotti casa": "Detersivi e prodotti casa",
    "Detersivi": "Detersivi e prodotti casa",
    "Prodotti pulizia": "Detersivi e prodotti casa",
}

# 2. IPOTESI SUI PESI AL PEZZO (per le 6 categorie donate in pz/pezzi/n)
PESO_PER_PEZZO_KG = {
    "Latte UHT": 1.00,                  # 1 brick da 1 litro ≈ 1,0 kg
    "Pomodori pelati e passata": 0.50,  # lattina pelati 400g / bottiglia passata 700g -> media 0,5 kg
    "Legumi in scatola": 0.40,          # lattina standard da 400 g (peso totale) ≈ 0,4 kg
    "Olio di semi": 0.92,               # bottiglia da 1 litro di olio di semi ≈ 0,92 kg
    "Igiene personale": 0.30,           # flacone bagnoschiuma/shampoo/sapone ≈ 0,3 kg
    "Detersivi e prodotti casa": 1.00,  # flacone detersivo piatti/bucato ≈ 1,0 kg
}


def salva_mappa_csv(percorso_csv="mappa_categorie.csv"):
    righe = []
    for nome_grezzo, categoria in MAPPA_CATEGORIE.items():
        peso_pz = PESO_PER_PEZZO_KG.get(categoria, None)
        righe.append({
            "nome_grezzo": nome_grezzo,
            "categoria": categoria,
            "peso_stimato_kg_per_pz": peso_pz
        })
    df_mappa = pd.DataFrame(righe)
    df_mappa.to_csv(percorso_csv, index=False, encoding="utf-8")
    print(f"[OK] Salvato '{percorso_csv}' con {len(df_mappa)} prodotti mappati su {df_mappa['categoria'].nunique()} categorie.")


def separa_quantita(valore_str):
    s = str(valore_str).strip().lower().replace(",", ".")
    match_num = re.search(r"(\d+(?:\.\d+)?)", s)
    match_unit = re.search(r"(kg|pz|pezzi|n\.?)", s)
    if not match_num or not match_unit:
        raise ValueError(f"Quantità illeggibile: {valore_str}")
    numero = float(match_num.group(1))
    unita_raw = match_unit.group(1)
    unita = "kg" if unita_raw == "kg" else "pz"
    return pd.Series([numero, unita])


def pulisci_donazioni(percorso_excel="donazioni_set2025_ott2026.xlsx", percorso_output="donazioni_pulite.csv"):
    df = pd.read_excel(percorso_excel, sheet_name="Donazioni")
    righe_iniziali = len(df)

    # Rimozione duplicati esatti
    df = df.drop_duplicates().copy()
    print(f"[OK] Duplicati rimossi: {righe_iniziali - len(df)} (righe rimaste: {len(df)})")

    # Conversione date con dayfirst=True
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, format="mixed")
    assert df["data"].isna().sum() == 0, "Trovate date non convertibili!"

    # Regex per separare numero e unità (kg / pz)
    df[["quantita_valore", "unita"]] = df["quantita"].apply(separa_quantita)

    # Mappatura sulle 14 categorie
    df["categoria"] = df["prodotto"].map(MAPPA_CATEGORIE)
    assert df["categoria"].isna().sum() == 0, "Trovati prodotti non mappati!"

    # Calcolo peso stimato totale in kg (utile per KPI e capienze)
    def calcola_kg(row):
        if row["unita"] == "kg":
            return row["quantita_valore"]
        return round(row["quantita_valore"] * PESO_PER_PEZZO_KG[row["categoria"]], 2)

    df["quantita_kg_stimata"] = df.apply(calcola_kg, axis=1)

    # Pulizia spazi codice_donatore
    df["codice_donatore"] = df["codice_donatore"].fillna("ANONIMO").str.strip()

    df.to_csv(percorso_output, index=False, encoding="utf-8")
    print(f"[OK] Salvato '{percorso_output}'! Date illeggibili: 0 | Quantità illeggibili: 0")


if __name__ == "__main__":
    salva_mappa_csv("mappa_categorie.csv")
    pulisci_donazioni("donazioni_set2025_ott2026.xlsx", "donazioni_pulite.csv")