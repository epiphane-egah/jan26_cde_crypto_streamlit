import os
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import ta
from sqlalchemy import create_engine, text
import dotenv
dotenv.load_dotenv()

from utils.clients import Client  # noqa: E402
from utils.util import (  # noqa: E402
    get_historical_data,
    fit_arch,
    forecast_volatility,
    update_balance,
    save_order,
)

MARGE_SECURITE_FRAIS = Decimal("0.999")
LOG = """    Transaction non effectuée

        Type de la transaction:{interval}
        Type de crypto:{crypto}
        Heure:{heure}
        Nom du client:{prenom} {nom}
"""


def trade():
    try:
        data = get_historical_data("ETHUSDT", "1h", 850)
    except Exception as e:
        print(e)
    df = pd.DataFrame(data)
    df = df.set_index("open_time")
    df["rendement"] = df["close"].pct_change() * 1000
    df["SMA200"] = ta.trend.sma_indicator(df["close"], 200)
    df["SMA600"] = ta.trend.sma_indicator(df["close"], 600)
    df.dropna(inplace=True)

    res = fit_arch(df["rendement"], p=1)

    vol_pred = forecast_volatility(res, horizon=1)

    # si ma volatilité est supérieure à 0.05, j'investis
    # seulement une fraction de mon usdt
    frac = min(1.0, 0.05 / vol_pred)

    signal_achat = df["SMA200"].iloc[-1] > df["SMA600"].iloc[-1]
    signal_vente = df["SMA200"].iloc[-1] < df["SMA600"].iloc[-1]

    order = None
    
    user = os.getenv("user")
    password = os.getenv("password")
    host = os.getenv("host")
    port = os.getenv("DB_PORT")
    table_name = os.getenv('table_name')
    db_name = os.getenv("dbname")

    engine = create_engine(
        f"postgresql://{user}:{password}@{host}:{port}/{db_name}")
    conn = engine.connect()

    query = f"""SELECT * FROM {table_name} WHERE type_crypto='Ethereum (ETH)' 
    AND interval='1 Heure' """

    df_client = pd.read_sql(query, con=engine)

    for index, row in df_client.iterrows():
        id = row.clientorderid
        nom = row.lastname
        prenom = row.firstname
        crypto = row.type_crypto
        intervalle = row.interval
        solde_crypto = row.solde_crypto
        usdt = row.usdt

        client = Client(
            firstname=prenom,
            lastname=nom,
            type_crypto=crypto,
            interval=intervalle,
            usdt_sold=usdt,
            crypto_sold=solde_crypto,
        )

        if client.usdt > 10 and signal_achat:
            quantity = (
                client.usdt * float(MARGE_SECURITE_FRAIS) * frac
            ) / df["close"].iloc[-1]
            order = client.buy_or_sell(
                "BUY", client.type_crypto, df, quantity
            )
            update_balance(client, order)
        elif client.solde_crypto > 0.0001 and signal_vente:
            quantity = client.solde_crypto * frac
            order = client.buy_or_sell(
                "SELL", client.type_crypto, df, quantity
            )
            update_balance(client, order)

        # Update client information in the database
        query = f"""UPDATE {table_name}
        SET usdt = {client.usdt},
        solde_crypto = {client.solde_crypto}
        WHERE clientorderid = '{id}' """
        conn.execute(text(query))
        conn.commit()

        # if a transaction performed, we save it to a jsonl document
        # if there is no transaction we write a message transactions.log
        if order is None:
            with open("logs/non_transactions.log", "a") as f:
                f.write(LOG.format(
                    interval=client.interval,
                    crypto=client.type_crypto,
                    heure=datetime.now(
                        ZoneInfo("Europe/Paris")
                    ).strftime("%Y-%m-%d, %Hh-%Mmin"),
                    prenom=client.firstname,
                    nom=client.lastname,
                ))
        else:
            date_now = datetime.now(tz=ZoneInfo("Europe/Paris"))
            month, year = date_now.month, date_now.year
            path = f"info_transactions/transactions-{year}-{month}.jsonl"
            save_order(order, path)


if __name__ == "__main__":
    trade()
