import requests
import datetime
import time
import certifi


def get_data_binance(symbol, interval,
                     start_time, end_time):
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
                "volume": float(k[5]),
                "interval": interval,
                "crypto": symbol
                }
            result.append(candle)
        time.sleep(60)
        interval_ms = convert_in_ms(interval)
        start_time = data[-1][0] + interval_ms

    return result


def convert_in_ms(interval: str):
    """Cette fonction conertie les inetrvalles au format texte en 
    millisecondes.
    """
    if interval == "1m":
        return 60*1000
    elif interval == "1h":
        return 3600*1000
    elif interval == "1d":
        return 24*3600*1000


def get_historical_data(symbol, interval, nb_data):
    """Cette fonction permet de prendre en entrée un symbole de crypto, 
    un interval et la quantité de donnée souhaité et renvooie un json
    """
    end_time = int(datetime.datetime.today().timestamp()*1000)
    start_time = end_time - convert_in_ms(interval) * nb_data
    return get_data(symbol, interval,
                    start_time=start_time, end_time=end_time)
