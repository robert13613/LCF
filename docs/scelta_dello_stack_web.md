# Architettura e Scelta dello Stack Web – Buby Solidale

Per garantire rapidità di sviluppo, manutenibilità e massima compatibilità con il lavoro del team Data & AI, la struttura dell'applicazione web si basa sulle seguenti tecnologie:

## 1. Backend: Python + FastAPI (con SQLAlchemy)
* **Perché:** L'uso di Python crea un ecosistema unico e condiviso con il team Dati, permettendo di riutilizzare facilmente modelli, logiche e competenze. 
* **Vantaggi tecnici:** FastAPI garantisce prestazioni elevate, generazione automatica della documentazione interattiva (Swagger/OpenAPI) fondamentale per allineare i team sul contratto API, e validazione nativa dei dati tramite Pydantic. L'integrazione con SQLAlchemy permette di interagire in modo pulito, tipizzato e sicuro con i due schemi (`solidale` e `riservato`) del database PostgreSQL.

## 2. Frontend: React (con Vite)
* **Perché:** È uno standard consolidato e già noto al gruppo, riducendo a zero la curva di apprendimento iniziale.
* **Vantaggi tecnici:** L'architettura a componenti riutilizzabili facilita lo sviluppo parallelo delle diverse schermate operative (gestione scadenze FEFO, monitoraggio turni, dashboard impatto sociale e inbox messaggi). L'uso di Vite riduce drasticamente i tempi di build e semplifica la configurazione dell'ambiente di sviluppo.

## 3. Database e Pubblicazione (Hosting): Supabase + Render / Railway
* **Database (Supabase):** Per l'archiviazione dei dati è stato scelto Supabase (PostgreSQL gestito), che offre un piano gratuito affidabile per la fase di sviluppo, isolamento nativo tramite schemi per la conformità GDPR e gestione semplificata degli accessi.
* **Hosting (Render o Railway):** Per la pubblicazione online dell'applicativo si opta per Render (o Railway) in quanto consentono il deploy continuo (CI/CD) direttamente dal repository GitHub a costo zero o estremamente contenuto. Entrambe le piattaforme gestiscono nativamente sia servizi web Python (FastAPI) sia siti statici (React), evitando configurazioni complesse di infrastruttura server.