import re

import numpy as np
import pandas as pd
import quantstats as qs
import statsmodels.api as sm
import streamlit as st
import yfinance as yf

from const import BENCHMARKS
from src.holding import get_holdings


def portfolio_historical(
    holdings_df: pd.DataFrame, period: str, interval: str
) -> pd.Series:
    """
    Get returns for certain period using certain interval data.

    Input:
    holdings_df (df): ['symbol', 'quantity', 'currentPrice', 'weight']
    period (str): "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", and "max"
    interval (str): "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"

    Output:
    portfolio_return (series): Index(pd.DateTimeIndex) Value(Float)
    e.g.
    Date
    2021-05-01   -0.029245
    """

    tickers = holdings_df["Symbol"].tolist()
    total_value = holdings_df["Market Value"].sum()
    holdings_df["weight"] = holdings_df["Market Value"] / total_value
    weights = holdings_df["weight"].tolist()

    returns = get_returns(tickers, period=period, interval=interval)

    # w_i = portfolio weights
    # w_tilda{i,t} = w_i / sum(w_j), R_{p,t} = sum (w_tilda{i,t} * R_{i,t})
    # R_{p,t} = sum(w_i * R_{i,t}) / sum(w_j)
    weighted = returns.mul(weights, axis=1)
    portfolio_return = weighted.sum(axis=1) / weighted.notna().mul(weights, axis=1).sum(
        axis=1
    )
    portfolio_return.name = "RP"

    return portfolio_return


@st.cache_data(show_spinner=False)
def get_returns(symbols, period="1y", interval="1d", log=False):
    data = yf.download(symbols, period=period, interval=interval, auto_adjust=True)
    prices = data["Close"]

    if log:
        returns = np.log(prices).diff()
    else:
        returns = prices.pct_change(fill_method=None)
    returns = returns.dropna(how="all").iloc[1:]
    return returns


@st.cache_data(show_spinner=False)
def get_volatility(returns: pd.DataFrame, steps=252):
    return returns.std() * np.sqrt(steps)


@st.cache_data(show_spinner=False)
def get_benchmarks_volatility(period, steps=252):
    benchmark_returns = get_returns(list(BENCHMARKS.values()), period=period)
    return get_volatility(benchmark_returns)


@st.cache_data(show_spinner=False)
def get_msci_returns(period="1y"):
    return qs.utils.download_returns("XWD.TO", period=period)


@st.cache_data(show_spinner=False)
def get_betas(returns, benchmark_returns):
    betas = []
    exchange_benchmark_map = {
        r"\.HK$": "^HSI",
        r"\.PA$|\.AS$|\.DE$|\.BR$|\.MI$|\.MC$": "^STOXX50E",
        r"\.L$": "^FTSE",
        r"\.T$": "^N225",
        r"\.SS$|\.SZ$": "000001.SS",
    }

    for col in returns.columns:
        selected_bench = "^GSPC"
        for pattern, bench_ticker in exchange_benchmark_map.items():
            if re.search(pattern, col):
                selected_bench = bench_ticker
                break

        asset_series = returns[col]
        bench_series = benchmark_returns[selected_bench]

        try:
            greeks = qs.stats.greeks(asset_series, bench_series)
            beta = greeks["beta"]
        except:
            beta = np.nan

        betas.append({"symbol": col, "beta": round(beta, 2)})

    return pd.DataFrame(betas)


@st.cache_data(show_spinner=False)
def get_corr_matrix(returns):
    return returns.corr()


@st.cache_data(show_spinner=False)
def generate_report(returns, benchmark, output_path):
    qs.reports.html(returns, benchmark=benchmark, output=output_path)


@st.cache_data(show_spinner=False)
def factor_analysis(period):
    holdings_df = get_holdings()
    portfolio_return = portfolio_historical(holdings_df, period, "1mo")
    portfolio_return.index = portfolio_return.index.map(
        lambda x: int(x.strftime("%Y%m"))
    )

    fama_df = pd.read_csv("data/F-F_Research_Data_5_Factors_2x3.csv", index_col=0)
    fama_df = fama_df / 100

    df = fama_df.join(portfolio_return).dropna()
    df["RP-RF"] = df["RP"] - df["RF"]

    y = df["RP-RF"]
    X = df[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]]
    X = sm.add_constant(X)

    model = sm.OLS(y, X).fit()
    return model
