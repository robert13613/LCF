# Contratto API – bozza v0.1 (18/11/2026)

Il contratto tra team dati (DAI) e team web (WSA): quali richieste fa l'app, con quali parametri,
e quali campi riceve (nome, tipo, unità). Si congela dopo la SAL.

## Come leggerlo

- **Il modo più semplice**: scaricare `contratto_api.html` e aprirlo con doppio clic. Si apre nel browser,
  funziona anche senza internet, ha il menu a sinistra per schermata e gli esempi di risposta a destra.
- **Per chi lavora sul codice**: aprire https://editor.swagger.io, menu File → Import file → `openapi.yaml`.
- **Per commentare**: aprire una Issue su GitHub con titolo `Contratto: <richiesta>` (es. `Contratto: GET /api/turni`),
  oppure un commento sulla card W1-09 in Trello. Le modifiche al file le fa solo Alberto.

## File

| File | A cosa serve | Chi lo usa |
|---|---|---|
| `openapi.yaml` | Il contratto: 9 richieste, campi, tipi, unità ed esempi. **È il file che fa fede** | tutti |
| `contratto_api.html` | Versione leggibile generata da `openapi.yaml` (non si modifica a mano) | tutti |
| `query_contratto.sql` | Una query SQL per richiesta, che restituisce già il JSON del contratto | Mattia (backend) |

Lo schema del database a cui si riferisce il contratto è `docs/schema/buby_solidale_schema_v1.0.sql`.

## Le 9 richieste

| Schermata | Richiesta | Cosa restituisce |
|---|---|---|
| Tutte | `GET /api/anagrafiche` | punti, categorie, settimane disponibili |
| Scadenze | `GET /api/scadenze?punto=PR03&settimana=2026-10-26` | lista FEFO con urgenza e previsione della settimana dopo |
| Scadenze | `GET /api/trasferimenti?settimana=` | trasferimenti suggeriti e messaggio per i volontari (Salva-scadenze) |
| Turni | `GET /api/turni?punto=&settimana=` | turni con probabilità di restare scoperti |
| Turni | `GET /api/assegnazioni/T04425/sostituti` | classifica dei sostituti |
| Turni | `POST /api/assegnazioni/T04425/sostituzione` | registra il sostituto |
| Impatto | `GET /api/impatto?da=2025-09&a=2026-10&punto=` | totali e serie mensile, con le ipotesi |
| Messaggi | `GET /api/messaggi?categoria=&pagina=` | messaggi anonimizzati e classificati |
| Form donazione | `POST /api/donazioni` | crea una donazione con stato "offerta" |

## Come si usa nello sviluppo

- **Server di risposte finte** (frontend, card W2-12): `npx @stoplight/prism-cli mock openapi.yaml`.
  Le richieste a `http://127.0.0.1:4010/api/...` rispondono con gli esempi del contratto. I numeri degli esempi sono illustrativi.
- **Backend** (FastAPI): ogni richiesta esegue la sua query di `query_contratto.sql` con i parametri e restituisce il JSON.
- **Rigenerare la versione leggibile** dopo una modifica: `npx @redocly/cli build-docs openapi.yaml -o contratto_api.html`.

## Verifiche fatte

- `openapi.yaml` è una specifica OpenAPI 3.0 valida.
- Schema v1.0 caricato su PostgreSQL 16 con dati di prova: tutte le query girano e ogni risposta rispetta il contratto,
  anche con ruolo non coordinatore (nomi nascosti, note degli operatori escluse).
- Prism parte dal file e risponde con gli esempi; rifiuta le richieste senza i parametri obbligatori.

## Regole

Dopo la SAL il contratto si congela (tag `v1.0` nel repository). Da lì nomi, tipi e unità dei campi
non cambiano senza l'accordo di Alberto e Mattia.
