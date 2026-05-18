import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import quantstats as qs
import seaborn as sns
import streamlit as st

from const import BENCHMARKS, BENCHMARKS_INDEX, CURRENCY_SIGN_MAP
from helpers import (
    adjust_period,
    base_currency_format,
    color,
    format_series,
    get_start_date,
    period_select_box,
)
from src.holding import get_holdings, get_portfolio_value, portfolio_daily_return
from src.risk_analysis_src import (
    factor_analysis,
    generate_report,
    get_benchmarks_volatility,
    get_betas,
    get_corr_matrix,
    get_returns,
    get_volatility,
)

st.set_page_config(page_icon="⚠️", layout="wide")
qs.extend_pandas()
cache_key = st.session_state.get("cache_key", "v1")

# Main page content
st.title("⚠️ Risk Analysis Tools")

# Calculating the weights of holdings in portfolio
holdings = get_holdings()
holdings.rename(columns={"Symbol": "symbol"}, inplace=True)
holdings = holdings.sort_values(by="symbol")
total_value = holdings["Market Value"].sum()
holdings = holdings[["symbol", "Weight", "Market Value"]]
symbols = holdings["symbol"].unique().tolist()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "Volatility",
        "Beta",
        "Drawdown",
        "Value-at-risk (VaR)",
        "Correlation Analysis",
        "Factor Analysis",
        "Comprehensive Report",
    ]
)

# Volatility
with tab1:
    period = period_select_box(1, 5)
    st.markdown("### Individual Stocks Volatility (%)")

    indv_returns = get_returns(symbols, period=period)
    indv_volatility = get_volatility(indv_returns)
    indv_volatility = format_series(indv_volatility)

    indv_volatility.name = "Volatility (%)"
    indv_volatility.index.name = "symbol"
    indv_volatility.reset_index()

    holdings_volatility = holdings[["symbol", "Weight"]]
    final_indv_volatility = pd.merge(
        indv_volatility, holdings_volatility, on="symbol", how="inner"
    )
    final_indv_volatility["Weight"] = round(final_indv_volatility["Weight"] * 100, 2)
    final_indv_volatility.columns = ["Symbol", "Volatility (%)", "Weight (%)"]
    st.dataframe(final_indv_volatility, hide_index=True)

    w = holdings_volatility["Weight"].to_numpy(copy=True).reshape(-1, 1)
    C = indv_returns.cov().values
    port_vol = (np.sqrt(w.T @ C @ w) * np.sqrt(252)).item()

    st.markdown(f"###  Portfolio Volatility: {port_vol * 100:.2f}%")

    st.markdown("### Benchmarks Volatility (%)")
    benchmark_volatility = get_benchmarks_volatility(period=period)
    benchmark_volatility.name = "Volatility (%)"
    benchmark_volatility.index = BENCHMARKS.keys()
    benchmark_volatility.index.name = "Benchmark"
    benchmark_volatility = format_series(benchmark_volatility)
    st.dataframe(benchmark_volatility.reset_index(), hide_index=True)

# Beta
with tab2:
    period = period_select_box(2, 6)
    st.markdown("### Individual Stocks Beta")

    indv_returns = get_returns(symbols, period=period, interval="1mo")
    benchmark_returns = get_returns(
        list(BENCHMARKS_INDEX.values()), period=period, interval="1mo"
    )

    betas = get_betas(indv_returns, benchmark_returns)
    beta_df = holdings[["symbol", "Weight"]]

    df = pd.merge(beta_df, betas, on="symbol", how="inner")
    df["Weight"] = round(df["Weight"] * 100, 2)
    df.columns = ["Symbol", "Weight (%)", "Beta"]
    df = df[["Symbol", "Beta", "Weight (%)"]]
    st.dataframe(df, hide_index=True)

    portfolio_beta = (df["Beta"] * (df["Weight (%)"] / 100)).sum()
    st.markdown(f"### Portfolio Beta: {portfolio_beta:.2f}")

# Maximum drawdown
with tab3:
    period = period_select_box(3, 5)
    st.markdown("### Individual Stocks Maximum Drawdown (%)")
    indv_returns = get_returns(symbols, period)
    drawdown = indv_returns.max_drawdown()
    drawdown.name = "Maximum Drawdown (%)"
    drawdown.index.name = "Symbol"
    drawdown = format_series(drawdown)
    drawdown.sort_values(inplace=True)
    st.dataframe(drawdown.reset_index(), hide_index=True)

    max_drawdown_df = holdings.copy()
    max_drawdown_df.set_index("symbol", inplace=True)
    port_max_drawdown = (drawdown * max_drawdown_df["Weight"]).sum()

    st.markdown(f"###  Portfolio Maximum Drawdown(%): {port_max_drawdown:.2f}%")

    st.markdown("### Drawdown details")
    symbol = st.selectbox("Select symbol", symbols)

    dd_series = indv_returns[symbol].to_drawdown_series()
    st.dataframe(qs.stats.drawdown_details(dd_series), hide_index=True)

# Value-at-risk
with tab4:
    period = period_select_box(4, 5)
    indv_returns = get_returns(symbols, period=period, log=True)
    corr_matrix = get_corr_matrix(indv_returns)

    col1, col2 = st.columns([2, 6])
    with col1:
        base_currency = st.selectbox(
            "Choose base currency",
            ("HKD", "USD", "EUR", "GBP", "JPY", "CNY"),
            width=150,
            format_func=base_currency_format,
        )
    with col2:
        confidence_level = st.slider("Confidence level (%)", 0, 99, 95)

    var_df = get_holdings(base_currency)
    var_df.rename(columns={"Symbol": "symbol"}, inplace=True)
    var_df["var"] = round(
        qs.stats.var(indv_returns, confidence=confidence_level)
        * var_df["Market Value"],
        2,
    )

    st.write("### Individual Stocks daily Value-at-risk (VaR)")
    display_df = var_df[["symbol", "var"]]
    display_df.columns = ["Symbol", "Value-at-risk"]
    st.dataframe(display_df, hide_index=True)

    indv_var = var_df["var"].to_numpy(copy=True).reshape(-1, 1)
    Corr = corr_matrix.values
    port_var = -np.sqrt(indv_var.T @ Corr @ indv_var).item()

    st.write(
        f"### Portfolio daily Value-at-risk (VaR): {CURRENCY_SIGN_MAP[base_currency]} {port_var:.2f}"
    )

# Correlation
with tab5:
    period = period_select_box(5, 6)
    st.write("### Portfolio Correlation Analysis")

    indv_returns = get_returns(symbols, period=period, interval="1mo")

    selected_symbols = st.multiselect(
        "Select assets to include",
        options=symbols,
        default=symbols,
    )

    if len(selected_symbols) < 2:
        st.warning("Please select at least 2 assets to display the correlation matrix.")
    else:
        filtered_returns = indv_returns[selected_symbols]
        corr_matrix = get_corr_matrix(filtered_returns)
        fig = px.imshow(
            corr_matrix,
            text_auto=".2f",
            color_continuous_scale="Reds",
            zmin=-1,
            zmax=1,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, width="stretch")

# Factor analysis
with tab6:
    period = period_select_box(6, 6)
    st.write("### Factor Analysis Results")
    st.write("#### Regression Summary")

    model = factor_analysis(period)
    summary_df = pd.DataFrame(
        {
            "Metric": [
                "Time Period",
                "Observations",
                "R²",
                "Adjusted R²",
                "F-statistic",
                "F-statistic p-value",
            ],
            "Value": [
                period,
                str(int(model.nobs)),
                f"{round(model.rsquared * 100, 2)}%",
                f"{round(model.rsquared_adj * 100, 2)}",
                str(round(model.fvalue, 2)),
                str(round(model.f_pvalue, 2)),
            ],
        }
    )
    st.dataframe(summary_df, hide_index=True)

    st.write("#### Factors")
    factors_df = pd.DataFrame(
        data={
            "Loading": model.params,
            "Std. Error": model.bse,
            "t-stat": model.tvalues,
            "p-value": model.pvalues,
        }
    )
    factors_df.index = [
        "Alpha (α)",
        "Market (Rm-Rf)",
        "Size (SMB)",
        "Value (HML)",
        "Profitability (RMW)",
        "Investment (CMA)",
    ]
    styled = factors_df.style.format("{:.4f}").map(color, subset=["p-value"])
    st.dataframe(styled)

    st.markdown(
        f"#### Annualised Alpha (α): {round(model.params.iloc[0] * 12 * 100, 2)}%"
    )

# Comprehensive report
with tab7:
    period = period_select_box(7, 6)
    start = get_start_date()
    portfolio_value_df = get_portfolio_value(symbols, start)
    start = adjust_period(start, period)
    portfolio_value_df = portfolio_value_df[portfolio_value_df.index >= start]

    portfolio_return = portfolio_daily_return(portfolio_value_df)
    selected_benchmark = st.selectbox(
        "Select a benchmark for comparison",
        options=BENCHMARKS.keys(),
    )
    output_path = "report.html"

    if st.button("Generate report"):
        with st.spinner("Generating comprehensive report..."):
            generate_report(
                portfolio_return,
                BENCHMARKS[selected_benchmark],
                output_path,
            )
        with open(output_path, "rb") as f:
            st.download_button(
                label="Download report (HTML)",
                data=f,
                file_name="comprehensive_report.html",
                mime="text/html",
                type="primary",
            )
