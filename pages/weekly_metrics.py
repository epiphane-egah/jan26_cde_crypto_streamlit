"""
Calcul des métriques de performance à partir des ordres enregistrés.

Le point clé pour rester compatible avec une future migration SQL :
tout le reste du fichier (et le dashboard Streamlit) ne connaît que la
fonction load_trades(), qui renvoie un DataFrame avec des colonnes fixes.
Le jour où tu passes en base, tu ne changes QUE l'intérieur de
load_trades() (un SELECT au lieu d'une lecture de fichier) — aucune autre
fonction ni le dashboard n'ont besoin d'être modifiés.
"""

import json
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# Couche d'accès aux données — SEULE partie à changer en cas de migration SQL
# --------------------------------------------------------------------------

def load_trades(path="transactions.jsonl"):
    """
    Charge les ordres depuis le fichier JSON Lines et renvoie un DataFrame
    avec un schéma stable, qui correspond terme à terme aux colonnes
    qu'aurait une table SQL FAIT_SIGNAL_TRADING.

    Migration future vers SQL : remplacer le corps de cette fonction par
    quelque chose comme
        pd.read_sql("SELECT * FROM FAIT_SIGNAL_TRADING", conn)
    en gardant exactement les mêmes noms de colonnes en sortie.
    """
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=[
            "order_id", "symbol", "side", "transact_time", "price",
            "executed_qty", "quote_qty", "commission_total",
            "commission_asset", "id_ordre_ouverture",
        ])

    lignes = []
    with open(path) as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            o = json.loads(ligne)
            lignes.append({
                "order_id": o["orderId"],
                "symbol": o["symbol"],
                "side": o["side"],
                "transact_time": o["transactTime"],
                "price": o["price"],
                "executed_qty": o["executedQty"],
                "quote_qty": o["cummulativeQuoteQty"],
                "commission_total": o.get("commission_total", 0.0),
                "commission_asset": o.get("commission_asset"),
                "id_ordre_ouverture": o.get("id_ordre_ouverture"),
            })

    df = pd.DataFrame(lignes)
    if not df.empty:
        df["transact_time"] = pd.to_datetime(df["transact_time"])
        df = df.sort_values("transact_time").reset_index(drop=True)
    return df


# --------------------------------------------------------------------------
# Appariement BUY / SELL et calcul du P&L par trade
# --------------------------------------------------------------------------

def compute_trade_pnl(df):
    """
    Construit une ligne par trade FERMÉ (un couple BUY -> SELL), avec le
    P&L net (frais déduits). S'appuie sur id_ordre_ouverture (Option A) :
    chaque SELL référence directement son BUY, pas besoin de reconstituer
    l'appariement par déduction.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "date_ouverture", "date_fermeture", "prix_achat", "prix_vente",
            "quantite", "pnl_brut", "pnl_net", "frais_totaux", "duree_heures",
        ])

    achats = df[df["side"] == "BUY"].set_index("order_id")
    ventes = df[df["side"] == "SELL"]

    trades = []
    for _, vente in ventes.iterrows():
        id_achat = vente["id_ordre_ouverture"]
        if id_achat is None or id_achat not in achats.index:
            continue  # SELL orphelin (ex: position ouverte avant le début du log)

        achat = achats.loc[id_achat]

        pnl_brut = (vente["price"] - achat["price"]) * vente["executed_qty"]
        frais_totaux = achat["commission_total"] + vente["commission_total"]
        # Approximation : les frais BUY sont en crypto, les frais SELL en
        # USDT — ici on additionne les deux en valeur USDT approximative
        # en supposant que le frais BUY (en crypto) vaut ~ prix d'achat.
        # Pour une précision comptable totale, il faudrait convertir le
        # frais BUY (en crypto) au prix du moment via commission_asset.
        frais_usdt_estimes = (
            vente["commission_total"]
            + achat["commission_total"] * achat["price"]
        )
        pnl_net = pnl_brut - frais_usdt_estimes

        duree_heures = (
            vente["transact_time"] - achat["transact_time"]
        ).total_seconds() / 3600

        trades.append({
            "date_ouverture": achat["transact_time"],
            "date_fermeture": vente["transact_time"],
            "prix_achat": achat["price"],
            "prix_vente": vente["price"],
            "quantite": vente["executed_qty"],
            "pnl_brut": pnl_brut,
            "pnl_net": pnl_net,
            "frais_totaux": frais_usdt_estimes,
            "duree_heures": duree_heures,
        })

    return pd.DataFrame(trades)


# --------------------------------------------------------------------------
# Métriques agrégées
# --------------------------------------------------------------------------

def compute_equity_curve(trades_df, solde_initial):
    """Courbe d'équité cumulée à partir du P&L net de chaque trade fermé."""
    if trades_df.empty:
        return pd.DataFrame(columns=["date", "equity"])

    courbe = trades_df[["date_fermeture", "pnl_net"]].copy()
    courbe["equity"] = solde_initial + courbe["pnl_net"].cumsum()
    courbe = courbe.rename(columns={"date_fermeture": "date"})
    return courbe[["date", "equity"]]


def compute_max_drawdown(equity_curve):
    if equity_curve.empty:
        return 0.0
    sommet_courant = equity_curve["equity"].cummax()
    drawdown = (equity_curve["equity"] - sommet_courant) / sommet_courant
    return float(drawdown.min() * 100)  # en %


def compute_metrics(trades_df, solde_initial):
    """Calcule le paquet complet de métriques pour le dashboard."""
    if trades_df.empty:
        return {
            "nb_trades": 0, "win_rate": 0.0, "profit_factor": None,
            "pnl_total": 0.0, "rendement_pct": 0.0, "max_drawdown_pct": 0.0,
            "frais_totaux": 0.0, "duree_moyenne_heures": 0.0,
        }

    gains = trades_df[trades_df["pnl_net"] > 0]["pnl_net"]
    pertes = trades_df[trades_df["pnl_net"] < 0]["pnl_net"]

    pnl_total = trades_df["pnl_net"].sum()
    equity_curve = compute_equity_curve(trades_df, solde_initial)

    return {
        "nb_trades": len(trades_df),
        "win_rate": round(len(gains) / len(trades_df) * 100, 1),
        "profit_factor": (
            round(gains.sum() / abs(pertes.sum()), 2) if len(pertes) > 0 and pertes.sum() != 0 else None
        ),
        "pnl_total": round(pnl_total, 2),
        "rendement_pct": round(pnl_total / solde_initial * 100, 2),
        "max_drawdown_pct": round(compute_max_drawdown(equity_curve), 2),
        "frais_totaux": round(trades_df["frais_totaux"].sum(), 2),
        "duree_moyenne_heures": round(trades_df["duree_heures"].mean(), 1),
    }


def load_weekly_report(path="transactions.jsonl", solde_initial=1000, jours=7):
    """
    Point d'entrée unique pour le dashboard : charge, filtre sur la
    dernière période, et renvoie (metrics, trades_df, equity_curve).
    """
    df = load_trades(path)
    trades_df = compute_trade_pnl(df)

    if not trades_df.empty and jours is not None:
        limite = trades_df["date_fermeture"].max() - pd.Timedelta(days=jours)
        trades_df = trades_df[trades_df["date_fermeture"] >= limite]

    metrics = compute_metrics(trades_df, solde_initial)
    equity_curve = compute_equity_curve(trades_df, solde_initial)

    return metrics, trades_df, equity_curve


if __name__ == "__main__":
    metrics, trades_df, equity_curve = load_weekly_report()
    print(json.dumps(metrics, indent=2))
    print(trades_df)
