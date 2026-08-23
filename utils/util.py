import requests
import datetime
import certifi
import json
from decimal import Decimal
from arch import arch_model
import numpy as np


def get_data(symbol, interval, start_time, end_time):
    url = "https://api.binance.com/api/v3/klines"
    
    result = []
    
    while start_time < end_time:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time,
            "limit": 1000
        }

        response = requests.get(
            url,
            params=params,
            timeout=10,
            verify=certifi.where()
        )

        if response.status_code != 200:
            raise ValueError(
                f"Erreur Binance HTTP {response.status_code}: "
                f"{response.text}"
            )
        data = response.json()
        
        if not data:
            break
        
        for k in data:
            candle = {
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            }
            
            result.append(candle)

        interval_ms = convert_in_ms(interval)
        start_time = data[-1][0] + interval_ms

    return result


def convert_in_ms(interval: str):
    if interval == "1m":
        return 60*1000
    elif interval == "1h":
        return 3600*1000
    elif interval == "1d":
        return 24*3600*1000


def get_historical_data(symbol, interval, nb_data):
    end_time = int(datetime.datetime.today().timestamp()*1000)
    start_time = end_time - convert_in_ms(interval) * nb_data
    return get_data(symbol, interval,
                    start_time=start_time, end_time=end_time)


def calculate_rsi(prices, periodes=1):
    delta = prices.diff()

    gain = delta.clip(lower=0)  # delta.where(delta>0, 0)
    loss = -delta.clip(upper=0)  # -delta.where(delta<0, 0)

    avg_gain = gain.rolling(window=periodes).mean()
    avg_loss = loss.rolling(window=periodes).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100/(1+rs))

    return rsi 


def macd(series, periode_1, periode_2):
    macd_1 = series.ewm(span=periode_1, adjust=False).mean()

    macd_2 = series.ewm(span=periode_2, adjust=False).mean()

    return macd_1 - macd_2


def fit_arch(series, p):
    model = arch_model(series, vol="ARCH", p=p)
    result = model.fit(update_freq=5, disp="off")
    return result


def forecast_volatility(res, horizon=1):
    """
    Retourne la volatilité conditionnelle prédite (écart-type, en %)
    """
    fc = res.forecast(horizon=horizon, reindex=False)
    variance_forecast = fc.variance.values[-1, :]
    vol_forecast = np.sqrt(variance_forecast)
    vol_forecast = np.sqrt(fc.variance.values[-1, :])
    return vol_forecast[0]


def update_balance(client, order):
    executed_qty = Decimal(str(order["executedQty"]))
    quote_qty = Decimal(str(order["cummulativeQuoteQty"]))
 
    frais_crypto = sum(
        Decimal(str(f["commission"])) for f in order["fills"]
        if f["commissionAsset"] == client.type_crypto
    )
    frais_usdt = sum(
        Decimal(str(f["commission"])) for f in order["fills"]
        if f["commissionAsset"] == "USDT"
    )
 
    if order["side"] == "BUY":
        client.usdt -= float(quote_qty)
        client.usdt -= float(frais_usdt)
        client.solde_crypto += float(executed_qty)
        client.solde_crypto -= float(frais_crypto)
    elif order["side"] == "SELL":
        client.solde_crypto -= float(executed_qty)
        client.solde_crypto -= float(frais_crypto)
        client.usdt += float(quote_qty)
        client.usdt -= float(frais_usdt)
 
    return client


def save_order(order, path="info_transactions/transactions.jsonl"):
    
    """
    JSON Lines : un objet JSON complet par ligne. Chaque ligne correspond
    exactement à une future ligne de table SQL FAIT_SIGNAL_TRADING — c'est
    ce format qui permet de migrer vers SQL plus tard sans rien changer à
    la structure des données elles-mêmes (voir weekly_metrics.py).
    """
    with open(path, "a") as f:
        f.write(json.dumps(order) + "\n")