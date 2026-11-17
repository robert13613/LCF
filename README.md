# Buby Solidale

## Obiettivo
Buby Solidale è un'applicazione web sviluppata per ottimizzare la gestione della rete solidale di Buby Group. Il progetto unisce le competenze del team Data & AI (DAI) e del team Web Solutions Architecture (WSA) per raggiungere tre traguardi principali:
*   **Ridurre gli sprechi alimentari:** implementando logiche FEFO (First Expired, First Out) e modelli di previsione per redistribuire le eccedenze tra i punti di ritiro.
*   **Garantire la copertura dei turni:** identificando i turni a rischio scopertura e suggerendo i volontari più adatti per le sostituzioni.
*   **Misurare l'impatto sociale:** calcolando KPI chiari come pasti equivalenti distribuiti e kg di merce recuperata.

## Struttura del Repository
Il progetto segue un'architettura a servizi separati per facilitare lo sviluppo parallelo.

*   `/backend/` - Applicazione server e API (Python, FastAPI). Legge dal database PostgreSQL e rispetta il contratto API stabilito.
*   `/frontend/` - Interfaccia utente (Node.js/React/Vue). Contiene le schermate operative (Scadenze, Turni, Impatto, Messaggi).
*   `/pipeline/` - Script e job di data ingestion, pulizia dati, NLP e Machine Learning (Python, Prefect).
*   `/docs/` - Documentazione tecnica, contratto API e schema del database.

## Come Contribuire
1.  Crea un branch dal ramo `main` per la tua funzionalità (es. `feature/wsa-nuova-dashboard` o `feature/dai-modello-turni`).
2.  Assicurati che il codice rispetti il contratto API concordato.
3.  Apri una Pull Request descrivendo i cambiamenti effettuati.

⚠️ **REGOLA TASSATIVA SUI DATI PERSONALI (GDPR)** ⚠️
**È severamente vietato caricare dati reali, anagrafiche in chiaro, email o file forniti dal committente all'interno di questo repository.** 
*   Il codice deve operare esclusivamente su dati pseudonimizzati (schema `solidale`) o file di mock generati per lo sviluppo.
*   Qualsiasi file contenente nomi, telefoni, dati sulla salute o credenziali deve rimanere locale e non deve mai essere tracciato da Git.
