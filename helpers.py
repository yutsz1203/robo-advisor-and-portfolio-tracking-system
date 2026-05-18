import time
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import quantstats as qs
import streamlit as st
import yfinance as yf
from dateutil.relativedelta import relativedelta

from src.db import fetch_transaction


def bump_cache_key():
    st.session_state["cache_key"] = datetime.now().strftime("%Y%m%d-%H%M%S")


def base_currency_format(base_currency):
    currency_mapping = {
        "HKD": "🇭🇰 HKD",
        "USD": "🇺🇸 USD",
        "EUR": "🇪🇺 EUR",
        "GBP": "🇬🇧 GBP",
        "JPY": "🇯🇵 JPY",
        "CNY": "🇨🇳 CNY",
    }
    return currency_mapping[base_currency]


def country_format(country):
    if not country:
        return "N.A."
    country_mapping = {
        "Hong Kong": "🇭🇰 Hong Kong",
        "United States": "🇺🇸 United States",
        "United Kingdom": "🇬🇧 United Kingdom",
        "Japan": "🇯🇵 Japan",
        "China": "🇨🇳 China",
        "Netherlands": "🇳🇱 Netherlands",
        "Germany": "🇩🇪 Germany",
        "France": "🇫🇷 France",
    }
    return country_mapping.get(country, country)


def adjust_period(start: datetime.date, period: str) -> datetime.date:
    today = pd.Timestamp.today().date()
    if period == "1W":
        start = max(start, today - pd.Timedelta(days=7))
    elif period == "MTD":
        start = max(start, today.replace(day=1))
    elif period == "1M":
        start = max(start, today - relativedelta(months=1))
    elif period == "3M":
        start = max(start, today - relativedelta(months=3))
    elif period == "YTD":
        start = max(start, today.replace(month=1, day=1))
    elif period == "1Y":
        start = max(start, today - relativedelta(years=1))
    else:
        start = start
    return start


def get_start_date():
    tx_df = fetch_transaction()
    tx_df.set_index("date", inplace=True)
    start = tx_df.index.min()
    return start


def graph_nearest(field: str):
    return alt.selection_point(
        nearest=True, on="mouseover", fields=[field], empty=False
    )


def create_chart(
    df: pd.DataFrame, field: str, base: alt.Chart, tooltips: list, title: str
) -> alt.LayerChart:
    nearest = alt.selection_point(
        nearest=True, on="mouseover", fields=[field], empty=False
    )

    line = base.mark_line(strokeWidth=2, color="skyblue")

    rule = (
        alt.Chart(df.reset_index())
        .mark_rule(color="gray", strokeDash=[4, 4], strokeWidth=1)
        .encode(x=f"{field}:T")
        .transform_filter(nearest)
    )

    baseline = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="white", strokeDash=[4, 4], strokeWidth=1, opacity=0.4)
        .encode(y="y:Q")
    )

    points = (
        base.mark_circle(size=90, color="skyblue")
        .encode(
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
            tooltip=tooltips,
        )
        .add_params(nearest)
    )

    chart = (
        alt.layer(baseline, line, points, rule)
        .properties(
            width=1000,
            height=400,
            title=alt.Title(title, anchor="middle"),
        )
        .interactive()
    )

    return chart


@st.cache_data(show_spinner=True)
def calc_return(tickers, period):
    returns = qs.utils.download_returns(tickers, period=period)
    returns.index = pd.to_datetime(returns.index).date
    return returns


def format_series(series):
    series *= 100
    series = series.round(2)
    series.sort_values(ascending=False, inplace=True)
    return series


def color(val, type="p-val"):
    if type == "p-val":
        color = "red" if val > 0.05 else "green"
    else:
        color = "red" if val < 0 else "green"
    return f"color: {color}"


def period_select_box(key, index=4):
    period = st.selectbox(
        "Lookback Period",
        ("5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"),
        index=index,
        key=key,
    )
    return period


@st.cache_data(show_spinner=False)
def fetch_price(tickers, start, fetch_type="initial") -> pd.DataFrame:
    if isinstance(tickers, str):
        tickers = [tickers]

    org_start = pd.Timestamp(start)

    window_start = (org_start - timedelta(days=7)).strftime("%Y-%m-%d")
    window_end = (org_start + timedelta(days=7)).strftime("%Y-%m-%d")

    data = yf.download(
        tickers,
        start=window_start,
        end=window_end,
        auto_adjust=True,
        progress=False,
    )["Close"]

    if data.empty:
        raise ValueError(f"No price data found for {tickers} around {start}.")

    if fetch_type == "initial":
        price = data.asof(org_start)

        df = price.to_frame(name="Price").reset_index()
        df.rename(columns={df.columns[0]: "Ticker"}, inplace=True)
        df["Date"] = org_start

    else:
        rows = []
        for tick in tickers:
            time.sleep(0.5)
            ticker = yf.Ticker(tick)
            price = ticker.info.get("regularMarketPrice")
            if price is None:
                hist = ticker.history(period="1d", interval="1d", auto_adjust=True)
                price = hist["Close"].iloc[-1] if not hist.empty else None
            rows.append(
                {
                    "Ticker": tick,
                    "Price": price,
                    "Date": datetime.strptime(start, "%Y-%m-%d"),
                }
            )
        df = pd.DataFrame(rows)

    return df
