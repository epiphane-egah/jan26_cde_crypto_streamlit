import os
import time
import psycopg2
import streamlit as st
import dotenv
dotenv.load_dotenv()


# Configuration de la page pour un rendu propre
st.set_page_config(page_title="Crypto Bot Dashboard", page_icon="🪙", layout="centered")

# Titre principal et description
st.title("🪙 Configuration du Bot")
st.markdown("Remplissez le formulaire ci-dessous pour lancer votre stratégie de trading.")

# Utilisation d'un conteneur visuel pour regrouper le formulaire
with st.form("crypto_trading_form", clear_on_submit=False):
    st.subheader("👤 Informations Personnelles")
    
    # Alignement du nom et du prénom sur la même ligne
    col1, col2 = st.columns(2)
    with col1:
        prenom = st.text_input("Prénom", placeholder="Epiphane").capitalize()
    with col2:
        nom = st.text_input("Nom", placeholder="Egah").capitalize()
        
    st.markdown("---") # Ligne de séparation visuelle
    st.subheader("💰 Paramètres d'Investissement")
    
    # Champ de saisie pour le montant en USDT
    montant = st.number_input(
        "Montant à investir (USDT)", 
        min_value=10.0, 
        value=100.0, 
        step=50.0,
        help="Montant minimum requis : 10 USDT"
    )
    
    # Alignement du choix de la crypto et de l'intervalle
    col3, col4 = st.columns(2)
    with col3:
        crypto = st.selectbox(
            "Crypto-monnaie cible", 
            ["Bitcoin (BTC)", "Binance Coin (BNB)", "Ethereum (ETH)"]
        )
    with col4:
        intervalle = st.radio(
            "Intervalle de trading", 
            ["1 Heure", "1 Journée"],
            horizontal=False
        )
        
    # Bouton de soumission personnalisé par Streamlit
    st.markdown("<br>", unsafe_allow_html=True) # Espacement
    bouton_lancement = st.form_submit_button("🚀 Lancer l'application de trading")

# 📊 Traitement et affichage des résultats après clic
if bouton_lancement:
    # Validation basique des champs textuels
    if not nom.strip() or not prenom.strip():
        st.error("⚠️ Veuillez renseigner votre nom et votre prénom avant de lancer le bot.")
    else:
        while True:
            try:
                user = os.getenv("user")
                password = os.getenv("password")
                port = os.getenv("DB_PORT")
                dbname = os.getenv("dbname")
                host = os.getenv("host")
                conn = psycopg2.connect(f"postgresql://{user}:{password}@{host}:{port}/{dbname}")
                print("Connexion PostgreSQL réussie !")
                break
            except Exception as e:
                print(f"Connexion échouée : {e}")
                time.sleep(2)
        try:
            table = os.getenv("table_name")
            c = conn.cursor()
            c.execute(f"""INSERT INTO {table} (ClientOrderId, lastname, firstname, interval, type_crypto, usdt, solde_crypto)
                  VALUES ('bot_{prenom}_{nom}', '{nom}', '{prenom}', '{intervalle}', '{crypto}', {montant}, {0} )""")
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            st.info("### 📋 Le client existe déjà, voici ses informations à ce jour :")
            # requête SQL pour récupérer les données
            conn.rollback()
            c.execute("SELECT * FROM Clients")
            result = c.fetchone()
            prenom, nom, crypto, intervalle, solde_crypto, usdt = result[1], result[2], result[3], result[4], result[5], result[6]

            # Titre
            st.markdown("### 👤 Informations de votre compte")

            # Première ligne
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"""
                **👤 Prénom**  
                ### {prenom}
                """)

            with col2:
                st.markdown(f"""
                **👤 Nom**  
                ### {nom}
                """)

            with col3:
                st.markdown(f"""
                **🪙 Crypto**  
                ### {crypto}
                """)

            col4, col5, col6 = st.columns(3)
           
            with col4:
                st.markdown(f"""
                **⏱️ Intervalle**  
                ### {intervalle}
                """)

            with col5:
                st.markdown(f"""
                **💰 Solde crypto**  
                ### {solde_crypto}
                """)

            with col6:
                st.markdown(f"""
                **💵 Solde USDT**  
                ### {usdt} USDT
                """)

        else:
            # Message de succès global
            st.success("✨ Paramètres validés avec succès ! Initialisation du bot...")
            # Affichage visuel des données récoltées (prêtes à être envoyées à votre app)
            st.info("### 📋 Récapitulatif de la configuration")
        
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                prenom, nom = prenom.capitalize(), nom.capitalize()
                st.markdown(f"**Utilisateur :** {prenom} {nom}")
                st.markdown(f"**Capital alloué :** {montant:,.2f} USDT")
            with col_res2:
                st.markdown(f"**Actif sélectionné :** {crypto}")
                st.markdown(f"**Fréquence :** Chaque {intervalle.lower()}")
        finally:
            conn.close()
