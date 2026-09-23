from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import ta
from sqlalchemy import create_engine, text
from uuid import uuid4
import json
import time
import gzip
from google.cloud import storage
from google.api_core.exceptions import Conflict
from utils.clients import Client  # noqa: E402
from utils.util import (  # noqa: E402
    get_historical_data,
    fit_arch,
    forecast_volatility,
    update_balance,
    get_secret
)

MARGE_SECURITE_FRAIS = Decimal("0.999")

LOG = """    Transaction non effectuée

        Type de la transaction:{interval}
        Type de crypto:{crypto}
        Heure:{heure}
        Nom du client:{prenom} {nom}
"""

# connection à notre bucket de transaction
client = storage.Client("jan26-cde-crypto")
bucket_name = "trading-bot-bucket-epiphane-2026"
bucket = client.get_bucket(bucket_name)
print(f"Bucket '{bucket_name}' already exists, connected instead.")


def trade_bnb():
    try:
        data = get_historical_data("BNBUSDT", "1h", 850)
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

    database_url = get_secret("jan26-cde-crypto", "clients-database-url-pooler")

    engine = create_engine(database_url)
    conn = engine.connect()

    query = """SELECT * FROM Clients WHERE type_crypto='Binance Coin (BNB)' 
    AND interval='1 Heure' """

    df_client = pd.read_sql(query, con=engine)

    for index, row in df_client.iterrows():
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
        query = f"""UPDATE Clients
        SET usdt = {client.usdt},
        solde_crypto = {client.solde_crypto}
        WHERE clientorderid = '{id}' """
        conn.execute(text(query))
        conn.commit()

        # if a transaction performed, we save it to a bucket in gcp
        # if there is no transaction we write a message transactions.log
        if order is None:
            print(LOG.format(
                    interval=client.interval,
                    crypto=client.type_crypto,
                    heure=datetime.now(
                        ZoneInfo("Europe/Paris")
                    ).strftime("%Y-%m-%d, %Hh-%Mmin"),
                    prenom=client.firstname,
                    nom=client.lastname,
                ))
        else:
            file_path = f"raw/transactions-{uuid4()}.jsonl.gz"

            try:
                blob = bucket.blob(file_path)

                # Une ligne JSONL
                content = json.dumps(order) + "\n"

                # str -> bytes -> gzip
                compressed_content = gzip.compress(
                    content.encode("utf-8")
                )

                blob.upload_from_string(
                    compressed_content,
                    content_type="application/x-ndjson"
                )

            except Exception as e:
                print(e)
    conn.close()
    engine.dispose()


def trade_btc():
    try:
        data = get_historical_data("BTCUSDT", "1h", 850)
    except Exception as e:
        print(e)
        return

    df = pd.DataFrame(data)
    df = df.set_index("open_time")
    df["rendement"] = df["close"].pct_change() * 1000
    df["SMA200"] = ta.trend.sma_indicator(df["close"], 200)
    df["SMA600"] = ta.trend.sma_indicator(df["close"], 600)
    df.dropna(inplace=True)

    res = fit_arch(df["rendement"], p=1)
    vol_pred = forecast_volatility(res, horizon=1)

    frac = min(1.0, 0.05 / vol_pred)

    signal_achat = df["SMA200"].iloc[-1] > df["SMA600"].iloc[-1]
    signal_vente = df["SMA200"].iloc[-1] < df["SMA600"].iloc[-1]

    database_url = get_secret(
        "jan26-cde-crypto",
        "clients-database-url-pooler"
    )

    engine = create_engine(database_url)
    conn = engine.connect()

    query = """
    SELECT *
    FROM Clients
    WHERE type_crypto='Bitcoin (BTC)'
    AND interval='1 Heure'
    """

    df_client = pd.read_sql(query, con=engine)

    for index, row in df_client.iterrows():

        # IMPORTANT : reset pour chaque client
        order = None

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
                client.usdt
                * float(MARGE_SECURITE_FRAIS)
                * frac
            ) / df["close"].iloc[-1]

            order = client.buy_or_sell(
                "BUY",
                client.type_crypto,
                df,
                quantity
            )

            update_balance(client, order)

        elif client.solde_crypto > 0.0001 and signal_vente:
            quantity = client.solde_crypto * frac

            order = client.buy_or_sell(
                "SELL",
                client.type_crypto,
                df,
                quantity
            )

            update_balance(client, order)

        # Mise à jour de la DB
        query = f"""
        UPDATE Clients
        SET usdt = {client.usdt},
            solde_crypto = {client.solde_crypto}
        WHERE clientorderid = '{id}'
        """

        conn.execute(text(query))
        conn.commit()

        # Pas de transaction
        if order is None:
            print(
                LOG.format(
                    interval=client.interval,
                    crypto=client.type_crypto,
                    heure=datetime.now(
                        ZoneInfo("Europe/Paris")
                    ).strftime("%Y-%m-%d, %Hh-%Mmin"),
                    prenom=client.firstname,
                    nom=client.lastname,
                )
            )

        # Transaction effectuée -> GCS
        else:
            file_path = f"raw/transactions-{uuid4()}.jsonl.gz"

            try:
                blob = bucket.blob(file_path)

                content = json.dumps(order) + "\n"

                compressed_content = gzip.compress(
                    content.encode("utf-8")
                )

                blob.upload_from_string(
                    compressed_content,
                    content_type="application/x-ndjson"
                )

            except Exception as e:
                print(e)

    conn.close()
    engine.dispose()


def trade_eth():
    try:
        data = get_historical_data("ETHUSDT", "1h", 850)
    except Exception as e:
        print(e)
        return

    df = pd.DataFrame(data)
    df = df.set_index("open_time")
    df["rendement"] = df["close"].pct_change() * 1000
    df["SMA200"] = ta.trend.sma_indicator(df["close"], 200)
    df["SMA600"] = ta.trend.sma_indicator(df["close"], 600)
    df.dropna(inplace=True)

    res = fit_arch(df["rendement"], p=1)
    vol_pred = forecast_volatility(res, horizon=1)

    frac = min(1.0, 0.05 / vol_pred)

    signal_achat = df["SMA200"].iloc[-1] > df["SMA600"].iloc[-1]
    signal_vente = df["SMA200"].iloc[-1] < df["SMA600"].iloc[-1]

    database_url = get_secret(
        "jan26-cde-crypto",
        "clients-database-url-pooler"
    )

    engine = create_engine(database_url)
    conn = engine.connect()

    query = """
    SELECT *
    FROM Clients
    WHERE type_crypto='Ethereum (ETH)'
    AND interval='1 Heure'
    """

    df_client = pd.read_sql(query, con=engine)

    for index, row in df_client.iterrows():

        # IMPORTANT : reset pour chaque client
        order = None

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
                client.usdt
                * float(MARGE_SECURITE_FRAIS)
                * frac
            ) / df["close"].iloc[-1]

            order = client.buy_or_sell(
                "BUY",
                client.type_crypto,
                df,
                quantity
            )

            update_balance(client, order)

        elif client.solde_crypto > 0.0001 and signal_vente:
            quantity = client.solde_crypto * frac

            order = client.buy_or_sell(
                "SELL",
                client.type_crypto,
                df,
                quantity
            )

            update_balance(client, order)

        # Mise à jour de la DB
        query = f"""
        UPDATE Clients
        SET usdt = {client.usdt},
            solde_crypto = {client.solde_crypto}
        WHERE clientorderid = '{id}'
        """

        conn.execute(text(query))
        conn.commit()

        # Pas de transaction
        if order is None:
            print(
                LOG.format(
                    interval=client.interval,
                    crypto=client.type_crypto,
                    heure=datetime.now(
                        ZoneInfo("Europe/Paris")
                    ).strftime("%Y-%m-%d, %Hh-%Mmin"),
                    prenom=client.firstname,
                    nom=client.lastname,
                )
            )

        # Transaction effectuée -> GCS
        else:
            file_path = f"raw/transactions-{uuid4()}.jsonl.gz"

            try:
                blob = bucket.blob(file_path)

                content = json.dumps(order) + "\n"

                compressed_content = gzip.compress(
                    content.encode("utf-8")
                )

                blob.upload_from_string(
                    compressed_content,
                    content_type="application/x-ndjson"
                )

            except Exception as e:
                print(e)

    conn.close()
    engine.dispose()


if __name__ == "__main__":
    trade_bnb()
    time.sleep(10)
    trade_btc()
    time.sleep(10)
    trade_eth()