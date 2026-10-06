"""Patch 2: disciplina de tool calls no market_analyst.md."""
path = "/home/francfrancisco/vyra-ia/venv/lib/python3.14/site-packages/tradingagents/agents/prompts/market_analyst.md"

with open(path) as f:
    code = f.read()

old = "Select indicators that provide diverse and complementary information."

new = (
    "STRICT TOOL BUDGET (MANDATORY RULE): You may make AT MOST 3 tool calls in total. "
    "Plan ahead: call get_stock_data ONCE, then call get_indicators at most TWICE, "
    "requesting ALL the indicators you need in a SINGLE call (pass the full list at once). "
    "After the 3rd tool call you MUST stop calling tools and immediately write your final report "
    "with the data you already have. NEVER say you need more data. "
    "Always use look_back_days of 15 or less to keep responses compact. "
    "Select indicators that provide diverse and complementary information."
)

if old not in code:
    print("ERRO: padrao nao encontrado. NADA foi alterado.")
else:
    code = code.replace(old, new)
    with open(path, "w") as f:
        f.write(code)
    print("PATCH 2 APLICADO COM SUCESSO!")
