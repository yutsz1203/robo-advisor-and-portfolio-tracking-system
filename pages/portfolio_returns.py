import altair as alt
import pandas as pd
import streamlit as st

from const import MARKETS, MARKETS_MAP, PERIODS, RETURN_TEXT
from helpers import adjust_period, calc_return, create_chart, get_start_date
from src.holding import (
    get_holdings,
    get_portfolio_value,
    portfolio_time_weighted_return,
)

st.set_page_config(page_icon="📈", layout="wide")
st.title("📈 Portfolio Returns and Performance Benchmarking")
period = st.pills("Time period", PERIODS, key="value", default=PERIODS[6])

tab1, tab2 = st.tabs(["Portfolio Returns", "Performance Benchmarking"])

holdings_df = get_holdings()
assets = holdings_df["Symbol"].to_list()
start = get_start_date()
portfolio_value_df = get_portfolio_value(assets, start, adjust=True)
start = adjust_period(start, period)
portfolio_value_df = portfolio_value_df[portfolio_value_df.index >= start]

portfolio_return_df = portfolio_time_weighted_return(portfolio_value_df)
portfolio_return_df["TWR_pct_str"] = portfolio_return_df["TWR"].apply(
    lambda x: f"{x:.2f}%"
)
period_return = portfolio_return_df.iloc[-1]["TWR_pct_str"]

# Portfolio Return
with tab1:
    if "-" in period_return:
        st.markdown(f"### Total return {RETURN_TEXT[period]}: :red[{period_return}]")
    else:
        st.markdown(f"### Total return {RETURN_TEXT[period]}: :green[{period_return}]")
    base = alt.Chart(portfolio_return_df.reset_index()).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(
            "TWR:Q",
            title="Portfolio Return",
            scale=alt.Scale(
                domain=[
                    portfolio_return_df["TWR"].min(),
                    portfolio_return_df["TWR"].max(),
                ]
            ),
        ),
    )
    tooltips = [
        alt.Tooltip("date:T", title="Date"),
        alt.Tooltip("TWR_pct_str:N", title="Portfolio Return"),
    ]
    title = "Portfolio Return"
    chart = create_chart(portfolio_return_df, "date", base, tooltips, title)
    st.altair_chart(chart, width="stretch")

# Performance Benchmarking
with tab2:
    # Select markets for benchmarking
    market_tickers = [MARKETS_MAP[market] for market in MARKETS]
    returns = calc_return(market_tickers, period="10y")
    selected_markets = st.multiselect(
        "Select market for benchmarking",
        MARKETS,
        default=["US"],
    )

    # Calculating returns of selected markets
    selected_market_tickers = [MARKETS_MAP[market] for market in selected_markets]
    returns = returns[returns.index >= start]
    returns = returns[selected_market_tickers]
    returns = ((1 + returns).cumprod() - 1) * 100
    returns.columns = selected_markets
    returns["Portfolio"] = portfolio_return_df["TWR"]
    returns.reset_index(inplace=True)
    returns.rename(columns={"index": "date"}, inplace=True)

    all_series = ["Portfolio"] + selected_markets
    for col in all_series:
        returns[f"{col}_str"] = returns[col].apply(
            lambda x: f"{x:.2f}%" if pd.notna(x) else "—"
        )

    # Merging returns of portfolio and market benchmarks
    returns_long = returns.melt(
        id_vars="date",
        value_vars=all_series,
        var_name="series",
        value_name="return_pct",
    )
    returns_str_long = returns.melt(
        id_vars="date",
        value_vars=[f"{s}_str" for s in all_series],
        var_name="series_str",
        value_name="return_pct_str",
    )
    returns_str_long["series"] = returns_str_long["series_str"].str.replace("_str", "")
    returns_long = returns_long.merge(
        returns_str_long[["date", "series", "return_pct_str"]],
        on=["date", "series"],
        how="left",
    )

    # Plot graph of comparison
    color_palette = [
        "skyblue",
        "orange",
        "red",
        "green",
        "purple",
        "yellow",
        "grey",
        "pink",
    ]
    base = alt.Chart(returns_long).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(
            "return_pct:Q",
            title="Return (%)",
        ),
        color=alt.Color(
            "series:N",
            scale=alt.Scale(domain=all_series, range=color_palette[: len(all_series)]),
        ),
    )
    tooltips = [
        alt.Tooltip("date:T", title="Date"),
        alt.Tooltip("series:N", title="Series"),
        alt.Tooltip("return_pct_str:N", title="Return"),
    ]
    title = "Portfolio Return vs Benchmark Return"
    chart = create_chart(returns_long, "date", base, tooltips, title)
    st.altair_chart(chart, width="stretch")
