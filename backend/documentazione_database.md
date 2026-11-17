# Documentazione Modulo Database

Il modulo `collegamentoDB.py` gestisce la connessione al database PostgreSQL utilizzando il pattern Object-Oriented. Sfrutta **SQLAlchemy** come ORM (Object-Relational Mapper) e carica in modo sicuro le credenziali tramite variabili d'ambiente.

## Prerequisiti

Prima di utilizzare questo modulo, è necessario installare le dipendenze nel proprio ambiente virtuale (`venv`):

```bash
pip install sqlalchemy psycopg2-binary python-dotenv
```

Inoltre, è **obbligatorio** creare un file `.env` nella stessa cartella del file `collegamentoDB.py` con le seguenti chiavi:

```env
DB_USER=postgres
DB_PASSWORD=tua_password_sicura
DB_HOST=localhost
DB_PORT=5432
DB_NAME=buby_solidale_db
```
*(Nota: Assicurati che il file `.env` sia sempre inserito nel `.gitignore` per evitare di esporre dati sensibili su GitHub).*

---

## Classe `DatabaseManager`

Questa classe incapsula tutta la logica di connessione e configurazione dell'ORM.

### `__init__(self)`
Il costruttore della classe. Al momento dell'inizializzazione, esegue in automatico questi passaggi:
1. Carica le variabili d'ambiente usando `load_dotenv()`.
2. Costruisce la stringa di connessione (URL) nel formato richiesto da PostgreSQL.
3. Inizializza l'`engine` di SQLAlchemy (il motore di comunicazione).
4. Crea `SessionLocal`, una "fabbrica" per generare le sessioni necessarie a interrogare il database.
5. Inizializza `Base`, la classe madre da cui erediteranno tutti i futuri modelli di dati (es. `Volontario`, `Donazione`).

### `testa_connessione(self)`
Metodo di utilità per verificare che le credenziali siano corrette e che il database sia raggiungibile.
* **Comportamento:** Tenta di aprire una connessione con l'engine. Stampa a schermo un messaggio di successo o l'errore specifico in caso di fallimento.
* **Utilizzo consigliato:** Utile in fase di setup o come script di health-check.

### `get_session(self)`
Il metodo più importante per le operazioni CRUD (Create, Read, Update, Delete).
* **Ritorna:** Un oggetto sessione generato da `SessionLocal()`.
* **Note:** La sessione restituita deve sempre essere chiusa manualmente (es. `sessione.close()`) al termine delle operazioni per liberare le risorse del database.

---

## Esempio di Utilizzo (in altri file)

Per utilizzare il database in altri file del progetto (es. nelle rotte API), non serve istanziare nuovamente la classe. Basta importare l'oggetto `db` già configurato:

```python
# Importa l'istanza globale
from collegamentoDB import db 

# Apri la sessione
sessione = db.get_session()

try:
    # Esegui le query...
    # esempio: risultati = sessione.query(ModelloX).all()
    pass
finally:
    # Chiudi sempre la sessione alla fine
    sessione.close()
```
