import re

import mariadb
import streamlit as st
import yfinance as yf

from const import CLASS_MAP, SECTOR_MAP, SESSION
from update_db import get_events, insert_db

from .db import fetch_holdings, fetch_stock_event


def get_tx(_conn):
    df = _conn.query(
        "SELECT * FROM FYP.Transaction",
    )
    df.drop(columns=["UID"], inplace=True)
    df.columns = [
        "TId",
        "Date",
        "Symbol",
        "Price",
        "Quantity",
        "Action",
        "Commission",
    ]
    lastid = df.iloc[-1]["TId"]
    st.session_state["lastrowid"] = lastid + 1
    return df


SUPPORTED_EXCHANGE_SUFFIXES = (
    ".HK",
    ".SS",
    ".SZ",
    ".L",
    ".PA",
    ".AS",
    ".DE",
    ".BR",
    ".MI",
    ".MC",
    ".T",
)

SUPPORTED_EXCHANGE_MESSAGE = (
    "Supported exchanges are US tickers (no suffix) or the following suffixes: "
    + ", ".join(SUPPORTED_EXCHANGE_SUFFIXES)
)


def is_supported_ticker(symbol: str) -> bool:
    if not isinstance(symbol, str) or not symbol.strip():
        return False
    normalized = symbol.strip().upper()
    if "." not in normalized:
        return bool(re.match(r"^[A-Z0-9]+$", normalized))
    return any(normalized.endswith(suffix) for suffix in SUPPORTED_EXCHANGE_SUFFIXES)


def can_fetch_ticker(symbol: str) -> bool:
    try:
        ticker = yf.Ticker(symbol, session=SESSION)
        info = ticker.info
        if (
            info.get("regularMarketPrice") is not None
            or info.get("regularMarketPreviousClose") is not None
        ):
            return True
        history = ticker.history(period="5d", interval="1d", auto_adjust=True)
        return not history.empty
    except Exception:
        return False


def validate_ticker(symbol: str):
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return False, "Please enter a ticker symbol."

    supported = is_supported_ticker(symbol)
    fetchable = can_fetch_ticker(symbol)

    if not supported and not fetchable:
        return (
            False,
            f"Ticker '{symbol}' is not supported or cannot be found on Yahoo Finance. {SUPPORTED_EXCHANGE_MESSAGE}",
        )
    if not supported:
        return (
            False,
            f"Ticker '{symbol}' is not on a supported exchange. {SUPPORTED_EXCHANGE_MESSAGE}",
        )
    if not fetchable:
        return (
            False,
            f"Ticker '{symbol}' cannot be fetched from Yahoo Finance. Please verify the symbol. (For HK stock, please use 4 digits, e.g. 0005.HK)",
        )

    return True, ""


def delete_tx(tid, conn):
    try:
        tid = int(tid)
        # Fetch the transaction details before deleting
        conn.execute(
            "SELECT date, symbol, price, quantity, action, commission FROM FYP.Transaction WHERE transactionID = ?",
            (tid,),
        )
        row = conn.fetchone()
        if not row:
            st.error("Transaction not found.")
            return False
        tx_date, symbol, price, quantity, action, commission = row

        # Delete the transaction
        conn.execute("DELETE FROM FYP.Transaction WHERE transactionID = ?", (tid,))

        # Reverse the holdings update
        holdings_df = fetch_holdings()
        stock_events = fetch_stock_event()
        if symbol not in stock_events["symbol"].values:
            stock_events = get_events(conn, [symbol])

        normalized_quantity, normalized_price = normalize_historical_transaction(
            stock_events, symbol, tx_date, quantity, price
        )

        action_val = 1 - 2 * action  # buy -> 1, sell -> -1

        if symbol in holdings_df["Symbol"].values:
            current_quantity = holdings_df.loc[
                holdings_df["Symbol"] == symbol, "Position"
            ].item()
            current_costbasis = holdings_df.loc[
                holdings_df["Symbol"] == symbol, "Cost Basis"
            ].item()

            new_quantity = current_quantity - (action_val * normalized_quantity)
            new_costbasis = current_costbasis - (
                action_val * normalized_quantity * normalized_price
                + action_val * commission
            )

            if abs(new_quantity) < 1e-6:
                conn.execute("DELETE FROM FYP.Holding WHERE symbol = ?", (symbol,))
            else:
                conn.execute(
                    "UPDATE FYP.Holding SET quantity=?, costBasis=? WHERE symbol=?",
                    (new_quantity, new_costbasis, symbol),
                )

        return True
    except (ValueError, mariadb.Error) as e:
        st.error(f"Delete failed: {e}")
        return False


def insert_tx(form, conn):
    try:
        conn.execute(
            "INSERT INTO FYP.Transaction VALUES (?, ?, ?, ?, ?, ?, ?, ?)", form
        )
        holdings_df = fetch_holdings()
        tx_date, symbol, price, quantity, action, commission = form[1:-1]
        action = 1 - 2 * action  # buy -> 0 to 1, sell -> 1 to -1

        stock_events = fetch_stock_event()
        if symbol not in stock_events["symbol"].values:
            stock_events = get_events(conn, [symbol])

        quantity, price = normalize_historical_transaction(
            stock_events, symbol, tx_date, quantity, price
        )

        if symbol in holdings_df["Symbol"].values:
            new_quantity = holdings_df.loc[
                holdings_df["Symbol"] == symbol, "Position"
            ].item() + (action * quantity)
            new_costbasis = (
                holdings_df.loc[holdings_df["Symbol"] == symbol, "Cost Basis"].item()
                + (action * quantity * price)
                + (action * commission)
            )
            conn.execute(
                """
                UPDATE FYP.Holding
                SET quantity=?, costBasis=?
                WHERE symbol=?
                """,
                (new_quantity, new_costbasis, symbol),
            )

        else:
            insert_new_asset(conn, symbol)
            new_holding = (
                symbol,
                quantity * action,
                quantity * price * action + commission,
                1,
            )
            conn.execute("INSERT INTO FYP.Holding VALUES (?, ?, ?, ?)", new_holding)

        return 1
    except mariadb.Error as e:
        st.error(e)
        return 0


def insert_new_asset(conn, symbol: str):

    try:
        conn.execute("SELECT * FROM Asset WHERE symbol = ?", [symbol])
    except mariadb.Error as e:
        print(e)
        return None

    res = conn.fetchall()

    # Asset in Asset table already
    if res:
        print(f"{symbol} in Asset table already.")
        return

    ticker = yf.Ticker(symbol, session=SESSION)
    info = ticker.info

    if "regularMarketPrice" in info:
        price = info["regularMarketPrice"]
    elif "regularMarketPreviousClose" in info:
        price = info["regularMarketPreviousClose"]
    else:
        price = 0

    assetClass = info.get("typeDisp", "")
    country = info.get("country", None)
    if assetClass == "ETF":
        fund_data = ticker.funds_data
        sector_weightings = fund_data.sector_weightings

        # Sector 13: Multi (has sector weightings data)
        sector = 13 if sector_weightings else 12

        category = info.get("category", "")
        cleaned_category = category.strip().lower()
        bond_position = fund_data.asset_classes.get("bondPosition", 0)

        if not bond_position:
            bond_position = 0

        if "bond" in cleaned_category or bond_position > 0.8:
            assetClass = CLASS_MAP["Bond"]
        elif cleaned_category == "digital assets":
            assetClass = CLASS_MAP["Cryptocurrency"]
        elif "commodities" in cleaned_category or "commodity" in cleaned_category:
            assetClass = CLASS_MAP["Commodity"]
        else:
            assetClass = CLASS_MAP["Equity"]

    else:
        assetClass = CLASS_MAP[assetClass]
        sector = info.get("sector", "")
        sector = SECTOR_MAP[sector]

    insert_db(conn, symbol, price, sector, assetClass, country)

    print(
        f"Inserted {symbol}. Price: {price}; Sector: {sector}; Asset Class: {assetClass}; Country: {country}."
    )


def normalize_historical_transaction(stock_events, ticker, tx_date, tx_qty, tx_price):
    """
    Converts historical units to current units based on split history.
    """
    cumulative_factor = 1.0
    stock_events = stock_events[
        (stock_events["symbol"] == ticker) & (stock_events["date"] > tx_date)
    ]
    if not stock_events.empty:
        cumulative_factor *= stock_events["amount"].prod()

    normalized_qty = tx_qty * cumulative_factor
    normalized_price = tx_price / cumulative_factor

    return normalized_qty, normalized_price
