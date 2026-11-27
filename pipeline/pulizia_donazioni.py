import re
import pandas as pd

try:
    from regole import data, MAPPA_CATEGORIE, CAT_TO_ID, CAT_TO_PESO_PZ
except ImportError:
    from pipeline.regole import data, MAPPA_CATEGORIE, CAT_TO_ID, CAT_TO_PESO_PZ


def salva_mappa_csv(percorso_csv="mappa_categorie.csv"):
    righe = [
        {
            "nome_grezzo": nome_grezzo,
            "categoria_id": CAT_TO_ID[categoria],
            "categoria": categoria,
            "peso_medio_pz_kg": CAT_TO_PESO_PZ[categoria],
        }
        for nome_grezzo, categoria in MAPPA_CATEGORIE.items()
    ]
    df_mappa = pd.DataFrame(righe)
    df_mappa.to_csv(percorso_csv, index=False, encoding="utf-8")
    return df_mappa


def separa_quantita(valore_str):
    s = str(valore_str).strip().lower().replace(",", ".")
    match_num = re.search(r"(\d+(?:\.\d+)?)", s)
    match_unit = re.search(r"(kg|pz|pezzi|n\.?)", s)
    if not match_num or not match_unit:
        raise ValueError(f"Quantità illeggibile: {valore_str}")
    numero = round(float(match_num.group(1)), 2)
    unita = "kg" if match_unit.group(1) == "kg" else "pz"
    return pd.Series([numero, unita])


def elabora_donazioni(percorso_excel="donazioni_set2025_ott2026.xlsx"):
    df = pd.read_excel(percorso_excel, sheet_name="Donazioni")
    righe_grezze = len(df)

    df["id_donazione"] = df["id_donazione"].astype(str).str.strip()
    df["data"] = df["data"].apply(data)
    df["punto_id"] = df["punto_ritiro"].astype(str).str.strip()
    df["prodotto_originale"] = df["prodotto"].astype(str).str.strip()

    df["donatore_id"] = df["codice_donatore"].apply(
        lambda x: None if pd.isna(x) or str(x).strip() == "" else str(x).strip()
    )

    df[["quantita", "unita"]] = df["quantita"].apply(separa_quantita)
    df["categoria"] = df["prodotto_originale"].map(MAPPA_CATEGORIE)
    df["categoria_id"] = df["categoria"].map(CAT_TO_ID)
    df["kg_stimato"] = df["unita"] == "pz"
    df["kg"] = df.apply(
        lambda r: r["quantita"] if r["unita"] == "kg" else round(r["quantita"] * CAT_TO_PESO_PZ[r["categoria"]], 2),
        axis=1,
    )

    df = df.drop_duplicates(
        subset=["id_donazione", "data", "punto_id", "prodotto_originale", "quantita", "unita"]
    ).copy()

    mappa_donatori = df.dropna(subset=["donatore_id"]).groupby("id_donazione")["donatore_id"].first()
    df["donatore_id_testata"] = df["id_donazione"].map(mappa_donatori)

    df_donazione = (
        df.groupby("id_donazione", as_index=False)
        .agg(
            data=("data", "first"),
            donatore_id=("donatore_id_testata", "first"),
            punto_id=("punto_id", "first"),
        )
        .rename(columns={"id_donazione": "id"})
    )
    df_donazione["canale"] = "storico"
    df_donazione["messaggio_id"] = None
    df_donazione["stato_corrente"] = "ricevuta"
    df_donazione = df_donazione[["id", "data", "donatore_id", "punto_id", "canale", "messaggio_id", "stato_corrente"]]

    df_riga = df[["id_donazione", "categoria_id", "prodotto_originale", "quantita", "unita", "kg", "kg_stimato"]].copy()
    df_riga = df_riga.rename(columns={"id_donazione": "donazione_id"})

    df_donazione.to_csv("donazione.csv", index=False, encoding="utf-8")
    df_riga.to_csv("donazione_riga.csv", index=False, encoding="utf-8")

    assert len(MAPPA_CATEGORIE) == 51
    assert df_riga["categoria_id"].nunique() == 14
    assert df_riga["categoria_id"].isna().sum() == 0
    assert df_donazione["data"].isna().sum() == 0
    assert (df_riga["quantita"] > 0).all()
    assert (df_riga["kg"] > 0).all()
    assert df_riga["unita"].isin(["kg", "pz"]).all()
    assert (df_donazione["donatore_id"] == "ANONIMO").sum() == 0
    assert df_donazione["id"].nunique() == len(df_donazione)
    assert set(df_riga["donazione_id"]).issubset(set(df_donazione["id"]))

    print(f"[OK] Righe lette: {righe_grezze} | Duplicati rimossi: {righe_grezze - len(df_riga)}")
    print(f"[OK] donazione.csv: {len(df_donazione)} righe ({df_donazione['donatore_id'].isna().sum()} senza donatore)")
    print(f"[OK] donazione_riga.csv: {len(df_riga)} righe ({df_riga['kg'].sum():.2f} kg totali)")


if __name__ == "__main__":
    salva_mappa_csv("mappa_categorie.csv")
    elabora_donazioni("donazioni_set2025_ott2026.xlsx")