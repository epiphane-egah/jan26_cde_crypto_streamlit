import sys
import glob
import json
from decimal import Decimal
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import ta
from utils.clients import Client # noqa: E402
from utils.util import (get_historical_data, fit_arch,
                  forecast_volatility, update_balance,
                  save_order) # noqa: E402
MARGE_SECURITE_FRAIS = Decimal("0.999")
LOG = """    Transaction non effectuée

        Type de la transaction:{interval}
        Type de crypto:{crypto}
        Heure:{heure}
        Nom du client:{prenom} {nom}
"""


def trade():
    data = get_historical_data("ETHUSDT", "1d", 850)
    df = pd.DataFrame(data)
    df = df.set_index("open_time")
    df["rendement"] = df["close"].pct_change() * 1000
    df["SMA200"] = ta.trend.sma_indicator(df["close"], 200)
    df["SMA600"] = ta.trend.sma_indicator(df["close"], 600)
    df.dropna(inplace=True)
    
    res = fit_arch(df["rendement"], p=1)

    vol_pred = forecast_volatility(res, horizon=1)

    frac = min(1.0, 0.05 / vol_pred) # si ma volatilité est 
    # supérieur à 0.05, j'investie seulement une fraction de mon usdt

    signal_achat = df["SMA200"].iloc[-1] > df["SMA600"].iloc[-1]
    signal_vente = df["SMA200"].iloc[-1] < df["SMA600"].iloc[-1]

    order = None

    for path in glob.glob('info_clients/*.json'):
        with open(path, mode="r") as f:
            data = json.load(f)
        nom = data["lastname"]
        prenom = data["firstname"]
        crypto = data["type_crypto"]
        intervalle = data['interval']
        solde_crypto = data["solde_crypto"]
        usdt = data["usdt"]
        if intervalle != "1 Journée" and crypto != "Ethereum (ETH)":
            continue
       
        client = Client(firstname=prenom, lastname=nom,
                        type_crypto=crypto, interval=intervalle,
                        usdt_sold=usdt, crypto_sold=solde_crypto)

        if client.usdt > 10 and signal_achat:
            quantity = (
                            client.usdt
                            * float(MARGE_SECURITE_FRAIS)
                            * frac
                        ) / df["close"].iloc[-1]
            order = client.buy_or_sell("BUY", client.type_crypto, df, quantity)
            update_balance(client, order)
        elif client.solde_crypto > 0.0001 and signal_vente:
            quantity = client.solde_crypto * frac
            order = client.buy_or_sell("SELL", client.type_crypto, df, quantity)
            update_balance(client, order)
        save_path = save_path = f"info_clients/client_{nom.lower().strip()}_{prenom.lower().strip()}_{crypto}.json"
        Client.save(path=save_path, usdt=usdt,
                    solde_crypto=solde_crypto,
                    lastname=nom, firstname=prenom,
                    interval=intervalle, crypto=crypto)

        if order is None:
            with open("logs/transactions.log", "a") as f:
                f.write(LOG.format(interval=client.interval,
                 crypto=client.type_crypto,
                 heure=datetime.now(ZoneInfo("Europe/paris")).strftime("%Y-%m-%d, %Hh-%Mmin"),
                 prenom=client.firstname,
                 nom=client.lastname))
        else:
            save_order(order)


while True:
    trade()
    time.sleep(3600)