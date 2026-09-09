import datetime
from zoneinfo import ZoneInfo
import uuid
from decimal import Decimal, ROUND_DOWN
 
 
def simulate_order(df, symbol, side, client_order_id,
                   quantite=0.05, commission_rate=0.001):
    """
    Construit une réponse d'ordre simulée à partir de la dernière bougie
    d'un DataFrame OHLCV.
 
    Paramètres :
        df               : DataFrame contenant au moins les colonnes
                            'open_time' (timestamp en ms) et 'close'
        symbol            : ex. "BTCUSDT"
        side              : "BUY" ou "SELL" — déterminé par la logique
                            de la stratégie, pas codé en dur
        client_order_id   : identifiant de ta stratégie (ex. "bot_strategie2_001")
        quantite          : quantité tradée (en unité de la crypto, ex. BTC)
        commission_rate   : taux de frais simulé (0.1% par défaut, typique
                            d'un exchange sans réduction VIP)
 
    Retourne :
        dict au format compatible avec la structure attendue par
        FAIT_SIGNAL_TRADING.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side invalide : {side!r} (attendu BUY ou SELL)")
    df = df.copy()
    df = df.reset_index()
    derniere_bougie = df.iloc[-1]
   
 
    # Précision complète : indispensable pour une stratégie en 1H,
    # sinon deux ordres passés à des heures différentes le même jour
    # deviennent indistinguables dans DIM_TEMPS.
    transact_time = datetime.datetime.fromtimestamp(
        derniere_bougie['open_time'] / 1000
    ).strftime("%Y-%m-%d %H:%M:%S")
 
    prix_execution = Decimal(str(derniere_bougie["close"]))
    quantite_dec = Decimal(str(quantite))
 
    montant_total = (prix_execution * quantite_dec).quantize(
        Decimal("0.00000001"), rounding=ROUND_DOWN
    )
 
    # La commission est prélevée sur l'actif acheté en BUY,
    # sur la devise de cotation en SELL — comportement standard exchange.
    if side == "BUY":
        commission = (quantite_dec * Decimal(str(commission_rate))).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        commission_asset = symbol.replace("USDT", "")  # ex. BTC
    else:
        commission = (montant_total * Decimal(str(commission_rate))).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        commission_asset = "USDT"
 
    return {
        # str(uuid4()) plutôt que uuid4().int : un entier 128 bits dépasse
        # la capacité d'un BIGINT SQL (max ~9.2 × 10^18). Une chaîne texte
        # se stocke sans problème dans une colonne VARCHAR/id technique.
        "orderId": str(uuid.uuid4()),
        "symbol": symbol,
        "clientOrderId": client_order_id,
        "transactTime": transact_time,
        "price": float(prix_execution),
        "origQty": float(quantite_dec),
        "executedQty": float(quantite_dec),
        "cummulativeQuoteQty": float(montant_total),
        "status": "FILLED",
        "type": "MARKET",
        "side": side,
        "commission_total": float(commission),
        "commission_asset": commission_asset,
        "id_ordre_ouverture": None,
        "fills": [
            {
                "price": float(prix_execution),
                "qty": float(quantite_dec),
                "commission": float(commission),
                "commissionAsset": commission_asset,
            }
        ],
        "heure_transaction": datetime.datetime.now(
            ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d, %Hh-%Mmin")
    }