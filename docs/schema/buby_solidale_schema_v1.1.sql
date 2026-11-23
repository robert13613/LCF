-- =====================================================================
-- Buby Solidale - schema database v1.1 (PostgreSQL 15+)
-- 23/11/2026. Versione congelata insieme al contratto API v0.2.
-- Storia: v0.4 (costruito sui dati del committente, 1 settembre 2025 -
-- 31 ottobre 2026) + v0.5 (rischio delle assegnazioni, sostituti e
-- trasferimenti suggeriti, soglie, codici delle donazioni dall'app) = v1.0;
-- v1.0 + aggiunte v1.1 (feedback dall'app con sentiment, registro dei
-- caricamenti dei file settimanali) = v1.1.
-- Crea da zero lo stesso database che si ottiene lanciando v1.0 e poi
-- schema_v1.1_aggiunte.sql (differiscono solo i nomi di due vincoli).
-- Le modifiche successive si fanno con nuovi file di aggiunta (v1.1, ...),
-- mai riscrivendo questo file.
--
-- Struttura:
--   schema "solidale"  -> dati operativi e di analisi (codici pseudonimi)
--   schema "riservato" -> account e dati identificativi (mai al team dati)
--   ruoli di gruppo    -> ruolo_backend, ruolo_team_dati (vedi sezione 9)
--
-- Esecuzione: psql -d <database> -f buby_solidale_schema_v1.1.sql
--             oppure Supabase -> SQL Editor -> incolla tutto -> Run (solo su database vuoto)
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS solidale;
CREATE SCHEMA IF NOT EXISTS riservato;

SET search_path = solidale, public;

-- ---------------------------------------------------------------------
-- 1. TIPI ENUMERATI (il contratto dei valori ammessi, anche per le API)
-- ---------------------------------------------------------------------

CREATE TYPE solidale.unita_misura        AS ENUM ('kg', 'pz');
CREATE TYPE solidale.macro_categoria     AS ENUM ('alimentare', 'prima_necessita');
CREATE TYPE solidale.tipo_donatore       AS ENUM ('azienda', 'privato', 'ente');
CREATE TYPE solidale.ruolo_operatore     AS ENUM ('responsabile_punto', 'operatore_sociale');
CREATE TYPE solidale.fascia_eta          AS ENUM ('18-29', '30-44', '45-64', '65+');
CREATE TYPE solidale.stato_scheda        AS ENUM ('attiva', 'sospesa', 'chiusa');
CREATE TYPE solidale.canale_donazione    AS ENUM ('storico', 'app', 'email', 'telefono');
CREATE TYPE solidale.stato_donazione_t   AS ENUM ('offerta', 'accettata', 'rifiutata', 'ritiro_programmato', 'ricevuta', 'annullata');
CREATE TYPE solidale.causale_scarto      AS ENUM ('scaduto', 'non_idoneo', 'danneggiato');
CREATE TYPE solidale.fonte_distribuzione AS ENUM ('stimata_bilancio', 'registrata_app');
CREATE TYPE solidale.fascia_turno        AS ENUM ('mattina', 'pomeriggio');
CREATE TYPE solidale.stato_assegnazione  AS ENUM ('pianificato', 'coperto', 'parziale', 'scoperto', 'sostituito');
CREATE TYPE solidale.fonte_messaggio     AS ENUM ('email', 'chat_volontari', 'nota_operatore', 'recensione', 'feedback_app');
CREATE TYPE solidale.ruolo_autore        AS ENUM ('donatore', 'partner', 'ente_pubblico', 'volontario', 'operatore', 'visitatore', 'altro', 'beneficiario');
CREATE TYPE solidale.origine_segnalazione AS ENUM ('app', 'messaggio');
CREATE TYPE solidale.priorita_t          AS ENUM ('bassa', 'media', 'alta');
CREATE TYPE solidale.stato_segnalazione  AS ENUM ('aperta', 'in_gestione', 'chiusa');
CREATE TYPE solidale.target_previsione   AS ENUM ('donato_kg', 'distribuito_kg', 'eccedenza_kg', 'turni_scoperti');
CREATE TYPE solidale.stato_trasferimento AS ENUM ('suggerito', 'avvisato', 'fatto', 'ignorato');
CREATE TYPE solidale.sentiment_t         AS ENUM ('negativo', 'neutro', 'positivo');
CREATE TYPE solidale.tipo_caricamento    AS ENUM ('giacenze', 'scarti');
CREATE TYPE solidale.stato_caricamento   AS ENUM ('in_attesa', 'in_elaborazione', 'completato', 'completato_con_scarti', 'errore');
CREATE TYPE riservato.ruolo_utente       AS ENUM ('coordinatore', 'operatore', 'volontario', 'donatore', 'partner', 'admin');

-- ---------------------------------------------------------------------
-- 2. ANAGRAFICHE DI RIFERIMENTO
-- ---------------------------------------------------------------------

CREATE TABLE solidale.punto_ritiro (
    id            text PRIMARY KEY CHECK (id ~ '^PR[0-9]{2}$'),
    nome          text NOT NULL UNIQUE,
    comune        text NOT NULL,
    indirizzo     text NOT NULL,
    capienza_kg   numeric(8,1) CHECK (capienza_kg > 0),
    frigorifero   boolean NOT NULL
);
COMMENT ON TABLE  solidale.punto_ritiro IS 'Fonte: anagrafiche_buby_solidale.xlsx, foglio "Punti di ritiro" (7 punti).';
COMMENT ON COLUMN solidale.punto_ritiro.capienza_kg IS 'NULL per PR06: dato mancante nella fonte.';

CREATE TABLE solidale.punto_apertura (
    punto_id          text NOT NULL REFERENCES solidale.punto_ritiro(id),
    giorno_settimana  smallint NOT NULL CHECK (giorno_settimana BETWEEN 1 AND 7),
    ora_apertura      time NOT NULL,
    ora_chiusura      time NOT NULL,
    PRIMARY KEY (punto_id, giorno_settimana, ora_apertura),
    CHECK (ora_chiusura > ora_apertura)
);
COMMENT ON TABLE  solidale.punto_apertura IS 'Normalizza "giorni_apertura" e "orario" della fonte. giorno_settimana: 1 = lunedi (ISO).';

CREATE TABLE solidale.categoria_prodotto (
    id                 smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome               text NOT NULL UNIQUE,
    macro              solidale.macro_categoria NOT NULL,
    unita_standard     solidale.unita_misura NOT NULL,
    peso_medio_pz_kg   numeric(6,3) CHECK (peso_medio_pz_kg > 0),
    deperibile         boolean NOT NULL,
    richiede_frigo     boolean NOT NULL,
    conta_come_pasti   boolean NOT NULL,
    CHECK (unita_standard = 'kg' OR peso_medio_pz_kg IS NOT NULL)
);
COMMENT ON TABLE  solidale.categoria_prodotto IS '14 categorie canoniche. I 51 nomi grezzi della fonte sono mappati nella pipeline di pulizia.';
COMMENT ON COLUMN solidale.categoria_prodotto.peso_medio_pz_kg IS 'Ipotesi dichiarata (dato sintetico ammesso dal committente) per convertire i pezzi in kg.';
COMMENT ON COLUMN solidale.categoria_prodotto.conta_come_pasti IS 'false per igiene e detersivi: non entrano nel calcolo dei pasti.';

CREATE TABLE solidale.donatore (
    id              text PRIMARY KEY CHECK (id ~ '^D[0-9]{3}$'),
    tipo            solidale.tipo_donatore,
    tipo_sintetico  boolean NOT NULL DEFAULT false
);
COMMENT ON TABLE solidale.donatore IS 'Solo codici (D001-D036). Il tipo non e nella fonte: NULL o sintetico dichiarato.';

CREATE TABLE solidale.volontario (
    id                  text PRIMARY KEY CHECK (id ~ '^V[0-9]{3}$'),
    punto_preferito_id  text REFERENCES solidale.punto_ritiro(id),
    attivo              boolean NOT NULL DEFAULT true
);

CREATE TABLE solidale.operatore (
    id     text PRIMARY KEY CHECK (id ~ '^OP[0-9]{2}$'),
    ruolo  solidale.ruolo_operatore
);
COMMENT ON TABLE solidale.operatore IS 'OP01-OP06 compaiono sia negli scarti sia nelle note degli operatori sociali: ruolo da confermare.';

CREATE TABLE solidale.beneficiario (
    id                        text PRIMARY KEY CHECK (id ~ '^B[0-9]{4}$'),
    fascia_eta_referente      solidale.fascia_eta NOT NULL,
    n_componenti              smallint NOT NULL CHECK (n_componenti >= 1),
    n_minori                  smallint CHECK (n_minori >= 0),
    n_over65                  smallint NOT NULL CHECK (n_over65 >= 0),
    comune_residenza          text NOT NULL,
    punto_riferimento_id      text NOT NULL REFERENCES solidale.punto_ritiro(id),
    data_prima_registrazione  date NOT NULL,
    accessi_ultimi_12_mesi    smallint NOT NULL CHECK (accessi_ultimi_12_mesi >= 0),
    accessi_riferiti_al       date NOT NULL DEFAULT DATE '2026-10-31',
    stato_scheda              solidale.stato_scheda NOT NULL,
    CHECK (n_minori IS NULL OR n_minori + n_over65 <= n_componenti)
);
COMMENT ON TABLE  solidale.beneficiario IS 'Fonte: foglio "Beneficiari anonimi" (452 righe, 450 codici unici). Nessun dato identificativo.';
COMMENT ON COLUMN solidale.beneficiario.n_minori IS '21 valori mancanti nella fonte.';

-- ---------------------------------------------------------------------
-- 3. FLUSSO DEI BENI
-- ---------------------------------------------------------------------

-- Codici delle donazioni inserite dall'app: DON-10001, DON-10002, ...
-- (le storiche arrivano fino a DON-03385 e la pipeline le carica con il loro codice)
CREATE SEQUENCE solidale.donazione_app_seq START WITH 10001;

CREATE TABLE solidale.donazione (
    id               text PRIMARY KEY CHECK (id ~ '^DON-[0-9]{5}$')
                     DEFAULT 'DON-' || lpad(nextval('solidale.donazione_app_seq')::text, 5, '0'),
    data             date NOT NULL,
    donatore_id      text REFERENCES solidale.donatore(id),
    punto_id         text NOT NULL REFERENCES solidale.punto_ritiro(id),
    canale           solidale.canale_donazione NOT NULL DEFAULT 'storico',
    messaggio_id     bigint,                       -- FK aggiunta dopo la creazione di messaggio
    stato_corrente   solidale.stato_donazione_t NOT NULL DEFAULT 'ricevuta'
);
COMMENT ON TABLE  solidale.donazione IS 'Fonte: donazioni_set2025_ott2026.xlsx (3.385 donazioni).';
COMMENT ON COLUMN solidale.donazione.donatore_id IS 'NULL in 85 donazioni della fonte.';
COMMENT ON COLUMN solidale.donazione.stato_corrente IS 'Aggiornato dal trigger su stato_donazione.';

CREATE TABLE solidale.donazione_riga (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    donazione_id        text NOT NULL REFERENCES solidale.donazione(id) ON DELETE CASCADE,
    categoria_id        smallint NOT NULL REFERENCES solidale.categoria_prodotto(id),
    prodotto_originale  text NOT NULL,
    quantita            numeric(10,2) NOT NULL CHECK (quantita > 0),
    unita               solidale.unita_misura NOT NULL,
    kg                  numeric(10,2) NOT NULL CHECK (kg > 0),
    kg_stimato          boolean NOT NULL,
    CHECK (unita = 'pz' OR (kg = quantita AND NOT kg_stimato))
);
COMMENT ON TABLE  solidale.donazione_riga IS 'Fonte: 6.847 righe. kg = quantita se in kg, altrimenti quantita * peso_medio_pz_kg (kg_stimato = true).';

CREATE TABLE solidale.stato_donazione (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    donazione_id   text NOT NULL REFERENCES solidale.donazione(id) ON DELETE CASCADE,
    stato          solidale.stato_donazione_t NOT NULL,
    cambiato_il    timestamptz NOT NULL DEFAULT now(),
    utente_id      bigint,                         -- FK verso riservato.utente, aggiunta piu sotto
    nota           text
);
COMMENT ON TABLE solidale.stato_donazione IS 'Storico degli stati per le donazioni inserite dall app. Le storiche hanno una sola riga "ricevuta".';

CREATE TABLE solidale.giacenza (
    data_rilevazione     date NOT NULL,
    punto_id             text NOT NULL REFERENCES solidale.punto_ritiro(id),
    categoria_id         smallint NOT NULL REFERENCES solidale.categoria_prodotto(id),
    quantita             numeric(10,2) NOT NULL CHECK (quantita >= 0),
    unita                solidale.unita_misura NOT NULL,
    kg                   numeric(10,2) NOT NULL CHECK (kg >= 0),
    scadenza_piu_vicina  date,
    PRIMARY KEY (data_rilevazione, punto_id, categoria_id),
    CHECK (extract(isodow FROM data_rilevazione) = 1)
);
COMMENT ON TABLE  solidale.giacenza IS 'Fonte: foglio "Giacenze". Fotografia di ogni lunedi per punto e categoria (61 settimane).';
COMMENT ON COLUMN solidale.giacenza.scadenza_piu_vicina IS '340 righe della fonte hanno una scadenza gia passata alla data di rilevazione.';

CREATE TABLE solidale.scarto (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data                date NOT NULL,
    punto_id            text NOT NULL REFERENCES solidale.punto_ritiro(id),
    categoria_id        smallint NOT NULL REFERENCES solidale.categoria_prodotto(id),
    prodotto_originale  text NOT NULL,
    quantita            numeric(10,2) NOT NULL CHECK (quantita > 0),
    unita               solidale.unita_misura NOT NULL,
    kg                  numeric(10,2) NOT NULL CHECK (kg > 0),
    causale             solidale.causale_scarto NOT NULL,
    causale_originale   text NOT NULL,
    operatore_id        text REFERENCES solidale.operatore(id)
);
COMMENT ON TABLE solidale.scarto IS 'Fonte: foglio "Scarti". Stima minima dello spreco: la registrazione non e uniforme tra i punti (committente, 12/11/2026).';

CREATE TABLE solidale.distribuzione (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    punto_id         text NOT NULL REFERENCES solidale.punto_ritiro(id),
    categoria_id     smallint NOT NULL REFERENCES solidale.categoria_prodotto(id),
    periodo_inizio   date NOT NULL,
    periodo_fine     date NOT NULL,
    kg               numeric(10,2) NOT NULL CHECK (kg >= 0),
    beneficiario_id  text REFERENCES solidale.beneficiario(id),
    fonte            solidale.fonte_distribuzione NOT NULL,
    CHECK (periodo_fine >= periodo_inizio),
    CHECK (fonte = 'registrata_app' OR beneficiario_id IS NULL)
);
COMMENT ON TABLE solidale.distribuzione IS 'La fonte non contiene distribuzioni. stimata_bilancio = giacenza inizio + donato - scartato - giacenza fine, per settimana. registrata_app = inserite in futuro dall app.';

-- ---------------------------------------------------------------------
-- 4. VOLONTARI E TURNI
-- ---------------------------------------------------------------------

CREATE TABLE solidale.turno (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    punto_id    text NOT NULL REFERENCES solidale.punto_ritiro(id),
    data        date NOT NULL,
    fascia      solidale.fascia_turno NOT NULL,
    ora_inizio  time NOT NULL,
    ora_fine    time NOT NULL,
    UNIQUE (punto_id, data, fascia),
    CHECK (ora_fine > ora_inizio)
);
COMMENT ON TABLE solidale.turno IS 'Lo slot (punto + data + fascia), ricavato dalle righe del foglio "Turni".';

CREATE TABLE solidale.assegnazione (
    id               text PRIMARY KEY CHECK (id ~ '^T[0-9]{5}$'),
    turno_id         bigint NOT NULL REFERENCES solidale.turno(id),
    volontario_id    text NOT NULL REFERENCES solidale.volontario(id),
    ore_pianificate  numeric(4,1) NOT NULL CHECK (ore_pianificate > 0),
    ore_effettive    numeric(4,1) CHECK (ore_effettive >= 0),
    stato            solidale.stato_assegnazione NOT NULL,
    sostituto_id     text REFERENCES solidale.volontario(id),
    CHECK ((stato = 'sostituito') = (sostituto_id IS NOT NULL)),
    CHECK (stato <> 'scoperto' OR ore_effettive IS NULL),
    CHECK (sostituto_id IS DISTINCT FROM volontario_id)
);
COMMENT ON TABLE solidale.assegnazione IS 'Fonte: foglio "Turni" (4.469 righe). Ogni riga e un volontario assegnato a uno slot; il suo id_turno (T00001) diventa l id dell assegnazione.';

-- ---------------------------------------------------------------------
-- 5. TESTI E SEGNALAZIONI
-- ---------------------------------------------------------------------

CREATE TABLE solidale.messaggio (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fonte               solidale.fonte_messaggio NOT NULL,
    ricevuto_il         timestamptz NOT NULL,
    autore_ruolo        solidale.ruolo_autore,
    operatore_id        text REFERENCES solidale.operatore(id),
    beneficiario_id     text REFERENCES solidale.beneficiario(id),
    voto                smallint CHECK (voto BETWEEN 1 AND 5),
    oggetto             text,
    testo_anonimizzato  text NOT NULL,
    categoria_predetta  text,
    confidenza          numeric(4,3) CHECK (confidenza BETWEEN 0 AND 1),
    entita_estratte     jsonb,
    etichetta_manuale   text,
    modello_versione    text,
    punto_id            text REFERENCES solidale.punto_ritiro(id),
    sentiment           solidale.sentiment_t,
    sentiment_punteggio numeric(4,3) CHECK (sentiment_punteggio BETWEEN -1 AND 1),
    CONSTRAINT messaggio_voto_solo_recensioni_e_feedback CHECK (fonte::text IN ('recensione', 'feedback_app') OR voto IS NULL),
    CONSTRAINT messaggio_nota_solo_operatore CHECK (fonte = 'nota_operatore' OR (operatore_id IS NULL AND beneficiario_id IS NULL))
);
COMMENT ON TABLE  solidale.messaggio IS 'Fonte: comunicazioni_e_note.docx. Il testo si salva solo dopo l anonimizzazione (nomi, telefoni, email, codici fiscali).';
COMMENT ON COLUMN solidale.messaggio.testo_anonimizzato IS 'Le note operatori contengono dati art. 9 GDPR (salute, religione): ridurre a etichette dove possibile.';
COMMENT ON COLUMN solidale.messaggio.punto_id IS 'Punto a cui si riferisce il messaggio (facoltativo), es. il punto valutato in un feedback.';
COMMENT ON COLUMN solidale.messaggio.sentiment IS 'Scritto dal modello di sentiment, come categoria_predetta.';
COMMENT ON COLUMN solidale.messaggio.sentiment_punteggio IS 'Da -1 (molto negativo) a +1 (molto positivo).';
COMMENT ON COLUMN solidale.messaggio.etichetta_manuale IS 'Etichetta assegnata a mano: serve a misurare precision, recall e F1 del classificatore.';

ALTER TABLE solidale.donazione
    ADD CONSTRAINT donazione_messaggio_fk FOREIGN KEY (messaggio_id) REFERENCES solidale.messaggio(id);

CREATE TABLE solidale.segnalazione (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    origine             solidale.origine_segnalazione NOT NULL,
    messaggio_id        bigint REFERENCES solidale.messaggio(id),
    autore_ruolo        solidale.ruolo_autore,
    creata_il           timestamptz NOT NULL DEFAULT now(),
    categoria           text NOT NULL,
    priorita            solidale.priorita_t NOT NULL,
    stato               solidale.stato_segnalazione NOT NULL DEFAULT 'aperta',
    chiusa_il           timestamptz,
    testo_anonimizzato  text,
    donazione_id        text REFERENCES solidale.donazione(id),
    punto_id            text REFERENCES solidale.punto_ritiro(id),
    turno_id            bigint REFERENCES solidale.turno(id),
    CHECK (num_nonnulls(donazione_id, punto_id, turno_id) >= 1),
    CHECK (origine = 'app' OR messaggio_id IS NOT NULL),
    CHECK ((stato = 'chiusa') = (chiusa_il IS NOT NULL))
);
COMMENT ON COLUMN solidale.segnalazione.categoria IS 'Esempi dai testi: catena_freddo, scorte_esaurite, turno_scoperto, ricevuta_mancante, frigo_guasto.';

-- Registro dei caricamenti (staging): l'admin carica dall'app il file
-- Excel settimanale; il file resta nello storage, la pipeline lo pulisce,
-- lo controlla e lo carica, poi scrive qui l'esito.
CREATE TABLE solidale.caricamento (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo             solidale.tipo_caricamento NOT NULL,
    nome_file        text NOT NULL,
    percorso_file    text NOT NULL,
    caricato_da      bigint,
    caricato_il      timestamptz NOT NULL DEFAULT now(),
    stato            solidale.stato_caricamento NOT NULL DEFAULT 'in_attesa',
    elaborato_il     timestamptz,
    righe_lette      integer CHECK (righe_lette >= 0),
    righe_caricate   integer CHECK (righe_caricate >= 0),
    righe_scartate   integer CHECK (righe_scartate >= 0),
    errori           jsonb,
    CHECK (righe_caricate IS NULL OR righe_lette IS NULL OR righe_caricate + coalesce(righe_scartate, 0) <= righe_lette)
);
COMMENT ON TABLE  solidale.caricamento IS 'Un file caricato dall app. Lo scrive il backend (in_attesa); la pipeline aggiorna stato, conteggi ed errori.';
COMMENT ON COLUMN solidale.caricamento.percorso_file IS 'Dove sta il file grezzo nello storage di staging, es. staging/2026-11-23/giacenze_PR03.xlsx.';
COMMENT ON COLUMN solidale.caricamento.caricato_da IS 'Id dell utente in riservato.utente (senza vincolo, cosi il team dati non legge lo schema riservato).';
COMMENT ON COLUMN solidale.caricamento.errori IS 'Righe scartate e perche, es. [{"riga": 14, "motivo": "data illeggibile"}].';
CREATE INDEX ix_caricamento_data ON solidale.caricamento (caricato_il DESC);

-- ---------------------------------------------------------------------
-- 6. ANALISI
-- ---------------------------------------------------------------------

CREATE TABLE solidale.previsione (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    target            solidale.target_previsione NOT NULL,
    punto_id          text NOT NULL REFERENCES solidale.punto_ritiro(id),
    categoria_id      smallint REFERENCES solidale.categoria_prodotto(id),
    periodo_inizio    date NOT NULL,
    periodo_fine      date NOT NULL,
    valore_previsto   numeric(12,2) NOT NULL,
    intervallo_basso  numeric(12,2),
    intervallo_alto   numeric(12,2),
    valore_reale      numeric(12,2),
    modello           text NOT NULL,
    versione          text NOT NULL,
    generata_il       timestamptz NOT NULL DEFAULT now(),
    CHECK (periodo_fine >= periodo_inizio),
    CHECK (intervallo_basso IS NULL OR intervallo_basso <= valore_previsto),
    CHECK (intervallo_alto  IS NULL OR intervallo_alto  >= valore_previsto),
    UNIQUE NULLS NOT DISTINCT (target, punto_id, categoria_id, periodo_inizio, modello, versione)
);
COMMENT ON TABLE solidale.previsione IS 'Ogni stima accanto al valore reale: le metriche di errore (MAE, WAPE) sono nella vista v_accuratezza_previsioni.';

CREATE TABLE solidale.parametro (
    chiave      text PRIMARY KEY,
    valore      numeric NOT NULL,
    unita       text,
    fonte       text NOT NULL,
    valido_dal  date NOT NULL
);

-- Risultati dei modelli letti dal backend (aggiunti con il contratto API)
-- GET /api/turni
CREATE TABLE solidale.rischio_assegnazione (
    assegnazione_id  text PRIMARY KEY REFERENCES solidale.assegnazione(id) ON DELETE CASCADE,
    probabilita      numeric(4,3) NOT NULL CHECK (probabilita BETWEEN 0 AND 1),
    modello          text NOT NULL,
    versione         text NOT NULL,
    generata_il      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE solidale.rischio_assegnazione IS 'Probabilita stimata che l assegnazione resti scoperta. Una riga per assegnazione, sovrascritta a ogni esecuzione del modello.';

-- GET /api/assegnazioni/{id}/sostituti
CREATE TABLE solidale.sostituto_suggerito (
    assegnazione_id  text NOT NULL REFERENCES solidale.assegnazione(id) ON DELETE CASCADE,
    volontario_id    text NOT NULL REFERENCES solidale.volontario(id),
    posizione        smallint NOT NULL CHECK (posizione BETWEEN 1 AND 5),
    punteggio        numeric(4,3) NOT NULL CHECK (punteggio BETWEEN 0 AND 1),
    motivi           text[] NOT NULL DEFAULT '{}',
    modello          text NOT NULL,
    versione         text NOT NULL,
    generata_il      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (assegnazione_id, volontario_id),
    UNIQUE (assegnazione_id, posizione)
);
COMMENT ON COLUMN solidale.sostituto_suggerito.motivi IS 'Frasi brevi mostrate cosi come sono, es. "Punto preferito PR03".';

-- GET /api/trasferimenti
CREATE TABLE solidale.trasferimento_suggerito (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    settimana            date NOT NULL CHECK (extract(isodow FROM settimana) = 1),
    da_punto_id          text NOT NULL REFERENCES solidale.punto_ritiro(id),
    a_punto_id           text NOT NULL REFERENCES solidale.punto_ritiro(id),
    categoria_id         smallint NOT NULL REFERENCES solidale.categoria_prodotto(id),
    kg                   numeric(10,2) NOT NULL CHECK (kg > 0),
    scadenza_piu_vicina  date,
    motivo               text NOT NULL,
    messaggio_volontari  text NOT NULL,
    volontari_suggeriti  text[] NOT NULL DEFAULT '{}',
    stato                solidale.stato_trasferimento NOT NULL DEFAULT 'suggerito',
    modello              text NOT NULL,
    versione             text NOT NULL,
    generata_il          timestamptz NOT NULL DEFAULT now(),
    CHECK (da_punto_id <> a_punto_id)
);
COMMENT ON COLUMN solidale.trasferimento_suggerito.messaggio_volontari IS 'Testo pronto da copiare. Mai nomi di persone: i nomi li aggiunge il backend solo per il coordinatore.';
COMMENT ON COLUMN solidale.trasferimento_suggerito.volontari_suggeriti IS 'Codici volontario (V012...) in ordine di preferenza.';
CREATE INDEX ix_trasferimento_settimana ON solidale.trasferimento_suggerito (settimana, da_punto_id);

-- ---------------------------------------------------------------------
-- 7. ACCOUNT E DATI RISERVATI (schema separato)
-- ---------------------------------------------------------------------

CREATE TABLE riservato.utente (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email          text NOT NULL UNIQUE,
    password_hash  text NOT NULL,
    ruolo          riservato.ruolo_utente NOT NULL,
    soggetto_id    text,
    attivo         boolean NOT NULL DEFAULT true,
    creato_il      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN riservato.utente.soggetto_id IS 'Codice D.., V.. o OP.. collegato all account.';

CREATE TABLE riservato.anagrafica_riservata (
    soggetto_id             text PRIMARY KEY,
    nome_o_ragione_sociale  text NOT NULL,
    email                   text,
    telefono                text
);
COMMENT ON TABLE riservato.anagrafica_riservata IS 'Dati identificativi, solo coordinatori e admin. Vuota per lo storico: la fonte Excel contiene solo codici.';

ALTER TABLE solidale.stato_donazione
    ADD CONSTRAINT stato_donazione_utente_fk FOREIGN KEY (utente_id) REFERENCES riservato.utente(id);

-- ---------------------------------------------------------------------
-- 8. TRIGGER, INDICI, VISTE
-- ---------------------------------------------------------------------

-- Tiene allineato donazione.stato_corrente all ultimo stato registrato
CREATE FUNCTION solidale.aggiorna_stato_donazione() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE solidale.donazione
       SET stato_corrente = NEW.stato
     WHERE id = NEW.donazione_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_stato_donazione
AFTER INSERT ON solidale.stato_donazione
FOR EACH ROW EXECUTE FUNCTION solidale.aggiorna_stato_donazione();

CREATE INDEX ix_donazione_punto_data  ON solidale.donazione (punto_id, data);
CREATE INDEX ix_donazione_donatore    ON solidale.donazione (donatore_id);
CREATE INDEX ix_riga_donazione        ON solidale.donazione_riga (donazione_id);
CREATE INDEX ix_riga_categoria        ON solidale.donazione_riga (categoria_id);
CREATE INDEX ix_stato_donazione       ON solidale.stato_donazione (donazione_id, cambiato_il);
CREATE INDEX ix_giacenza_scadenza     ON solidale.giacenza (scadenza_piu_vicina);
CREATE INDEX ix_scarto_punto_data     ON solidale.scarto (punto_id, data);
CREATE INDEX ix_distribuzione_punto   ON solidale.distribuzione (punto_id, periodo_inizio);
CREATE INDEX ix_assegnazione_turno    ON solidale.assegnazione (turno_id);
CREATE INDEX ix_assegnazione_volont   ON solidale.assegnazione (volontario_id);
CREATE INDEX ix_messaggio_fonte_data  ON solidale.messaggio (fonte, ricevuto_il);
CREATE INDEX ix_messaggio_entita      ON solidale.messaggio USING gin (entita_estratte);
CREATE INDEX ix_segnalazione_aperte   ON solidale.segnalazione (priorita, creata_il) WHERE stato <> 'chiusa';

-- Impatto mensile per punto: kg recuperati, scartati, distribuiti e pasti equivalenti
CREATE VIEW solidale.v_impatto_mensile AS
WITH donato AS (
    SELECT d.punto_id, date_trunc('month', d.data)::date AS mese, sum(r.kg) AS kg_recuperati
    FROM solidale.donazione d
    JOIN solidale.donazione_riga r ON r.donazione_id = d.id
    GROUP BY 1, 2
), scartato AS (
    SELECT punto_id, date_trunc('month', data)::date AS mese, sum(kg) AS kg_scartati
    FROM solidale.scarto
    GROUP BY 1, 2
), distribuito AS (
    SELECT di.punto_id, date_trunc('month', di.periodo_inizio)::date AS mese,
           sum(di.kg) AS kg_distribuiti,
           sum(di.kg) FILTER (WHERE c.conta_come_pasti) AS kg_alimentari
    FROM solidale.distribuzione di
    JOIN solidale.categoria_prodotto c ON c.id = di.categoria_id
    GROUP BY 1, 2
)
SELECT d.punto_id, d.mese, d.kg_recuperati,
       coalesce(s.kg_scartati, 0)    AS kg_scartati,
       coalesce(x.kg_distribuiti, 0) AS kg_distribuiti,
       round(coalesce(x.kg_alimentari, 0)
             / (SELECT valore FROM solidale.parametro WHERE chiave = 'kg_per_pasto')) AS pasti_equivalenti
FROM donato d
LEFT JOIN scartato s    USING (punto_id, mese)
LEFT JOIN distribuito x USING (punto_id, mese);

-- Copertura dei turni per punto e mese
CREATE VIEW solidale.v_copertura_turni AS
SELECT t.punto_id, date_trunc('month', t.data)::date AS mese,
       count(*)                                                AS assegnazioni,
       count(*) FILTER (WHERE a.stato IN ('coperto', 'sostituito')) AS coperte,
       count(*) FILTER (WHERE a.stato = 'parziale')            AS parziali,
       count(*) FILTER (WHERE a.stato = 'scoperto')            AS scoperte,
       round(count(*) FILTER (WHERE a.stato = 'scoperto')::numeric / count(*), 3) AS tasso_scopertura
FROM solidale.assegnazione a
JOIN solidale.turno t ON t.id = a.turno_id
GROUP BY 1, 2;

-- Giacenze con prodotti gia scaduti al momento della rilevazione
CREATE VIEW solidale.v_giacenza_scaduta AS
SELECT g.data_rilevazione, g.punto_id, c.nome AS categoria, g.kg, g.scadenza_piu_vicina,
       g.data_rilevazione - g.scadenza_piu_vicina AS giorni_oltre_scadenza
FROM solidale.giacenza g
JOIN solidale.categoria_prodotto c ON c.id = g.categoria_id
WHERE g.scadenza_piu_vicina < g.data_rilevazione;

-- Accuratezza delle previsioni concluse, per target, punto e modello
CREATE VIEW solidale.v_accuratezza_previsioni AS
SELECT target, punto_id, modello, versione,
       count(*)                                          AS n_periodi,
       round(avg(abs(valore_reale - valore_previsto)), 2) AS mae,
       round(sum(abs(valore_reale - valore_previsto)) / nullif(sum(abs(valore_reale)), 0), 3) AS wape
FROM solidale.previsione
WHERE valore_reale IS NOT NULL
GROUP BY 1, 2, 3, 4;

-- ---------------------------------------------------------------------
-- 9. RUOLI E PERMESSI (ruoli di gruppo: il DBA crea gli utenti di login)
-- ---------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ruolo_backend') THEN
        CREATE ROLE ruolo_backend NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ruolo_team_dati') THEN
        CREATE ROLE ruolo_team_dati NOLOGIN;
    END IF;
END
$$;

-- Backend (WSA): lettura e scrittura su entrambi gli schemi
GRANT USAGE ON SCHEMA solidale, riservato TO ruolo_backend;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA solidale, riservato TO ruolo_backend;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA solidale, riservato TO ruolo_backend;

-- Team dati (DAI): carica e analizza i dati, nessun accesso allo schema riservato
GRANT USAGE ON SCHEMA solidale TO ruolo_team_dati;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA solidale TO ruolo_team_dati;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA solidale TO ruolo_team_dati;
REVOKE ALL ON SCHEMA riservato FROM ruolo_team_dati;
REVOKE ALL ON SCHEMA riservato FROM PUBLIC;

-- Gli stessi permessi valgono per le tabelle create in futuro dall utente che esegue lo script
ALTER DEFAULT PRIVILEGES IN SCHEMA solidale  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ruolo_backend, ruolo_team_dati;
ALTER DEFAULT PRIVILEGES IN SCHEMA solidale  GRANT USAGE ON SEQUENCES TO ruolo_backend, ruolo_team_dati;
ALTER DEFAULT PRIVILEGES IN SCHEMA riservato GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ruolo_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA riservato GRANT USAGE ON SEQUENCES TO ruolo_backend;

-- Esempio di utenti di login (da adattare):
--   CREATE ROLE app_web  LOGIN PASSWORD '...' IN ROLE ruolo_backend;
--   CREATE ROLE dai_mario LOGIN PASSWORD '...' IN ROLE ruolo_team_dati;

-- ---------------------------------------------------------------------
-- 10. PARAMETRI NOTI
-- ---------------------------------------------------------------------

INSERT INTO solidale.parametro (chiave, valore, unita, fonte, valido_dal)
VALUES ('kg_per_pasto', 0.5, 'kg', 'Committente, email del 12/11/2026: 1 pasto = 0,5 kg di alimenti', DATE '2025-09-01'),
    ('giorni_urgenza_alta',  2,    'giorni',      'Contratto API v0.1: fino a 2 giorni alla scadenza = urgenza alta',  DATE '2025-09-01'),
    ('giorni_urgenza_media', 7,    'giorni',      'Contratto API v0.1: da 3 a 7 giorni = urgenza media',               DATE '2025-09-01'),
    ('soglia_rischio_alto',  0.30, 'probabilita', 'Contratto API v0.1: tasso medio di scopertura circa 0,095',         DATE '2025-09-01'),
    ('soglia_rischio_medio', 0.15, 'probabilita', 'Contratto API v0.1',                                                DATE '2025-09-01');

COMMIT;
