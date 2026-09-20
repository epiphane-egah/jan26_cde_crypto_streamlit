import datetime
import time
import itertools
import re
import pandas as pd
from google.cloud import storage
from utils import get_data_binance


# Configuration Cloud Storage (Authentification automatique sur GCP)
storage_client = storage.Client()
BUCKET_NAME = "crypto-data-candle"

symbols_list = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
intervals_list = ["1h", "1d"]
symbols_intervals_list = list(itertools.product(symbols_list, intervals_list))


def recuperer_dernier_timestamp_global():
    """
    Scanne le bucket pour trouver le fichier unique le plus récent
    et extrait son timestamp de fin (qui devient le start_time de cette semaine).
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    
    # On liste tous les fichiers globaux générés par le script
    blobs = bucket.list_blobs(prefix="crypto_")
    
    timestamps_trouves = []
    pattern = r"_to_(\d+)\.parquet$"
    
    for blob in blobs:
        match = re.search(pattern, blob.name)
        if match:
            timestamps_trouves.append(int(match.group(1)))
            
    # Si un fichier existe, on reprend là où le dernier s'est arrêté
    if timestamps_trouves:
        return max(timestamps_trouves)
        
    # Si le bucket est vide (première exécution historique), on démarre à 0
    return 0


def executer_tache_hebdomadaire():
    # 1. Définition de la date d'exécution et conversion immédiate en millisecondes (end_time)
    date_maintenant = datetime.datetime.now()
    end_time = int(date_maintenant.timestamp() * 1000)
    
    # 2. Récupération du point de départ commun basé sur le dernier fichier du bucket
    start_time = recuperer_dernier_timestamp_global()
    print(f"Début de l'extraction globale | Start_time : {start_time} -> End_time : {end_time}")

    tous_les_dataframes = []

    # 3. Boucle de collecte des données
    for symbole, intervalle in symbols_intervals_list:
        try:
            donnees_crypto = get_data_binance(symbole, intervalle, start_time=start_time, end_time=end_time)
        except Exception as e:
            print(f"🚨 ALERTE ERREUR : Impossible de contacter Binance pour {symbole} {intervalle} : {e}")
            continue
        
        if not donnees_crypto:
            print(f"⚠️ ALERTE DONNÉES VIDES : Aucune nouvelle donnée pour {symbole} ({intervalle}).")
            continue 

        # Structuration des données récupérées
        df_temp = pd.DataFrame(donnees_crypto)
        df_temp['symbole'] = symbole
        df_temp['intervalle'] = intervalle
        
        tous_les_dataframes.append(df_temp)
        
        # Pause pour respecter les limites de l'API Binance
        time.sleep(30)
        
    # 4. Fusion et écriture unique dans le bucket
    if tous_les_dataframes:
        df_final = pd.concat(tous_les_dataframes, ignore_index=True)
        
        nom_fichier = f"crypto_{start_time}_to_{end_time}.parquet"
        chemin_gcs = f"gs://{BUCKET_NAME}/{nom_fichier}"
        
        # supprimer les doublons
        df_final.drop_duplicates()

        df_final.to_parquet(chemin_gcs, index=False, engine='pyarrow')
        
        print(f"✅ Succès : Fichier unique sauvegardé : {nom_fichier}")
        return "Extraction et sauvegarde réussies", 200
    else:
        print("🚨 ALERTE CRITIQUE : Aucune donnée n'a pu être collectée ce coup-ci.")
        return "Aucune donnée récupérée", 204


if __name__ == "__main__":
    print(recuperer_dernier_timestamp_global())
    # executer_tache_hebdomadaire()