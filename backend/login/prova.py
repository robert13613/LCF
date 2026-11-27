from login import esegui_login

#  dati dell'utente per il test 
# 

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