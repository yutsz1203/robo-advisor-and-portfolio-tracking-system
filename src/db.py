import time

import mariadb
import pandas as pd
import sqlalchemy
import streamlit as st
import yfinance as yf
from sqlalchemy import create_engine

today = time.strftime("%Y-%m-%d")


@st.cache_resource
def init_db_engine() -> sqlalchemy.Engine:
    db_config = st.secrets["mariadb"]

    engine = create_engine(
        f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )

    return engine


@st.cache_resource(show_spinner=False)
def db_connect():
    conn = st.connection("mysql", type="sql")
    return conn


@st.cache_resource(show_spinner=False)
def mariadb_connect() -> mariadb.Cursor:
    cfg = st.secrets["mariadb"]
    try:
        conn = mariadb.connect(
            host=cfg["host"],
            port=cfg.get("port", 6608),
            user=cfg["user"],
            password=cfg["password"],
            database="FYP",
        )
        conn.autocommit = True
        return conn.cursor()
    except mariadb.Error as e:
        st.error(f"Connection error: {e}")
        return None


def fetch_transaction() -> pd.DataFrame:
    """
    date, symbol, price, quantity, action, commission, UID
    """
    conn = st.connection("mysql", type="sql")
    tx_df = conn.query("SELECT * FROM Transaction")
    return tx_df


@st.cache_data(show_spinner=False)
def fetch_stock_event() -> pd.DataFrame:
    """
    symbol, date, eventType (0 for split, 1 for dividend), amount
    """
    conn = st.connection("mysql", type="sql")
    stock_events_df = conn.query("SELECT * FROM Stock_Event")
    return stock_events_df


def fetch_rate() -> pd.DataFrame:
    """
    date, currency, rate

    currency: USD/HKD
    """
    conn = st.connection("mysql", type="sql")
    rate_df = conn.query("SELECT * FROM Rate")
    # rate_df.set_index("date", inplace=True)
    return rate_df


def fetch_holdings() -> pd.DataFrame:
    """
    Return: holdings_df

    holdings_df schema: Symbol, Current Price, Position, Cost Basis, Sector, Class
    """
    conn = st.connection("mysql", type="sql")
    holdings_df = conn.query(
        "SELECT h.symbol, a.currentPrice, h.quantity, h.costBasis, s.sector, c.className, a.country "
        "FROM Holding h "
        "JOIN Asset a ON h.symbol = a.symbol "
        "JOIN Class c ON a.class = c.classID "
        "JOIN Sector s ON a.sector = s.sectorID;"
    )
    holdings_df.columns = [
        "Symbol",
        "Current Price",
        "Position",
        "Cost Basis",
        "Sector",
        "Class",
        "Country",
    ]
    return holdings_df


@st.cache_data(show_spinner=False)
def fetch_price(assets, start, adjust=False) -> pd.DataFrame:
    """
    symbol, date, close
    """
    prices = yf.download(assets, start=start, auto_adjust=adjust)["Close"]
    idx = pd.date_range(start=start, end=today, freq="D").date
    daily_prices = prices.reindex(idx).ffill()

    close_long = daily_prices.reset_index().melt(
        id_vars="Date", var_name="Symbol", value_name="Close"
    )

    prices = close_long.sort_values(["Date"]).reset_index(drop=True).ffill()
    prices.dropna(inplace=True)
    prices.columns = ["date", "symbol", "close"]
    prices.set_index(["date", "symbol"], inplace=True)
    return prices
