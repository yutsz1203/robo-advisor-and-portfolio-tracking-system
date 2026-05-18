import altair as alt
import plotly.express as px
import streamlit as st

from const import BASE_CURRENCIES, CURRENCY_SIGN_MAP, PERIODS
from helpers import (
    adjust_period,
    base_currency_format,
    color,
    country_format,
    create_chart,
    get_start_date,
)
from src.holding import build_allocation, get_holdings, get_portfolio_value

st.set_page_config(page_icon="📊", layout="wide")
st.title("📊 Portfolio Overview")
st.markdown("### Portfolio Value")
base_currency = st.selectbox(
    "Choose base currency",
    BASE_CURRENCIES,
    width=150,
    format_func=base_currency_format,
)
period = st.pills("Time period", PERIODS, default=PERIODS[6])

# Build holdings_df
holdings_df = get_holdings(base_currency)
# print(holdings_df)
assets = holdings_df["Symbol"].to_list()

total_portfolio_value = holdings_df["Market Value"].sum()
st.markdown(
    f"#### Portfolio Value: {CURRENCY_SIGN_MAP[base_currency]} {total_portfolio_value:,.2f}"
)

# Calculating Portfolio Value (Market Values of positions)
start = get_start_date()
portfolio_value = get_portfolio_value(assets, start, base_currency=base_currency)

# Adjust time period for showing Portfolio Value
start = adjust_period(start, period)
portfolio_value_df = portfolio_value[portfolio_value.index >= start]
portfolio_value_df = portfolio_value_df.reset_index()

# Plotting Portfolio Value graph
base = alt.Chart(portfolio_value_df).encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y(
        "base_value_after_tx:Q",
        title="Portfolio Value",
        scale=alt.Scale(
            domain=[
                portfolio_value_df["base_value_after_tx"].min() / 1.1,
                portfolio_value_df["base_value_after_tx"].max(),
            ]
        ),
    ),
)
tooltips = [
    alt.Tooltip("date:T", title="Date"),
    alt.Tooltip("base_value_after_tx:Q", title="Portfolio Value", format=",.2f"),
]
title = "Portfolio Value"
chart = create_chart(portfolio_value_df, "date", base, tooltips, title)
st.altair_chart(chart, use_container_width=True)


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Assets",
        "Allocation - Sectors",
        "Allocation - Classes",
        "Allocation - Currencies",
        "Allocation - Country",
    ]
)

# User's holdings
with tab1:
    # Symbol, Current Price, Position, Market Value, Cost Basis, P&L
    assets_df = holdings_df[
        [
            "Symbol",
            "Current Price",
            "Position",
            "Market Value",
            "Cost Basis",
            "Unrealised P&L",
        ]
    ].copy()
    styled_assets_df = assets_df.style.format(
        {
            "Current Price": "{:,.2f}",
            "Position": "{:,.2f}",
            "Market Value": "{:,.2f}",
            "Cost Basis": "{:,.2f}",
            "Unrealised P&L": "{:,.2f}",
        }
    )
    styled_assets_df = styled_assets_df.map(
        color, subset=["Unrealised P&L"], type="holding"
    )
    total_p_and_l = assets_df["Unrealised P&L"].sum()
    if total_p_and_l < 0:
        st.markdown(
            f"#### Unrealized P&L: :red[{CURRENCY_SIGN_MAP[base_currency]} {total_p_and_l:,.2f}]"
        )
    else:
        st.markdown(
            f"#### Unrealized P&L: :green[{CURRENCY_SIGN_MAP[base_currency]} {total_p_and_l:,.2f}]"
        )
    st.dataframe(styled_assets_df, hide_index=True)
    st.write(
        f"Note: Market Value, Cost Basis, and P&L are displayed in the chosen base currency, which is {base_currency_format(base_currency)}."
    )

# Allocation by Sector
with tab2:
    st.markdown("### Portfolio Allocation by Sector")
    sector_allocation = build_allocation(holdings_df)
    sector_fig = px.pie(sector_allocation, values="Market Value", names="Sector")
    sector_fig.update_traces(
        hovertemplate="Sector=%{label}<br>Market Value=%{value}<extra></extra>",
        textfont_size=16,
    )
    sector_fig.update_layout(legend_font_size=16)
    st.plotly_chart(sector_fig, key="sector_chart")
    sector_allocation = sector_allocation.groupby("Sector").sum()
    sector_allocation["Weight"] = (
        sector_allocation["Market Value"] / sector_allocation["Market Value"].sum()
    )
    sector_allocation = sector_allocation[["Weight"]] * 100
    sector_allocation.reset_index(inplace=True)
    st.dataframe(
        sector_allocation.sort_values(by="Weight", ascending=False), hide_index=True
    )

# Allocation by Asset Class
# [Stocks, Bonds, Commodities, Cryptocurrencies]
with tab3:
    st.markdown("### Portfolio Allocation by Asset Class")
    class_fig = px.pie(holdings_df, values="Market Value", names="Class")
    class_fig.update_traces(
        hovertemplate="Asset Class=%{label}<br>Market Value=%{value}<extra></extra>",
        textfont_size=16,
    )
    class_fig.update_layout(legend_font_size=16)
    st.plotly_chart(class_fig, key="class_chart")
    class_allocation = holdings_df[["Class", "Market Value"]]
    class_allocation = class_allocation.groupby("Class").sum()
    class_allocation["Weight"] = (
        class_allocation["Market Value"] / class_allocation["Market Value"].sum()
    )
    class_allocation = class_allocation[["Weight"]] * 100
    class_allocation.reset_index(inplace=True)
    st.dataframe(
        class_allocation.sort_values(by="Weight", ascending=False), hide_index=True
    )

# Allocation by Currency
# [HKD, USD, EUR, GBP, JPY, CNY]
with tab4:
    st.markdown("### Portfolio Allocation by Currency")
    holdings_df["currency"] = holdings_df["currency"].apply(base_currency_format)
    currency_fig = px.pie(holdings_df, values="Market Value", names="currency")
    currency_fig.update_traces(
        hovertemplate="Currency=%{label}<br>Market Value=%{value}<extra></extra>",
        textfont_size=16,
    )
    currency_fig.update_layout(legend_font_size=16)
    st.plotly_chart(currency_fig, key="currency_chart")
    currency_allocation = holdings_df[["currency", "Market Value"]]
    currency_allocation = currency_allocation.groupby("currency").sum()
    currency_allocation["Weight"] = (
        currency_allocation["Market Value"] / currency_allocation["Market Value"].sum()
    )
    currency_allocation = currency_allocation[["Weight"]] * 100
    currency_allocation.reset_index(inplace=True)
    st.dataframe(
        currency_allocation.sort_values(by="Weight", ascending=False), hide_index=True
    )

# Allocation by Country
with tab5:
    st.markdown("### Portfolio Allocation by Country")
    holdings_df["Country"] = holdings_df["Country"].apply(country_format)
    country_fig = px.pie(holdings_df, values="Market Value", names="Country")
    country_fig.update_traces(
        hovertemplate="Currency=%{label}<br>Market Value=%{value}<extra></extra>",
        textfont_size=16,
    )
    country_fig.update_layout(legend_font_size=16)
    st.plotly_chart(country_fig, key="country_chart")
    country_allocation = holdings_df[["Country", "Market Value"]]
    country_allocation = country_allocation.groupby("Country").sum()
    country_allocation["Weight"] = (
        country_allocation["Market Value"] / country_allocation["Market Value"].sum()
    )
    country_allocation = country_allocation[["Weight"]] * 100
    country_allocation.reset_index(inplace=True)
    st.dataframe(
        country_allocation.sort_values(by="Weight", ascending=False), hide_index=True
    )
