-- =====================================================================
-- Buby Solidale – una query per ogni richiesta del contratto API v0.2 (schema v1.0 + v1.1)
-- Ogni query restituisce UNA riga con il JSON già nella forma del contratto:
-- il backend può eseguirla e restituire il risultato così com'è.
--
-- Qui i parametri sono variabili di psql (:'punto', :'settimana', ...). Nel backend
-- diventano parametri della query (es. %(punto)s con psycopg); stringa vuota = parametro assente.
-- Prova in locale:  psql -d <db> -v punto=PR03 -v settimana= -v ruolo=coordinatore ... -f query_contratto.sql
-- =====================================================================

-- Gli orari dei messaggi escono con il fuso italiano (impostarlo anche nella connessione del backend)
SET TIME ZONE 'Europe/Rome';

-- ---------------------------------------------------------------------
-- 1. GET /api/anagrafiche
-- ---------------------------------------------------------------------
SELECT json_build_object(
  'punti', (SELECT json_agg(json_build_object(
              'id', id, 'nome', nome, 'comune', comune,
              'frigorifero', frigorifero, 'capienza_kg', capienza_kg) ORDER BY id)
            FROM solidale.punto_ritiro),
  'categorie', (SELECT json_agg(json_build_object(
              'id', id, 'nome', nome, 'macro', macro, 'unita_standard', unita_standard,
              'deperibile', deperibile, 'richiede_frigo', richiede_frigo) ORDER BY id)
            FROM solidale.categoria_prodotto),
  'settimane', (SELECT json_build_object('prima', min(data_rilevazione), 'ultima', max(data_rilevazione))
            FROM solidale.giacenza)
) AS risposta;

-- ---------------------------------------------------------------------
-- 2. GET /api/scadenze?punto=&settimana=
-- ---------------------------------------------------------------------
WITH par AS (
  SELECT :'punto'::text AS punto,
         coalesce(nullif(:'settimana', '')::date,
                  (SELECT max(data_rilevazione) FROM solidale.giacenza)) AS sett,
         (SELECT valore FROM solidale.parametro WHERE chiave = 'giorni_urgenza_alta')  AS g_alta,
         (SELECT valore FROM solidale.parametro WHERE chiave = 'giorni_urgenza_media') AS g_media
), righe AS (
  SELECT g.categoria_id, c.nome AS categoria, g.kg, (g.unita = 'pz') AS kg_stimato,
         g.scadenza_piu_vicina, g.scadenza_piu_vicina - p.sett AS giorni, c.richiede_frigo,
         CASE WHEN g.scadenza_piu_vicina IS NULL          THEN 'nessuna'
              WHEN g.scadenza_piu_vicina - p.sett < 0       THEN 'scaduta'
              WHEN g.scadenza_piu_vicina - p.sett <= p.g_alta  THEN 'alta'
              WHEN g.scadenza_piu_vicina - p.sett <= p.g_media THEN 'media'
              ELSE 'bassa' END AS urgenza
  FROM solidale.giacenza g
  JOIN solidale.categoria_prodotto c ON c.id = g.categoria_id
  JOIN par p ON g.punto_id = p.punto AND g.data_rilevazione = p.sett
  WHERE g.kg > 0
), prev AS (
  SELECT count(*) AS n,
         max(valore_previsto) FILTER (WHERE target = 'donato_kg')      AS donato_kg,
         max(valore_previsto) FILTER (WHERE target = 'distribuito_kg') AS distribuito_kg,
         max(modello) AS modello
  FROM solidale.previsione pr JOIN par p
    ON pr.punto_id = p.punto AND pr.periodo_inizio = p.sett + 7 AND pr.categoria_id IS NULL
)
SELECT json_build_object(
  'punto_id', (SELECT punto FROM par),
  'settimana', (SELECT sett FROM par),
  'righe', coalesce((SELECT json_agg(json_build_object(
              'categoria_id', categoria_id, 'categoria', categoria, 'kg', round(kg, 1),
              'kg_stimato', kg_stimato, 'scadenza_piu_vicina', scadenza_piu_vicina,
              'giorni_alla_scadenza', giorni, 'urgenza', urgenza, 'richiede_frigo', richiede_frigo)
            ORDER BY giorni NULLS LAST, categoria) FROM righe), '[]'::json),
  'totali', (SELECT json_build_object(
              'kg_in_giacenza',  round(coalesce(sum(kg), 0), 1),
              'kg_urgenza_alta', round(coalesce(sum(kg) FILTER (WHERE urgenza = 'alta'), 0), 1),
              'kg_scaduti',      round(coalesce(sum(kg) FILTER (WHERE urgenza = 'scaduta'), 0), 1))
            FROM righe),
  'previsione_settimana_successiva', (SELECT CASE WHEN n = 0 THEN NULL ELSE json_build_object(
              'donato_kg', donato_kg, 'distribuito_kg', distribuito_kg, 'modello', modello) END FROM prev)
) AS risposta;
-- Il backend restituisce 404 se il punto non esiste, 400 se settimana non è un lunedì.

-- ---------------------------------------------------------------------
-- 3. GET /api/trasferimenti?punto=&settimana=
-- ---------------------------------------------------------------------
WITH par AS (
  SELECT nullif(:'punto', '') AS punto,
         coalesce(nullif(:'settimana', '')::date,
                  (SELECT max(data_rilevazione) FROM solidale.giacenza)) AS sett,
         :'ruolo'::text AS ruolo
)
SELECT json_build_object(
  'settimana', (SELECT sett FROM par),
  'trasferimenti', coalesce((
    SELECT json_agg(json_build_object(
      'id', t.id, 'da_punto_id', t.da_punto_id, 'a_punto_id', t.a_punto_id,
      'categoria_id', t.categoria_id, 'categoria', c.nome, 'kg', round(t.kg, 1),
      'scadenza_piu_vicina', t.scadenza_piu_vicina, 'motivo', t.motivo,
      'messaggio_volontari', t.messaggio_volontari,
      'volontari_suggeriti', coalesce((
          SELECT json_agg(json_build_object(
                   'volontario_id', v.vid,
                   'nome', CASE WHEN p.ruolo = 'coordinatore' THEN ar.nome_o_ragione_sociale END)
                 ORDER BY v.ord)
          FROM unnest(t.volontari_suggeriti) WITH ORDINALITY AS v(vid, ord)
          LEFT JOIN riservato.anagrafica_riservata ar ON ar.soggetto_id = v.vid), '[]'::json),
      'stato', t.stato) ORDER BY t.scadenza_piu_vicina NULLS LAST, t.kg DESC)
    FROM solidale.trasferimento_suggerito t
    JOIN solidale.categoria_prodotto c ON c.id = t.categoria_id
    JOIN par p ON t.settimana = p.sett
    WHERE p.punto IS NULL OR p.punto IN (t.da_punto_id, t.a_punto_id)), '[]'::json)
) AS risposta;

-- ---------------------------------------------------------------------
-- 4. GET /api/turni?punto=&settimana=
-- ---------------------------------------------------------------------
WITH par AS (
  SELECT nullif(:'punto', '') AS punto,
         coalesce(nullif(:'settimana', '')::date,
                  (SELECT max(data_rilevazione) FROM solidale.giacenza)) AS sett,
         :'ruolo'::text AS ruolo,
         (SELECT valore FROM solidale.parametro WHERE chiave = 'soglia_rischio_alto')  AS s_alto,
         (SELECT valore FROM solidale.parametro WHERE chiave = 'soglia_rischio_medio') AS s_medio
), ass AS (
  SELECT t.id AS turno_id, a.id, a.volontario_id, a.stato, a.sostituto_id, a.ore_pianificate,
         r.probabilita,
         CASE WHEN r.probabilita IS NULL THEN NULL
              WHEN r.probabilita >= p.s_alto  THEN 'alto'
              WHEN r.probabilita >= p.s_medio THEN 'medio'
              ELSE 'basso' END AS rischio,
         CASE WHEN p.ruolo = 'coordinatore' THEN ar.nome_o_ragione_sociale END AS nome
  FROM solidale.turno t
  JOIN par p ON t.data BETWEEN p.sett AND p.sett + 6 AND (p.punto IS NULL OR t.punto_id = p.punto)
  JOIN solidale.assegnazione a ON a.turno_id = t.id
  LEFT JOIN solidale.rischio_assegnazione r ON r.assegnazione_id = a.id
  LEFT JOIN riservato.anagrafica_riservata ar ON ar.soggetto_id = a.volontario_id
), per_turno AS (
  SELECT turno_id,
         CASE max(CASE rischio WHEN 'alto' THEN 3 WHEN 'medio' THEN 2 WHEN 'basso' THEN 1 END)
              WHEN 3 THEN 'alto' WHEN 2 THEN 'medio' WHEN 1 THEN 'basso' END AS rischio_massimo,
         json_agg(json_build_object(
           'assegnazione_id', id, 'volontario_id', volontario_id, 'nome', nome, 'stato', stato,
           'sostituto_id', sostituto_id, 'ore_pianificate', ore_pianificate,
           'probabilita_scoperto', probabilita, 'rischio', rischio) ORDER BY id) AS assegnazioni
  FROM ass GROUP BY turno_id
)
SELECT json_build_object(
  'settimana', (SELECT sett FROM par),
  'riepilogo', json_build_object(
      'turni',         (SELECT count(*) FROM per_turno),
      'assegnazioni',  (SELECT count(*) FROM ass),
      'rischio_alto',  (SELECT count(*) FROM ass WHERE rischio = 'alto'),
      'rischio_medio', (SELECT count(*) FROM ass WHERE rischio = 'medio')),
  'turni', coalesce((SELECT json_agg(json_build_object(
      'turno_id', t.id, 'punto_id', t.punto_id, 'data', t.data, 'fascia', t.fascia,
      'ora_inizio', to_char(t.ora_inizio, 'HH24:MI'), 'ora_fine', to_char(t.ora_fine, 'HH24:MI'),
      'rischio_massimo', pt.rischio_massimo, 'assegnazioni', pt.assegnazioni)
      ORDER BY t.data, t.fascia, t.punto_id)
    FROM per_turno pt JOIN solidale.turno t ON t.id = pt.turno_id), '[]'::json)
) AS risposta;

-- ---------------------------------------------------------------------
-- 5. GET /api/assegnazioni/{assegnazione_id}/sostituti
-- ---------------------------------------------------------------------
SELECT json_build_object(
  'assegnazione_id', a.id,
  'volontario_id', a.volontario_id,
  'turno', json_build_object('turno_id', t.id, 'punto_id', t.punto_id, 'data', t.data, 'fascia', t.fascia,
                             'ora_inizio', to_char(t.ora_inizio, 'HH24:MI'), 'ora_fine', to_char(t.ora_fine, 'HH24:MI')),
  'sostituti', coalesce((
      SELECT json_agg(json_build_object(
               'posizione', s.posizione, 'volontario_id', s.volontario_id,
               'nome', CASE WHEN :'ruolo' = 'coordinatore' THEN ar.nome_o_ragione_sociale END,
               'punteggio', s.punteggio, 'motivi', to_json(s.motivi)) ORDER BY s.posizione)
      FROM solidale.sostituto_suggerito s
      LEFT JOIN riservato.anagrafica_riservata ar ON ar.soggetto_id = s.volontario_id
      WHERE s.assegnazione_id = a.id), '[]'::json)
) AS risposta
FROM solidale.assegnazione a
JOIN solidale.turno t ON t.id = a.turno_id
WHERE a.id = :'assegnazione_id';
-- Nessuna riga → il backend restituisce 404.

-- ---------------------------------------------------------------------
-- 6. POST /api/assegnazioni/{assegnazione_id}/sostituzione   body: {"sostituto_id": "V024"}
--    Prima il backend controlla: assegnazione esistente (404), non già sostituita (409),
--    sostituto attivo, diverso dal titolare e non già nel turno (422).
-- ---------------------------------------------------------------------
UPDATE solidale.assegnazione
   SET stato = 'sostituito', sostituto_id = :'sostituto_id'
 WHERE id = :'assegnazione_id' AND stato <> 'sostituito'
RETURNING json_build_object('assegnazione_id', id, 'volontario_id', volontario_id, 'stato', stato,
                            'sostituto_id', sostituto_id, 'ore_pianificate', ore_pianificate) AS risposta;
-- Il backend aggiunge nome, probabilita_scoperto e rischio come in GET /api/turni.

-- ---------------------------------------------------------------------
-- 7. GET /api/impatto?da=AAAA-MM&a=AAAA-MM&punto=
-- ---------------------------------------------------------------------
WITH par AS (
  SELECT to_date(coalesce(nullif(:'da', ''), '2025-09'), 'YYYY-MM') AS da,
         coalesce(to_date(nullif(:'a', ''), 'YYYY-MM'),
                  (SELECT max(mese) FROM solidale.v_impatto_mensile)) AS a,
         nullif(:'punto', '') AS punto,
         (SELECT valore FROM solidale.parametro WHERE chiave = 'kg_per_pasto') AS kg_per_pasto
), mesi AS (
  SELECT generate_series(da, a, interval '1 month')::date AS mese FROM par
), imp AS (
  SELECT v.mese, sum(v.kg_recuperati) AS kg_recuperati, sum(v.kg_distribuiti) AS kg_distribuiti,
         sum(v.kg_scartati) AS kg_scartati, sum(v.pasti_equivalenti) AS pasti
  FROM solidale.v_impatto_mensile v, par p
  WHERE p.punto IS NULL OR v.punto_id = p.punto
  GROUP BY v.mese
), tur AS (
  SELECT date_trunc('month', t.data)::date AS mese,
         count(*) AS assegnazioni,
         count(*) FILTER (WHERE a.stato = 'scoperto') AS scoperte,
         coalesce(sum(a.ore_effettive), 0) AS ore
  FROM solidale.assegnazione a JOIN solidale.turno t ON t.id = a.turno_id, par p
  WHERE p.punto IS NULL OR t.punto_id = p.punto
  GROUP BY 1
), serie AS (
  SELECT m.mese,
         coalesce(i.kg_recuperati, 0) AS kg_recuperati, coalesce(i.kg_distribuiti, 0) AS kg_distribuiti,
         coalesce(i.kg_scartati, 0) AS kg_scartati, coalesce(i.pasti, 0) AS pasti,
         coalesce(tu.ore, 0) AS ore, coalesce(tu.assegnazioni, 0) AS assegnazioni, coalesce(tu.scoperte, 0) AS scoperte
  FROM mesi m LEFT JOIN imp i USING (mese) LEFT JOIN tur tu USING (mese)
), ben AS (
  SELECT count(*) AS nuclei, coalesce(sum(n_componenti), 0) AS persone, coalesce(sum(n_minori), 0) AS minori
  FROM solidale.beneficiario b, par p
  WHERE b.stato_scheda = 'attiva' AND (p.punto IS NULL OR b.punto_riferimento_id = p.punto)
)
SELECT json_build_object(
  'periodo', (SELECT json_build_object('da', to_char(da, 'YYYY-MM'), 'a', to_char(a, 'YYYY-MM')) FROM par),
  'punto_id', (SELECT punto FROM par),
  'totali', (SELECT json_build_object(
      'kg_recuperati', round(sum(kg_recuperati), 1),
      'kg_distribuiti_stimati', round(sum(kg_distribuiti), 1),
      'kg_scartati', round(sum(kg_scartati), 1),
      'tasso_spreco', round(sum(kg_scartati) / nullif(sum(kg_recuperati), 0), 3),
      'pasti_equivalenti', sum(pasti)::int,
      'ore_volontariato', round(sum(ore), 1),
      'tasso_scopertura_turni', round(sum(scoperte)::numeric / nullif(sum(assegnazioni), 0), 3),
      'nuclei_attivi', (SELECT nuclei FROM ben),
      'persone_raggiunte', (SELECT persone FROM ben),
      'minori_raggiunti', (SELECT minori FROM ben)) FROM serie),
  'mensile', (SELECT json_agg(json_build_object(
      'mese', to_char(mese, 'YYYY-MM'),
      'kg_recuperati', round(kg_recuperati, 1), 'kg_distribuiti_stimati', round(kg_distribuiti, 1),
      'kg_scartati', round(kg_scartati, 1), 'pasti_equivalenti', pasti::int,
      'ore_volontariato', round(ore, 1),
      'tasso_scopertura_turni', round(scoperte::numeric / nullif(assegnazioni, 0), 3)) ORDER BY mese) FROM serie),
  'ipotesi', json_build_object(
      'kg_per_pasto', (SELECT kg_per_pasto FROM par),
      'note', json_build_array(
        'Le distribuzioni sono stimate con il bilancio di magazzino (giacenza iniziale + donato − scartato − giacenza finale).',
        'Gli scarti sono una stima minima: alcuni punti li registrano meno degli altri.',
        'I pezzi sono convertiti in kg con un peso medio per categoria.'))
) AS risposta;

-- ---------------------------------------------------------------------
-- 8. GET /api/messaggi?categoria=&fonte=&punto=&da=&a=&pagina=&per_pagina=
-- ---------------------------------------------------------------------
WITH par AS (
  SELECT nullif(:'categoria', '') AS categoria, nullif(:'fonte', '') AS fonte, nullif(:'punto', '') AS punto,
         nullif(:'da', '')::date AS da, nullif(:'a', '')::date AS a,
         coalesce(nullif(:'pagina', '')::int, 1) AS pagina,
         coalesce(nullif(:'per_pagina', '')::int, 20) AS per_pagina,
         :'ruolo'::text AS ruolo
), filtro AS (
  SELECT m.* FROM solidale.messaggio m, par p
  WHERE (p.fonte IS NULL OR m.fonte::text = p.fonte)
    AND (p.punto IS NULL OR m.punto_id = p.punto)
    AND (p.da IS NULL OR m.ricevuto_il >= p.da)
    AND (p.a  IS NULL OR m.ricevuto_il <  p.a + 1)
    AND (p.ruolo = 'coordinatore' OR m.fonte <> 'nota_operatore')
), voti AS (
  -- recensioni e feedback nel periodo e nel punto scelti (ignora categoria, fonte e pagina)
  SELECT m.* FROM solidale.messaggio m, par p
  WHERE m.fonte::text IN ('recensione', 'feedback_app')
    AND (p.da IS NULL OR m.ricevuto_il >= p.da)
    AND (p.a  IS NULL OR m.ricevuto_il <  p.a + 1)
    AND (p.punto IS NULL OR m.punto_id = p.punto)
), con_categoria AS (
  SELECT f.* FROM filtro f, par p WHERE p.categoria IS NULL OR f.categoria_predetta = p.categoria
)
SELECT json_build_object(
  'totale', (SELECT count(*) FROM con_categoria),
  'pagina', (SELECT pagina FROM par),
  'per_pagina', (SELECT per_pagina FROM par),
  'conteggi_per_categoria', coalesce((SELECT json_agg(json_build_object('categoria', categoria, 'n', n) ORDER BY n DESC)
      FROM (SELECT categoria_predetta AS categoria, count(*) AS n FROM filtro
            WHERE categoria_predetta IS NOT NULL GROUP BY 1) x), '[]'::json),   -- i non ancora classificati (es. feedback appena arrivati) non entrano nel grafico
  'soddisfazione', json_build_object(
      'voto_medio', (SELECT round(avg(voto), 1) FROM voti),
      'n_voti', (SELECT count(voto) FROM voti),
      'sentiment', (SELECT json_build_object(
          'negativo', count(*) FILTER (WHERE sentiment = 'negativo'),
          'neutro',   count(*) FILTER (WHERE sentiment = 'neutro'),
          'positivo', count(*) FILTER (WHERE sentiment = 'positivo')) FROM voti),
      'mensile', coalesce((SELECT json_agg(json_build_object('mese', mese, 'voto_medio', voto_medio, 'n_voti', n_voti) ORDER BY mese)
          FROM (SELECT to_char(ricevuto_il, 'YYYY-MM') AS mese, round(avg(voto), 1) AS voto_medio, count(voto) AS n_voti
                FROM voti GROUP BY 1) x), '[]'::json)),
  'messaggi', coalesce((SELECT json_agg(json_build_object(
      'id', id, 'fonte', fonte, 'ricevuto_il', ricevuto_il, 'autore_ruolo', autore_ruolo, 'oggetto', oggetto,
      'punto_id', punto_id, 'voto', voto,
      'testo_anonimizzato', testo_anonimizzato, 'categoria_predetta', categoria_predetta,
      'confidenza', confidenza, 'sentiment', sentiment, 'sentiment_punteggio', sentiment_punteggio,
      'entita_estratte', entita_estratte) ORDER BY ricevuto_il DESC)
    FROM (SELECT c.* FROM con_categoria c, par p
          ORDER BY c.ricevuto_il DESC LIMIT (SELECT per_pagina FROM par)
          OFFSET ((SELECT pagina FROM par) - 1) * (SELECT per_pagina FROM par)) pag), '[]'::json)
) AS risposta;
-- conteggi_per_categoria ignora il filtro categoria, così il grafico mostra sempre tutte le categorie.

-- ---------------------------------------------------------------------
-- 9. POST /api/donazioni   (in una transazione; esempio con due righe)
-- ---------------------------------------------------------------------
BEGIN;
WITH nuova AS (
  INSERT INTO solidale.donazione (data, donatore_id, punto_id, canale, stato_corrente)
  VALUES ('2026-11-19', 'D012', 'PR03', 'app', 'offerta')
  RETURNING id
), righe_in (categoria_id, prodotto, quantita, unita) AS (
  VALUES (11, 'Yogurt bianco', 40.0, 'pz'), (9, 'Insalata', 6.5, 'kg')
), righe AS (
  INSERT INTO solidale.donazione_riga (donazione_id, categoria_id, prodotto_originale, quantita, unita, kg, kg_stimato)
  SELECT n.id, r.categoria_id, r.prodotto, r.quantita, r.unita::solidale.unita_misura,
         CASE WHEN r.unita = 'kg' THEN r.quantita ELSE round(r.quantita * c.peso_medio_pz_kg, 2) END,
         r.unita = 'pz'
  FROM righe_in r CROSS JOIN nuova n JOIN solidale.categoria_prodotto c ON c.id = r.categoria_id
  RETURNING *
), storico AS (
  INSERT INTO solidale.stato_donazione (donazione_id, stato, nota)
  SELECT id, 'offerta', 'Ritiro giovedì pomeriggio' FROM nuova
)
SELECT json_build_object(
  'id', n.id, 'data', DATE '2026-11-19', 'donatore_id', 'D012', 'punto_id', 'PR03',
  'canale', 'app', 'stato_corrente', 'offerta',
  'kg_totali', (SELECT sum(kg) FROM righe),
  'righe', (SELECT json_agg(json_build_object(
      'categoria_id', r.categoria_id, 'categoria', c.nome, 'prodotto', r.prodotto_originale,
      'quantita', r.quantita, 'unita', r.unita, 'kg', r.kg, 'kg_stimato', r.kg_stimato) ORDER BY r.id)
    FROM righe r JOIN solidale.categoria_prodotto c ON c.id = r.categoria_id)
) AS risposta
FROM nuova n;
COMMIT;
-- Se una categoria ha unità pz ma peso_medio_pz_kg nullo, il backend risponde 422.

-- ---------------------------------------------------------------------
-- 10. POST /api/feedback   body: {"ruolo_autore":"beneficiario","punto_id":"PR03","voto":4,"commento":"..."}
--     Prima di salvare, il backend toglie dal commento telefoni, email e codici fiscali
--     (stesse regex dell'anonimizzazione). Il lunedì la pipeline toglie i nomi e calcola categoria e sentiment.
-- ---------------------------------------------------------------------
INSERT INTO solidale.messaggio (fonte, ricevuto_il, autore_ruolo, punto_id, voto, testo_anonimizzato)
VALUES ('feedback_app', now(), :'ruolo_autore', nullif(:'punto_feedback', ''), :'voto'::smallint, coalesce(:'commento_anonimizzato', ''))
RETURNING json_build_object('id', id, 'ricevuto_il', ricevuto_il) AS risposta;

-- ---------------------------------------------------------------------
-- 11. POST /api/caricamenti   (multipart: tipo, file)
--     Il backend salva prima il file nello storage di staging (es. Supabase Storage, cartella staging/),
--     poi registra il caricamento. La pipeline lo elabora e aggiorna la riga.
-- ---------------------------------------------------------------------
INSERT INTO solidale.caricamento (tipo, nome_file, percorso_file, caricato_da)
VALUES (:'tipo_caricamento', :'nome_file', :'percorso_file', nullif(:'utente_id', '')::bigint)
RETURNING json_build_object('id', id, 'tipo', tipo, 'nome_file', nome_file, 'caricato_il', caricato_il, 'stato', stato,
       'elaborato_il', elaborato_il, 'righe_lette', righe_lette, 'righe_caricate', righe_caricate,
       'righe_scartate', righe_scartate, 'errori', coalesce(errori, '[]'::jsonb)) AS risposta;

-- ---------------------------------------------------------------------
-- 12. GET /api/caricamenti?limite=10
-- ---------------------------------------------------------------------
SELECT json_build_object(
  'ultimo_aggiornamento', (SELECT max(elaborato_il) FROM solidale.caricamento
                           WHERE stato IN ('completato', 'completato_con_scarti')),
  'caricamenti', coalesce((SELECT json_agg(json_build_object(
       'id', id, 'tipo', tipo, 'nome_file', nome_file, 'caricato_il', caricato_il, 'stato', stato,
       'elaborato_il', elaborato_il, 'righe_lette', righe_lette, 'righe_caricate', righe_caricate,
       'righe_scartate', righe_scartate, 'errori', coalesce(errori, '[]'::jsonb)) ORDER BY caricato_il DESC)
     FROM (SELECT * FROM solidale.caricamento ORDER BY caricato_il DESC
           LIMIT coalesce(nullif(:'limite', '')::int, 10)) c), '[]'::json)
) AS risposta;
