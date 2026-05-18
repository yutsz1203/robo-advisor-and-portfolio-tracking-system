import json
from datetime import date

import streamlit as st

st.set_page_config(page_icon="📝", layout="wide")

Q1_QS_MAP = {
    "Preserve capital": 1,
    "Generate steady income": 2,
    "Grow wealth over time": 3,
    "Pursue higher long-term growth": 4,
    "Maximize returns": 5,
}
Q2_QS_MAP = {
    "Less than 1 year": 1,
    "1-3 years": 2,
    "3-5 years": 3,
    "5-7 years": 4,
    "More than 7 years": 5,
}
Q3_QS_MAP = {
    "Sell to avoid further losses": 1,
    "Reduce exposure": 2,
    "Stay invested": 3,
    "Gradually invest more": 4,
    "Aggressively buy more": 5,
}
Q4_QS_MAP = {
    "Uncomfortable;Prefer stability": 1,
    "Somewhat uncomfortable": 2,
    "Neutral": 3,
    "Comfortable with uncertainty": 4,
    "Comfortable with volatility": 5,
}
Q5_QS_MAP = {
    "Nearly all": 1,
    "More than half": 2,
    "Around one-third": 3,
    "Small portion": 4,
    "Only surplus capital": 5,
}
Q6_QS_MAP = {
    "Low return; Minimal risk": 1,
    "Modest return; Low risk": 2,
    "Blanced return; Balanced risk": 3,
    "High return; High risk": 4,
    "Maximum return, Extreme risk": 5,
}
Q7_QS_MAP = {
    "No experience": 1,
    "Basic familiarity": 2,
    "Actively invest": 3,
    "Advanced understanding": 4,
    "Professional or semi-professional": 5,
}
Q8_QS_MAP = {
    "Scheduled reviews only": 5,
    "Occasional checks": 4,
    "Regular checks": 3,
    "Frequent checks": 2,
    "Stress from fluctuations": 1,
}
Q9_QS_MAP = {
    "Very predictable; Consistency": 1,
    "Mostly predictable; Stability with flexibility": 2,
    "Moderately predictable; Variability": 3,
    "Less predictable; Uncertainty": 4,
    "Highly unpredictable; Vary Outcomes": 5,
}

COMMODITIES_MAP = {
    "Gold": "GLD",
    "Silver": "SLV",
    "Oil": "USO",
    "Industrial Metals": "DBB",
    "Agriculture": "DBA",
    "Broad": "DJP",
    "Bitcoin": "IBIT",
}
COMMODITIES = list(COMMODITIES_MAP.keys())
commodities_checkboxs = [True] * 7

SECTOR_MAP = dict(
    [
        ("Technology", "XLK"),
        ("Financials", "XLF"),
        ("Health Care", "XLV"),
        ("Consumer(Non-Essential)", "XLY"),
        ("Consumer(Essential)", "XLP"),
        ("Industrials", "XLI"),
        ("Energy", "XLE"),
        ("Utilities", "XLU"),
        ("Materials", "XLB"),
        ("Real Estate", "XLRE"),
        ("Communication", "XLC"),
    ]
)
SECTOR = list(SECTOR_MAP.keys())
sector_checkboxs = [True] * 11


def validate(Inv_Q, US, HK, XUS, sector, value):
    if value <= 1:
        return False
    if (
        (None in Inv_Q)
        or not (US or HK or XUS)
        or (sum(x is not None for x in sector) <= 7)
    ):
        return False
    return True


def evaluation(score: int):
    if 9 <= score <= 15:
        return "Capital Preservation"
    if 16 <= score <= 23:
        return "Conservative"
    if 24 <= score <= 31:
        return "Balanced"
    if 32 <= score <= 38:
        return "Growth"
    if 39 <= score <= 45:
        return "Aggressive Growth"


def detect_contradictions(answers, meta):
    scores = {
        "Q1": Q1_QS_MAP[answers["Q1"]],
        "Q3": Q3_QS_MAP[answers["Q3"]],
        "Q4": Q4_QS_MAP[answers["Q4"]],
        "Q6": Q6_QS_MAP[answers["Q6"]],
    }
    pairs = [
        ("Q1", "Q3", "Investment goal", "reaction to a 15% drop"),
        ("Q1", "Q4", "Investment goal", "comfort with risk"),
        ("Q4", "Q6", "Comfort with risk", "portfolio preference"),
        ("Q3", "Q6", "Reaction to a 15% drop", "portfolio preference"),
    ]
    contradictions = []
    for qa, qb, label_a, label_b in pairs:
        if abs(scores[qa] - scores[qb]) >= 2:
            contradictions.append(
                f'**{label_a}** ("{answers[qa]}") conflicts with **{label_b}** ("{answers[qb]}")'
            )
    bitcoin_index = COMMODITIES.index("Bitcoin")
    if meta["commodities"][bitcoin_index] and scores["Q4"] <= 2:
        contradictions.append(
            f'**Bitcoin** is selected but your comfort with risk is low ("{answers["Q4"]}").'
            " Bitcoin is highly volatile and may not suit your risk profile."
        )
    return contradictions


def process_submission(answers, meta):
    score = (
        Q1_QS_MAP[answers["Q1"]]
        + Q2_QS_MAP[answers["Q2"]]
        + Q3_QS_MAP[answers["Q3"]]
        + Q4_QS_MAP[answers["Q4"]]
        + Q5_QS_MAP[answers["Q5"]]
        + Q6_QS_MAP[answers["Q6"]]
        + Q7_QS_MAP[answers["Q7"]]
        + Q8_QS_MAP[answers["Q8"]]
        + Q9_QS_MAP[answers["Q9"]]
    )
    resultScore = evaluation(score)
    st.success(f"Success! Your risk preference is : {resultScore}")

    resultEtf = ["BND"]
    if meta["US"]:
        resultEtf.append("VOO")
    if meta["HK"]:
        resultEtf.append("2800.HK")
    if meta["Global"]:
        resultEtf.append("VXUS")
    for i, checked in enumerate(meta["sectors"]):
        if checked:
            resultEtf.append(SECTOR_MAP[list(SECTOR_MAP.keys())[i]])
    for i, checked in enumerate(meta["commodities"]):
        if checked:
            resultEtf.append(COMMODITIES_MAP[list(COMMODITIES_MAP.keys())[i]])

    result = {
        "risk_preference": resultScore,
        "total_investment": meta["total_invest"],
        "asset_list": resultEtf,
        "created_on": str(date.today()),
    }
    with open("output/risk_assessment_result.json", "w") as f:
        json.dump(result, f, indent=4)


_ = st.title("📝 Risk Assessment")
st.write("Risk Assessment page to evaluate your tolerance and financial goal")
tab1 = st.tabs(["Risk Evaluation"])

with st.form("risk_assessment"):
    st.write("What is your estimated total investment value?")
    total_invest = st.number_input(
        "Investment Value", format="%d", step=1, min_value=1, value=None
    )

    st.write("Which markets to include?")

    checkbox_col = st.columns([1, 1, 1])
    US_checkbox = checkbox_col[0].checkbox("US market")
    HK_checkbox = checkbox_col[1].checkbox("HK market")
    Global_checkbox = checkbox_col[2].checkbox("Global market (exclude US)")

    st.write("Which commodities to include? (Can be empty)")
    checkbox_col2 = st.columns([1, 1, 1, 1])
    for i in range(4):
        commodities_checkboxs[i] = checkbox_col2[i].checkbox(COMMODITIES[i])
    checkbox_col21 = st.columns([1, 1, 1, 1])
    for i in range(4, 7):
        commodities_checkboxs[i] = checkbox_col21[i - 4].checkbox(COMMODITIES[i])

    st.write("Which sectors to include? (Max 3. Can be empty)")
    checkbox_col3 = st.columns([1, 1, 1, 1])
    for i in range(4):
        sector_checkboxs[i] = checkbox_col3[i].checkbox(SECTOR[i])

    checkbox_col4 = st.columns([1, 1, 1, 1])
    for i in range(4, 8):
        sector_checkboxs[i] = checkbox_col4[i - 4].checkbox(SECTOR[i], key=i)
    checkbox_col5 = st.columns([1, 1, 1, 1])
    for i in range(8, 11):
        sector_checkboxs[i] = checkbox_col5[i - 8].checkbox(SECTOR[i])

    Inv_Q1 = st.radio(
        "What is your primary investment goal?",
        Q1_QS_MAP.keys(),
        index=None,
    )

    Inv_Q2 = st.radio(
        "How long do you plan to keep this investment",
        Q2_QS_MAP.keys(),
        index=None,
    )

    Inv_Q3 = st.radio(
        "How would you react if your portfolio drops 15% in a short period due to market volatility?",
        Q3_QS_MAP.keys(),
        index=None,
    )

    Inv_Q4 = st.radio(
        "Which statement best describes your comfort with risk?",
        Q4_QS_MAP.keys(),
        index=None,
    )

    Inv_Q5 = st.radio(
        "What portion of your total savings does this investment represent?",
        Q5_QS_MAP.keys(),
        index=None,
    )

    Inv_Q6 = st.radio(
        "Which portfolio would you feel most comfortable holding?",
        Q6_QS_MAP.keys(),
        index=None,
    )

    Inv_Q7 = st.radio(
        "How familiar are you with investing and financial markets?",
        Q7_QS_MAP.keys(),
        index=None,
    )

    Inv_Q8 = st.radio(
        "How often would you check your investment performance?",
        Q8_QS_MAP.keys(),
        index=None,
    )

    Inv_Q9 = st.radio(
        "How predictable do you want your investment outcomes to be?",
        Q9_QS_MAP.keys(),
        index=None,
    )
    submit_button = st.form_submit_button("Submit")

if submit_button:
    if not validate(
        [Inv_Q1, Inv_Q2, Inv_Q3, Inv_Q4, Inv_Q5, Inv_Q6, Inv_Q7, Inv_Q8, Inv_Q9],
        US_checkbox,
        HK_checkbox,
        Global_checkbox,
        sector_checkboxs,
        total_invest,
    ):
        _ = st.warning("Please fill in the questions accordingly")
    else:
        answers = {
            "Q1": Inv_Q1, "Q2": Inv_Q2, "Q3": Inv_Q3,
            "Q4": Inv_Q4, "Q5": Inv_Q5, "Q6": Inv_Q6,
            "Q7": Inv_Q7, "Q8": Inv_Q8, "Q9": Inv_Q9,
        }
        meta = {
            "US": US_checkbox,
            "HK": HK_checkbox,
            "Global": Global_checkbox,
            "sectors": sector_checkboxs[:],
            "commodities": commodities_checkboxs[:],
            "total_invest": total_invest,
        }
        contradictions = detect_contradictions(answers, meta)
        if contradictions:
            st.session_state["pending_answers"] = answers
            st.session_state["pending_meta"] = meta
            st.session_state["pending_contradictions"] = contradictions
        else:
            process_submission(answers, meta)

if st.session_state.get("pending_contradictions"):
    st.warning(
        "Some of your answers appear to contradict each other:\n\n"
        + "\n".join(f"- {c}" for c in st.session_state["pending_contradictions"])
        + "\n\nPlease review your answers or confirm to proceed."
    )
    confirm_col, revise_col, _ = st.columns([2, 2, 8])
    if confirm_col.button("Confirm & Submit", type="primary"):
        process_submission(
            st.session_state.pop("pending_answers"),
            st.session_state.pop("pending_meta"),
        )
        st.session_state.pop("pending_contradictions")
    if revise_col.button("Revise Answers"):
        st.session_state.pop("pending_contradictions")
        st.session_state.pop("pending_answers")
        st.session_state.pop("pending_meta")
        st.rerun()
