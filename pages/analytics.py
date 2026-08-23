"""
Dashboard Streamlit — suivi hebdomadaire de la performance de la stratégie.

Lancer avec :
    streamlit run dashboard.py

N'accède jamais directement au fichier JSON ou à une base : passe toujours
par weekly_metrics.load_weekly_report(). C'est ce qui permet de migrer
vers SQL plus tard sans toucher à ce fichier.
"""

import streamlit as st

from weekly_metrics import load_weekly_report

st.set_page_config(page_title="Suivi stratégie crypto", layout="wide")

st.title("Suivi de la stratégie de trading")

with st.sidebar:
    fichier = st.text_input("Fichier de transactions", "transactions.jsonl")
    solde_initial = st.number_input("Solde initial (USDT)", value=1000.0, step=100.0)
    periode = st.selectbox(
        "Période",
        options=[7, 30, 90, None],
        format_func=lambda j: "Tout l'historique" if j is None else f"{j} derniers jours",
    )

metrics, trades_df, equity_curve = load_weekly_report(
    path=fichier, solde_initial=solde_initial, jours=periode
)

# --------------------------------------------------------------------------
# Cartes KPI
# --------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)
col1.metric("Rendement", f"{metrics['rendement_pct']}%")
col2.metric("Max drawdown", f"{metrics['max_drawdown_pct']}%")
col3.metric("Win rate", f"{metrics['win_rate']}%")
col4.metric(
    "Profit factor",
    f"{metrics['profit_factor']}" if metrics["profit_factor"] is not None else "—",
)

col5, col6, col7 = st.columns(3)
col5.metric("Nombre de trades", metrics["nb_trades"])
col6.metric("Frais totaux", f"{metrics['frais_totaux']} USDT")
col7.metric("Durée moyenne / trade", f"{metrics['duree_moyenne_heures']} h")

# --------------------------------------------------------------------------
# Courbe d'équité
# --------------------------------------------------------------------------

st.subheader("Évolution du solde")
if not equity_curve.empty:
    st.line_chart(equity_curve.set_index("date")["equity"])
else:
    st.info("Aucun trade fermé sur cette période.")

# --------------------------------------------------------------------------
# Détail des trades
# --------------------------------------------------------------------------

st.subheader("Détail des trades")
if not trades_df.empty:
    affichage = trades_df.copy()
    affichage["pnl_net"] = affichage["pnl_net"].round(2)
    affichage["duree_heures"] = affichage["duree_heures"].round(1)
    st.dataframe(
        affichage[[
            "date_ouverture", "date_fermeture", "prix_achat", "prix_vente",
            "quantite", "pnl_net", "duree_heures",
        ]],
        use_container_width=True,
    )
else:
    st.info("Aucun trade fermé à afficher.")