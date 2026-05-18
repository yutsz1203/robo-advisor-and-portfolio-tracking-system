import csv
import time
from datetime import date

import pymysql
import pandas as pd
import streamlit as st
import yfinance as yf
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine
from tqdm import tqdm

from const import CLASS_MAP, CURRENCIES, SECTOR_MAP, SESSION

db_connection_str = "mysql+pymysql://root:8888@miniweb.idv.hk:8080/FYP"
engine = create_engine(db_connection_str)


def db_connect():
    cfg = st.secrets["db"]
    try:
        conn = pymysql.connect(
            host=cfg["host"],
            port=cfg.get("port", 8080),
            user=cfg["user"],
            password=cfg["password"],
            database="FYP",
            autocommit=True,
        )
        return conn.cursor()
    except pymysql.Error as e:
        st.error(f"Connection error: {e}")
        return None


def insert_db(conn, ticker, price, sector, assetClass, country):
    try:
        conn.execute(
            "INSERT INTO Asset (symbol, currentPrice, sector, class, country) VALUES (%s, %s, %s, %s, %s)",
            (ticker, price, sector, assetClass, country),
        )
    except pymysql.Error as e:
        print(e)
        return update_db(conn, ticker, price)


def update_db(conn, ticker, price, country):
    try:
        conn.execute(
            "UPDATE Asset SET currentPrice = %s, country = %s WHERE symbol = %s",
            (price, country, ticker),
        )
    except pymysql.Error as e:
        print(e)
        return None


def fetch_db(conn):
    try:
        conn.execute("SELECT symbol FROM Asset")
    except pymysql.Error as e:
        print(e)
        return None
    return conn.fetchall()


def Test():
    ticker = yf.Ticker("9999.HK")
    print(ticker.info)


def read_csv():
    result = []
    with open("us_symbols.csv", newline="") as csvfile:
        spamreader = csv.reader(csvfile, delimiter=",")
        next(spamreader)
        for row in spamreader:
            result.append(row[0])
    return result


def Screener(conn):
    quotes = read_csv()
    for quote in quotes:
        info = yf.Ticker(quote, session=SESSION).info
        if "symbol" not in info:
            continue
        ticker = quote
        print(ticker)
        if "regularMarketPrice" in info:
            price = info["regularMarketPrice"]
        elif "regularMarketPreviousClose" in info:
            price = info["regularMarketPreviousClose"]
        else:
            continue
        sector = None
        assetClass = None
        if "sector" in info:
            sector = info["sector"]
            sector = SECTOR_MAP[sector]
        if "typeDisp" in info:
            assetClass = info["typeDisp"]
            assetClass = CLASS_MAP[assetClass]
        insert_db(conn, ticker, price, sector, assetClass)
    return None


def tickerFetch(quote, session):
    try:
        return yf.Ticker(quote, session=session).info
    except:
        time.sleep(5 * 60)
        return tickerFetch(quote, session)


def Updater(conn):
    # off = 0
    # q = yf.EquityQuery("eq", ["region", region])  # List[Str] -> List[QueryBase]
    # response = yf.screen(q, size=250, offset=off, session=SESSION, sortAsc=True)
    quotes = fetch_db(conn)
    if quotes is None:
        return 0
    for quote in tqdm(quotes):
        # print(quote["symbol"])
        # if len(quote["symbol"]) > 7:
        #     continue
        quote = quote[0]
        # print(quote)
        info = tickerFetch(quote, SESSION)
        ticker = quote
        if "regularMarketPrice" in info:
            price = info["regularMarketPrice"]
        elif "regularMarketPreviousClose" in info:
            price = info["regularMarketPreviousClose"]
        else:
            continue
        country = info.get("country", None)
        # insert_db(conn, ticker, price, SECTOR_MAP[sector], CLASS_MAP[assetClass])
        update_db(conn, ticker, price, country)
        print(ticker, price, country)


def update_rates(conn, currencies):
    dfs = []
    for currency_ticker, currency in currencies:
        print(f"Processing {currency}...")
        conn.execute(
            f"SELECT date FROM Rate WHERE currency = '{currency}' ORDER BY date DESC LIMIT 1"
        )
        results = conn.fetchone()
        if results:
            start = results[0] - relativedelta(days=2)
            rates = yf.download(
                currency_ticker, start=start, end=date.today(), interval="1d"
            )
        else:
            rates = yf.download(currency_ticker, period="10y", interval="1d")
            start = rates.index.min().date()
        if not rates.empty:
            df = rates["Close"].copy()
            df.columns = ["rate"]
            df = df.reindex(pd.date_range(start=start, end=date.today(), freq="D"))
            df["rate"] = df["rate"].ffill()
            df["currency"] = currency
            df["date"] = df.index
            df = df[df["date"].dt.date > start + relativedelta(days=2)]
            dfs.append(df)
        if df.empty:
            print(f"Rates ({currency}) up to date.")
    final = pd.concat(dfs, ignore_index=True)
    final.to_sql(name="Rate", con=engine, if_exists="append", index=False)
    engine.dispose()


def get_events(conn, ticker_list):
    tickers = yf.Tickers(" ".join(ticker_list))

    list_of_dfs = []
    # Loop through tickers to get calendar events
    for ticker in ticker_list:
        print(f"--- {ticker} Events ---")
        # Access split history
        try:
            df = tickers.tickers[ticker].actions
        except TypeError as e:
            print(f"No stock actions data for {ticker}.")
            continue
        df.index = df.index.date
        df["symbol"] = ticker
        df["date"] = df.index
        df = df[df["Dividends"] == 0]

        conn.execute(
            f"SELECT date FROM Stock_Event WHERE symbol = '{ticker}' ORDER BY date DESC LIMIT 1"
        )
        results = conn.fetchone()

        if results:
            df = df[df["date"] > results[0]]

        if df.empty:
            print(f"Stock splits record of {ticker} already up to date.")
            continue

        df.rename(columns={"Stock Splits": "amount"}, inplace=True)

        df["eventType"] = 0

        df = df[["symbol", "date", "eventType", "amount"]]

        list_of_dfs.append(df)
    if len(list_of_dfs) > 0:
        df = pd.concat([d for d in list_of_dfs if not d.empty], ignore_index=True)

        df.to_sql(name="Stock_Event", con=engine, if_exists="append", index=False)
        engine.dispose()

    return df


if __name__ == "__main__":
    # read_csv()
    conn = db_connect()
    # print(conn)
    # Test()
    # Screener(conn)
    update_rates(conn, CURRENCIES)
    # Updater(conn)
