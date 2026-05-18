# display portfolio components, past return performance graph, risk metrics, simulating value growth

import json
from datetime import date, datetime

import altair as alt
import pandas as pd
import plotly.express as px
import quantstats as qs
import streamlit as st

from const import RETURN_TEXT
from helpers import adjust_period, create_chart, fetch_price
from src.db import fetch_rate
from src.fx import assign_currency, convert_to_base, get_rates_pivot
from src.mpt import portfolio_optimize
from src.rebalance import rebalance_check, rebalance_NoSell, rebalance_Sell


@st.cache_data(show_spinner=False)
def historical_return(tickers):
    returns = qs.utils.download_returns(tickers, period="5y")
    return returns


@st.dialog("Rebalancing")
def rebalance_dialog(current, target):
    col1, col2 = st.columns([3, 2], vertical_alignment="center")
    with col1:
        st.write("Rebalance your portfolio")
    with col2:
        sell = st.toggle("With Selling")
    if sell:
        rebalance_df = rebalance_Sell(current, target)
        st.write(":red[**Sell**]")
        sell_df = rebalance_df[rebalance_df["Investment Action"] < 0]
        sell_df["Investment Action"] = -sell_df["Investment Action"]
        st.dataframe(
            sell_df,
            hide_index=True,
            column_config={
                "Investment Action": st.column_config.NumberColumn(
                    "Amount", format="-$%.2f"
                )
            },
        )
        st.write(":green[**Buy**]")
        buy_df = rebalance_df[rebalance_df["Investment Action"] > 0]
        st.dataframe(
            buy_df,
            hide_index=True,
            column_config={
                "Investment Action": st.column_config.NumberColumn(
                    "Amount", format="$%.2f"
                )
            },
        )
    else:
        rebalance_df = rebalance_NoSell(current, target)
        rebalance_df.loc[-1] = [
            "Total",
            rebalance_df["Investment Action"].sum(),
            rebalance_df["# of Shares"].sum(),
        ]
        st.dataframe(
            data=rebalance_df,
            hide_index=True,
            column_config={
                "Investment Action": st.column_config.NumberColumn(
                    "Buy", format="$%.2f"
                )
            },
        )


MARKET_TICKERS = {"VOO", "2800.HK", "VXUS"}
SECTOR_TICKERS = {
    "XLK",
    "XLF",
    "XLV",
    "XLY",
    "XLP",
    "XLI",
    "XLE",
    "XLU",
    "XLB",
    "XLRE",
    "XLC",
}
COMMODITY_TICKERS = {"GLD", "SLV", "USO", "DBB", "DBA", "DJP", "IBIT"}


def get_asset_category(asset):
    if asset == "BND":
        return "Bond"
    if asset in MARKET_TICKERS:
        return "Market"
    if asset in SECTOR_TICKERS:
        return "Sector"
    return "Commodity"


def apply_custom_category_weights(base_df, new_cat_weights):
    result = base_df.copy()
    result["Category"] = result["Asset"].apply(get_asset_category)
    cat_totals = result.groupby("Category")["Weight"].sum()
    for cat, new_weight in new_cat_weights.items():
        mask = result["Category"] == cat
        old_total = cat_totals.get(cat, 0)
        if old_total > 0:
            result.loc[mask, "Weight"] = (
                result.loc[mask, "Weight"] / old_total * new_weight
            )
    return result.drop(columns=["Category"])


def load_results():
    with open("output/risk_assessment_result.json", "r") as f:
        res = json.load(f)
    return res


def save_custom_weights(cat_weights):
    res = load_results()
    res["custom_cat_weights"] = cat_weights
    with open("output/risk_assessment_result.json", "w") as f:
        json.dump(res, f, indent=4)


def clear_custom_weights():
    res = load_results()
    res.pop("custom_cat_weights", None)
    with open("output/risk_assessment_result.json", "w") as f:
        json.dump(res, f, indent=4)


def get_robo_holdings(df, rate_df, user_info):
    start = user_info["created_on"]
    total_investment = user_info["total_investment"]
    assets = df["Asset"].tolist()

    initial_price = fetch_price(assets, start)
    initial_price = assign_currency(initial_price, "Ticker")
    rates_pivot = get_rates_pivot(rate_df)
    price_series = initial_price.set_index("Ticker")["Price"]
    df["Base Current Price"] = df["Asset"].map(price_series)
    initial_price["Price"] = convert_to_base(
        df=initial_price,
        value_col="Price",
        currency_col="currency",
        date_col="Date",
        base_currency="USD",
        rates_pivot=rates_pivot,
    )
    initial_price.set_index("Ticker", inplace=True)

    current_price = fetch_price(assets, str(date.today()), fetch_type="current")
    # current_price = pd.DataFrame(
    #     {
    #         "Ticker": ["2800.HK", "BND", "DJP", "IBIT", "XLE", "XLRE"],
    #         "Price": [30.959999, 73.800003, 42.259998, 35.590000, 60.110001, 41.020000],
    #         "Date": [datetime.strptime("2026-04-14", "%Y-%m-%d")] * 6,
    #     }
    # )
    current_price = assign_currency(current_price, "Ticker")
    current_price["Price"] = convert_to_base(
        df=current_price,
        value_col="Price",
        currency_col="currency",
        date_col="Date",
        base_currency="USD",
        rates_pivot=rates_pivot,
    )
    current_price.set_index("Ticker", inplace=True)

    df.index = df["Asset"]
    df["currency"] = initial_price["currency"]
    df["Initial Price"] = initial_price["Price"]
    df["Current Price"] = current_price["Price"]
    df["Amount to buy"] = total_investment * df["Weight"]
    df["Shares to buy"] = df["Amount to buy"] / df["Initial Price"]
    df["date"] = date.today()
    df["Market Value"] = df["Current Price"] * df["Shares to buy"]
    df.loc[df["currency"] == "GBP", "Amount to buy"] /= 100  # Adjust for pence
    df.loc[df["currency"] == "GBP", "Market Value"] /= 100  # Adjust for pence

    df["Unrealised P&L"] = df["Market Value"] - df["Amount to buy"]
    df["Current Weight"] = df["Market Value"] / df["Market Value"].sum()
    df.drop(columns=["date", "Asset"], inplace=True)
    df = df.reset_index()
    return df


res = load_results()
rate_df = fetch_rate()
risk_preference = res["risk_preference"]
total_investment = res["total_investment"]
asset_list = res["asset_list"]

if "custom_cat_weights" not in st.session_state and "custom_cat_weights" in res:
    st.session_state["custom_cat_weights"] = res["custom_cat_weights"]


weights_df, model_weights = portfolio_optimize(risk_preference, asset_list)
system_weights_df = weights_df.copy()
holdings_df = get_robo_holdings(weights_df, rate_df, res)
holdings_check = holdings_df[["Asset", "Current Weight"]]
holdings_check.columns = ["Symbol", "Weight"]
weights_df = weights_df.reset_index()
rebalance = rebalance_check(weights_df)


if "custom_cat_weights" in st.session_state:
    _custom_raw = apply_custom_category_weights(
        system_weights_df, st.session_state["custom_cat_weights"]
    )
    active_holdings_df = get_robo_holdings(_custom_raw, rate_df, res)
    active_cat_weights = st.session_state["custom_cat_weights"]
else:
    active_holdings_df = holdings_df
    active_cat_weights = model_weights

active_rebalance = rebalance_check(active_holdings_df)

st.set_page_config(page_icon="💼", layout="wide")
st.title("💼 Robo Advisor")
tab1, tab2 = st.tabs(
    [
        "Recommended Portfolio",
        "Current Portfolio",
    ]
)
with tab1:

    st.markdown("### Recommended Portfolio")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Risk Preference: {risk_preference}")
    with col2:
        st.write(f"Total Investment Value: ${total_investment}")

    col3, col4, col5, col6 = st.columns(4)
    with col3:
        st.write(f"Bond: {active_cat_weights['Bond']*100:.2f}%")
    with col4:
        st.write(f"Broad Market: {active_cat_weights['Market']*100:.2f}%")
    with col5:
        st.write(f"Sector: {active_cat_weights['Sector']*100:.2f}%")
    with col6:
        st.write(f"Commodity: {active_cat_weights['Commodity']*100:.2f}%")

    has_sector = model_weights["Sector"] > 0
    has_commodity = model_weights["Commodity"] > 0
    with st.expander("Customise Category Allocation"):
        st.caption("Adjust the category weights below. Values must sum to 100%.")
        default = st.session_state.get("custom_cat_weights", model_weights)
        cc1, cc2, cc3, cc4 = st.columns(4)
        bond_pct = cc1.number_input(
            "Bond (%)",
            min_value=0,
            max_value=100,
            step=1,
            value=int(round(default["Bond"] * 100)),
        )
        market_pct = cc2.number_input(
            "Broad Market (%)",
            min_value=0,
            max_value=100,
            step=1,
            value=int(round(default["Market"] * 100)),
        )
        sector_pct = cc3.number_input(
            "Sector (%)",
            min_value=0,
            max_value=100,
            step=1,
            value=int(round(default["Sector"] * 100)),
            disabled=not has_sector,
        )
        commodity_pct = cc4.number_input(
            "Commodity (%)",
            min_value=0,
            max_value=100,
            step=1,
            value=int(round(default["Commodity"] * 100)),
            disabled=not has_commodity,
        )
        total_pct = bond_pct + market_pct + sector_pct + commodity_pct
        if total_pct == 100:
            st.success(f"Total: {total_pct}%")
        else:
            st.warning(f"Total: {total_pct}% — must equal 100% to apply.")
        btn_col1, btn_col2, _ = st.columns([1, 1, 6])
        if btn_col1.button("Apply", type="primary", disabled=total_pct != 100):
            new_weights = {
                "Bond": bond_pct / 100,
                "Market": market_pct / 100,
                "Sector": sector_pct / 100,
                "Commodity": commodity_pct / 100,
            }
            st.session_state["custom_cat_weights"] = new_weights
            save_custom_weights(new_weights)
            st.rerun()
        if btn_col2.button("Reset to Recommended"):
            st.session_state.pop("custom_cat_weights", None)
            clear_custom_weights()
            st.rerun()

    optimised_fig = px.pie(active_holdings_df, values="Weight", names="Asset")
    optimised_fig.update_traces(
        hovertemplate="Asset=%{label}<br>Weight=%{value}<extra></extra>",
        textfont_size=16,
    )
    optimised_fig.update_layout(legend_font_size=16)

    st.plotly_chart(optimised_fig, key="optimised_chart")
    st.markdown("### Detailed Allocation")
    holdings_display = active_holdings_df[
        ["Asset", "Weight", "Amount to buy", "Shares to buy"]
    ].copy()
    holdings_display["Weight"] *= 100
    holdings_display.columns = ["Asset", "Weight (%)", "Amount to buy", "Shares to buy"]
    holdings_display = holdings_display.round(2)
    st.dataframe(holdings_display, hide_index=True)

    st.markdown("### Historical Returns")
    returns = historical_return(tickers=active_holdings_df["Asset"].tolist())
    active_holdings_indexed = active_holdings_df.set_index("Asset")
    daily_return = returns[active_holdings_indexed.index].dot(
        active_holdings_indexed[["Weight"]]
    )
    period = st.pills(
        "Time period",
        ["1W", "MTD", "1M", "3M", "YTD", "1Y", "5Y"],
        key="value",
        default="5Y",
    )
    daily_return.index = daily_return.index.date
    start = daily_return.index.min()
    start = adjust_period(start, period)
    daily_return = daily_return[daily_return.index >= start]
    daily_return = daily_return.reset_index(names=["Date"])
    daily_return.columns = ["Date", "Daily Return"]
    daily_return["Daily Return"] = (
        (1 + daily_return["Daily Return"]).cumprod() - 1
    ) * 100
    daily_return = daily_return.round(2)

    if len(daily_return) > 0:
        period_return = daily_return.iloc[-1]["Daily Return"]
    else:
        period_return = 0
    if period_return < 0:
        st.markdown(f"### Total return {RETURN_TEXT[period]}: :red[{period_return}%]")
    else:
        st.markdown(f"### Total return {RETURN_TEXT[period]}: :green[{period_return}%]")

    base = alt.Chart(daily_return.reset_index()).encode(
        x=alt.X("Date:T", title="Date"),
        y=alt.Y(
            "Daily Return:Q",
            title="Historical Return of the Optimised Portfolio",
        ),
    )
    tooltips = [
        alt.Tooltip("Date:T", title="Date"),
        alt.Tooltip("Daily Return:N", title="Daily Return"),
    ]
    title = "Historical Return"
    chart = create_chart(daily_return, "Date", base, tooltips, title)
    st.altair_chart(chart, use_container_width=True)

with tab2:
    col7, col8, col9 = st.columns(3)
    with col7:
        st.markdown(f"#### Initial Investment: $ {total_investment:.2f}")
    with col8:
        st.markdown(
            f"#### Current Value: $ {active_holdings_df['Market Value'].sum():.2f}"
        )
    with col9:
        total_p_and_l = active_holdings_df["Unrealised P&L"].sum()
        if total_p_and_l < 0:
            st.markdown(f"#### Unrealized P&L: :red[${total_p_and_l:,.2f}]")
        else:
            st.markdown(f"#### Unrealized P&L: :green[${total_p_and_l:,.2f}]")
    if active_rebalance:
        st.warning("Rebalancing available")
        if st.button("Show rebalance", type="primary"):
            rebalance_dialog(
                active_holdings_df[
                    ["Asset", "Current Weight", "Market Value", "Current Price"]
                ],
                active_holdings_df,
            )
    current_holdings = active_holdings_df.copy()
    current_holdings = current_holdings[
        [
            "Asset",
            "Weight",
            "Current Weight",
            "Base Current Price",
            "Amount to buy",
            "Market Value",
            "Unrealised P&L",
        ]
    ]
    current_holdings.columns = [
        "Asset",
        "Target Weight",
        "Current Weight",
        "Current Price",
        "Cost Basis",
        "Market Value",
        "Unrealised P&L",
    ]
    st.dataframe(current_holdings, hide_index=True)
