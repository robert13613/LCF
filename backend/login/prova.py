import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from login import esegui_login

#  dati dell'utente per il test 
# Email: test@buby.it
# Ruolo: coordinatore
# Soggetto ID: TEST01

def test_login_locale():
    print("=== TEST LOGIN BUBY SOLIDALE ===")
    print("(Scrivi 'esci' al posto dell'email per chiudere)\n")

    while True:
        email = input("Email: ").strip()
        if email.lower() == "esci":
            print("Test terminato.")
            break

        password = input("Password: ").strip()

        # Passiamo i dati al modulo di login e attendiamo la risposta
        risposta = esegui_login(email, password)

        if risposta["successo"]:
            print(f"\n✅ {risposta['messaggio']}")
            print(f"   • Ruolo utente: {risposta['ruolo']}")
            print(f"   • ID Utente:    {risposta['id']}")
            print(f"   • Soggetto ID:  {risposta['soggetto_id']}\n")
        else:
            print(f"\n❌ Accesso negato: {risposta['messaggio']}\n")


if __name__ == "__main__":
    test_login_locale()