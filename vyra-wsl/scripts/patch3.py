"""Patch 3: get_fundamentals crypto-aware - evita o 404 do yfinance."""
path = "/home/francfrancisco/vyra-ia/venv/lib/python3.14/site-packages/tradingagents/dataflows/y_finance.py"

with open(path) as f:
    code = f.read()

old = '''    try:
        ticker_obj = yf.Ticker(ticker.upper())
        info = ticker_obj.info

        if not info:
            return f"No fundamentals data found for symbol '{ticker}'"'''

new = '''    # PATCH 3: cryptocurrencies have no corporate fundamentals
    if "-USD" in ticker.upper() or "-EUR" in ticker.upper():
        return (
            f"N/A: {ticker} is a cryptocurrency, not a company. "
            "Corporate fundamentals (revenue, earnings, balance sheet) do not exist. "
            "For crypto, relevant 'fundamental' factors are: on-chain metrics, "
            "adoption trends, ETF flows, and macro conditions. "
            "Note this in your report and rely on other analysts' data."
        )

    try:
        ticker_obj = yf.Ticker(ticker.upper())
        info = ticker_obj.info

        if not info:
            return f"No fundamentals data found for symbol '{ticker}'"'''

if old not in code:
    print("ERRO: padrao nao encontrado. NADA alterado.")
else:
    code = code.replace(old, new)
    with open(path, "w") as f:
        f.write(code)
    print("PATCH 3 APLICADO COM SUCESSO!")
