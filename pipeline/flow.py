from prefect import flow, task, get_run_logger


@task(name="Estrai dati")
def estrai():
    logger = get_run_logger()
    logger.info("Fase 1: ESTRAI - esecuzione passo simulato")
    return {"dati": []}


@task(name="Pulisci dati")
def pulisci(dati):
    logger = get_run_logger()
    logger.info("Fase 2: PULISCI - esecuzione passo simulato")
    return dati


@task(name="Valida dati")
def valida(dati):
    logger = get_run_logger()
    logger.info("Fase 3: VALIDA - esecuzione passo simulato")
    return dati


@task(name="Carica dati")
def carica(dati):
    logger = get_run_logger()
    logger.info("Fase 4: CARICA - esecuzione passo simulato (in attesa DB W1-14)")
    return True


@flow(name="Pipeline ETL Locale", log_prints=True)
def etl_flow():
    logger = get_run_logger()
    logger.info("Avvio del flow principale...")

    dati_estratti = estrai()
    dati_puliti = pulisci(dati_estratti)
    dati_validati = valida(dati_puliti)
    carica(dati_validati)

    logger.info("Flow terminato con successo!")


if __name__ == "__main__":
    etl_flow()