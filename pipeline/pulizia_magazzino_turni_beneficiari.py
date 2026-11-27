import re
import pandas as pd

try:
    from regole import (
        data,
        MAPPA_CATEGORIE,
        CAT_TO_ID,
        CAT_TO_PESO_PZ,
        MAPPA_PUNTI,
        MAPPA_CAUSALI_SCARTO,
        MAPPA_STATI_TURNO,
    )
except ImportError:
    from pipeline.regole import (
        data,
        MAPPA_CATEGORIE,
        CAT_TO_ID,
        CAT_TO_PESO_PZ,
        MAPPA_PUNTI,
        MAPPA_CAUSALI_SCARTO,
        MAPPA_STATI_TURNO,
    )


def separa_quantita(valore_str):
    s = str(valore_str).strip().lower().replace(",", ".")
    match_num = re.search(r"(\d+(?:\.\d+)?)", s)
    match_unit = re.search(r"(kg|pz|pezzi|n\.?)", s)
    if not match_num or not match_unit:
        raise ValueError(f"Quantità illeggibile: {valore_str}")
    numero = round(float(match_num.group(1)), 2)
    unita = "kg" if match_unit.group(1) == "kg" else "pz"
    return pd.Series([numero, unita])


def elabora_punti_e_beneficiari(percorso_excel="anagrafiche_buby_solidale.xlsx"):
    # 1. Punti di ritiro
    df_punti = pd.read_excel(percorso_excel, sheet_name="Punti di ritiro")
    df_punti["id_punto"] = df_punti["id_punto"].astype(str).str.strip()
    df_punti["nome"] = df_punti["nome"].astype(str).str.strip()
    df_punti["comune"] = df_punti["comune"].astype(str).str.strip()
    df_punti["indirizzo"] = df_punti["indirizzo"].astype(str).str.strip()
    df_punti["giorni_apertura"] = df_punti["giorni_apertura"].astype(str).str.strip()
    df_punti["orario"] = df_punti["orario"].astype(str).str.strip()
    df_punti["frigorifero"] = (
        df_punti["frigorifero"].astype(str).str.strip().str.lower().map({"si": True, "sì": True, "no": False})
    )
    df_punti = df_punti.rename(columns={"id_punto": "id"})
    df_punti.to_csv("punto_ritiro.csv", index=False, encoding="utf-8")

    # 2. Beneficiari anonimi
    df_ben = pd.read_excel(percorso_excel, sheet_name="Beneficiari anonimi")
    righe_ben_grezze = len(df_ben)

    df_ben["id_beneficiario"] = df_ben["id_beneficiario"].astype(str).str.strip()
    df_ben = df_ben.drop_duplicates(subset=["id_beneficiario"]).copy()

    df_ben["n_componenti"] = df_ben["n_componenti"].astype(int)
    df_ben["n_minori"] = df_ben["n_minori"].fillna(0).astype(int)
    df_ben["n_over65"] = df_ben["n_over65"].fillna(0).astype(int)

    # Correzione riga che viola minori + over65 <= componenti (B0078)
    mask_viol = (df_ben["n_minori"] + df_ben["n_over65"]) > df_ben["n_componenti"]
    df_ben.loc[mask_viol, "n_minori"] = df_ben.loc[mask_viol, "n_componenti"] - df_ben.loc[mask_viol, "n_over65"]

    df_ben["punto_id"] = df_ben["punto_ritiro_riferimento"].astype(str).str.strip().map(MAPPA_PUNTI)
    df_ben["data_prima_registrazione"] = df_ben["data_prima_registrazione"].apply(data)
    df_ben["stato_scheda"] = df_ben["stato_scheda"].astype(str).str.strip().str.lower()
    df_ben["accessi_ultimi_12_mesi"] = df_ben["accessi_ultimi_12_mesi"].astype(int)

    df_ben = df_ben.rename(columns={"id_beneficiario": "id"})[
        [
            "id",
            "fascia_eta_referente",
            "n_componenti",
            "n_minori",
            "n_over65",
            "comune_residenza",
            "punto_id",
            "data_prima_registrazione",
            "accessi_ultimi_12_mesi",
            "stato_scheda",
        ]
    ]
    df_ben.to_csv("beneficiario.csv", index=False, encoding="utf-8")

    return df_punti, df_ben, righe_ben_grezze


def elabora_giacenze_e_scarti(percorso_excel="magazzino_giacenze_scarti.xlsx"):
    # 3. Giacenze
    df_giac = pd.read_excel(percorso_excel, sheet_name="Giacenze")
    df_giac["data_rilevazione"] = df_giac["data_rilevazione"].apply(data)
    df_giac["punto_id"] = df_giac["id_punto"].astype(str).str.strip().map(MAPPA_PUNTI)
    df_giac["prodotto_originale"] = df_giac["prodotto"].astype(str).str.strip()
    df_giac["categoria"] = df_giac["prodotto_originale"].map(MAPPA_CATEGORIE)
    df_giac["categoria_id"] = df_giac["categoria"].map(CAT_TO_ID)
    df_giac[["quantita", "unita"]] = df_giac["quantita"].apply(separa_quantita)
    df_giac["kg_stimato"] = df_giac["unita"] == "pz"
    df_giac["kg"] = df_giac.apply(
        lambda r: r["quantita"] if r["unita"] == "kg" else round(r["quantita"] * CAT_TO_PESO_PZ[r["categoria"]], 2),
        axis=1,
    )
    df_giac["scadenza_piu_vicina"] = df_giac["scadenza_piu_vicina"].apply(lambda x: data(x, allow_null=True))

    df_giac_out = df_giac[
        [
            "data_rilevazione",
            "punto_id",
            "categoria_id",
            "prodotto_originale",
            "quantita",
            "unita",
            "kg",
            "kg_stimato",
            "scadenza_piu_vicina",
        ]
    ].copy()
    df_giac_out.to_csv("giacenza.csv", index=False, encoding="utf-8")

    # 4. Scarti
    df_scarti = pd.read_excel(percorso_excel, sheet_name="Scarti")
    df_scarti["data"] = df_scarti["data"].apply(data)
    df_scarti["punto_id"] = df_scarti["punto"].astype(str).str.strip().map(MAPPA_PUNTI)
    df_scarti["prodotto_originale"] = df_scarti["prodotto"].astype(str).str.strip()
    df_scarti["categoria"] = df_scarti["prodotto_originale"].map(MAPPA_CATEGORIE)
    df_scarti["categoria_id"] = df_scarti["categoria"].map(CAT_TO_ID)
    df_scarti[["quantita", "unita"]] = df_scarti["quantita"].apply(separa_quantita)
    df_scarti["kg_stimato"] = df_scarti["unita"] == "pz"
    df_scarti["kg"] = df_scarti.apply(
        lambda r: r["quantita"] if r["unita"] == "kg" else round(r["quantita"] * CAT_TO_PESO_PZ[r["categoria"]], 2),
        axis=1,
    )
    df_scarti["causale"] = df_scarti["causale"].astype(str).str.strip().map(MAPPA_CAUSALI_SCARTO)
    df_scarti["operatore"] = df_scarti["operatore"].astype(str).str.strip()

    df_scarti_out = df_scarti[
        [
            "data",
            "punto_id",
            "categoria_id",
            "prodotto_originale",
            "quantita",
            "unita",
            "kg",
            "kg_stimato",
            "causale",
            "operatore",
        ]
    ].copy()
    df_scarti_out.to_csv("scarto.csv", index=False, encoding="utf-8")

    return df_giac_out, df_scarti_out


def elabora_turni(percorso_excel="turni_volontari.xlsx"):
    # 5. Turni
    df_turni = pd.read_excel(percorso_excel, sheet_name="Turni")
    df_turni["id"] = df_turni["id_turno"].astype(str).str.strip()
    df_turni["punto_id"] = df_turni["id_punto"].astype(str).str.strip().map(MAPPA_PUNTI)
    df_turni["data"] = df_turni["data"].apply(data)
    df_turni["fascia"] = df_turni["fascia"].astype(str).str.strip()
    df_turni["volontario_id"] = df_turni["id_volontario"].astype(str).str.strip()
    df_turni["ore_pianificate"] = df_turni["ore_pianificate"].astype(float)
    df_turni["stato"] = df_turni["stato"].astype(str).str.strip().map(MAPPA_STATI_TURNO)
    df_turni["sostituto_id"] = df_turni["id_sostituto"].apply(
        lambda x: None if pd.isna(x) or str(x).strip() == "" else str(x).strip()
    )

    df_turni_out = df_turni[
        [
            "id",
            "punto_id",
            "data",
            "fascia",
            "volontario_id",
            "ore_pianificate",
            "ore_effettive",
            "stato",
            "sostituto_id",
        ]
    ].copy()
    df_turni_out.to_csv("turno.csv", index=False, encoding="utf-8")
    return df_turni_out


if __name__ == "__main__":
    df_punti, df_ben, righe_ben_grezze = elabora_punti_e_beneficiari()
    df_giac, df_scarti = elabora_giacenze_e_scarti()
    df_turni = elabora_turni()

    punti_ammessi = {"PR01", "PR02", "PR03", "PR04", "PR05", "PR06", "PR07"}
    causali_ammesse = {"scaduto", "danneggiato", "non_idoneo"}
    stati_ammessi = {"coperto", "scoperto", "parziale", "sostituito"}
    stati_scheda_ammessi = {"attiva", "sospesa", "chiusa"}

    # Controlli assert come per le donazioni
    assert len(MAPPA_PUNTI) == 24
    assert set(df_punti["id"]) == punti_ammessi and len(df_punti) == 7
    assert df_punti["frigorifero"].isin([True, False]).all()

    assert len(df_ben) == 450 and df_ben["id"].nunique() == 450
    assert df_ben["n_minori"].isna().sum() == 0
    assert ((df_ben["n_minori"] + df_ben["n_over65"]) <= df_ben["n_componenti"]).all()
    assert set(df_ben["punto_id"]).issubset(punti_ammessi)
    assert set(df_ben["stato_scheda"]).issubset(stati_scheda_ammessi)
    assert df_ben["data_prima_registrazione"].isna().sum() == 0

    assert len(df_giac) == 5302
    assert set(df_giac["punto_id"]).issubset(punti_ammessi)
    assert df_giac["categoria_id"].isna().sum() == 0
    assert (df_giac["quantita"] >= 0).all()
    assert df_giac["data_rilevazione"].isna().sum() == 0

    assert len(df_scarti) == 1161
    assert set(df_scarti["punto_id"]).issubset(punti_ammessi)
    assert set(df_scarti["causale"]) == causali_ammesse
    assert df_scarti["categoria_id"].isna().sum() == 0
    assert (df_scarti["quantita"] > 0).all()
    assert df_scarti["data"].isna().sum() == 0

    assert len(df_turni) == 4469 and df_turni["id"].nunique() == 4469
    assert set(df_turni["punto_id"]).issubset(punti_ammessi)
    assert set(df_turni["stato"]) == stati_ammessi
    assert df_turni["data"].isna().sum() == 0

    print(f"[OK] punto_ritiro.csv: {len(df_punti)} punti (PR01-PR07)")
    print(f"[OK] beneficiario.csv: {righe_ben_grezze} righe -> {len(df_ben)} uniche (2 duplicati rimossi, 21 n_minori=0, B0078 corretto)")
    print(f"[OK] giacenza.csv: {len(df_giac)} righe ({df_giac['kg'].sum():.2f} kg stimati totali)")
    print(f"[OK] scarto.csv: {len(df_scarti)} righe ({df_scarti['kg'].sum():.2f} kg scartati | causali: {df_scarti['causale'].value_counts().to_dict()})")
    print(f"[OK] turno.csv: {len(df_turni)} righe (stati: {df_turni['stato'].value_counts().to_dict()})")