from curl_cffi import requests

BASE_CURRENCIES = ["HKD", "USD", "EUR", "GBP", "JPY", "CNY"]
CURRENCY_SIGN_MAP = {
    "HKD": "HK$",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "CN¥",
}
PERIODS = ["1W", "MTD", "1M", "3M", "YTD", "1Y", "All"]
MARKETS = [
    "Hong Kong",
    "US",
    "World",
    "UK",
    "Europe",
    "Japan",
    "China",
    "Conservative(70/30)",
    "Moderate(60/40)",
    "Growth(40/60)",
    "Aggressive(20/80)",
]
MARKETS_MAP = {
    "Hong Kong": "2800.HK",
    "US": "SPY",
    "World": "VT",
    "UK": "ISF.L",
    "Europe": "EXW1.DE",
    "Japan": "1329.T",
    "China": "2823.HK",
    "Conservative(70/30)": "AOK",
    "Moderate(60/40)": "AOM",
    "Growth(40/60)": "AOR",
    "Aggressive(20/80)": "AOA",
}
RETURN_TEXT = {
    "1W": "in the past week",
    "MTD": "this month",
    "1M": "in the past month",
    "3M": "in the past three months",
    "YTD": "this year",
    "1Y": "in the past year",
    "5Y": "in the past five years",
    "All": "since inception",
}
BENCHMARKS = {
    "Hang Seng Index": "2800.HK",
    "S&P 500": "SPY",
    "STOXX Europe 50": "EXSA.DE",
    "FTSE 100": "ISF.L",
    "Nikkei 225": "1329.T",
    "SSE Composite Index": "2823.HK",
}
BENCHMARKS_INDEX = {
    "Hang Seng Index": "^HSI",
    "S&P 500": "^GSPC",
    "STOXX Europe 50": "^STOXX50E",
    "FTSE 100": "^FTSE",
    "Nikkei 225": "^N225",
    "SSE Composite Index": "000001.SS",
}
SESSION = requests.Session(impersonate="chrome")
HK_MAX = 9999
US_MAX = 19161
SECTOR_MAP = {
    "": 0,
    "Healthcare": 1,
    "Financial Services": 2,
    "Technology": 3,
    "Industrials": 4,
    "Consumer Cyclical": 5,
    "Basic Materials": 6,
    "Communication Services": 7,
    "Real Estate": 8,
    "Energy": 9,
    "Consumer Defensive": 10,
    "Utilities": 11,
}

CLASS_MAP = {"Equity": 1, "Bond": 2, "Commodity": 3, "Cryptocurrency": 4, "": 1}

CURRENCIES = [
    ("HKD=X", "USD/HKD"),
    ("EUR=X", "USD/EUR"),
    ("GBP=X", "USD/GBP"),
    ("JPY=X", "USD/JPY"),
    ("CNY=X", "USD/CNY"),
]
SECTOR_CASE_MAP = {
    "realestate": "Real Estate",
    "consumer_cyclical": "Consumer Cyclical",
    "basic_materials": "Basic Materials",
    "consumer_defensive": "Consumer Defensive",
    "technology": "Technology",
    "communication_services": "Communication Services",
    "financial_services": "Financial Services",
    "utilities": "Utilities",
    "industrials": "Industrials",
    "energy": "Energy",
    "healthcare": "Healthcare",
}
