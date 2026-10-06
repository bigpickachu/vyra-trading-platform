"""Patch: converte o ValueError em mensagem amigavel ao agente."""
path = "/home/francfrancisco/vyra-ia/venv/lib/python3.14/site-packages/tradingagents/dataflows/y_finance.py"

with open(path) as f:
    code = f.read()

old = '''    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )'''

new = '''    if indicator not in best_ind_params:
        valid_indicators = list(best_ind_params.keys())
        return (
            f"ERROR: Indicator '{indicator}' is not supported. "
            f"Valid indicators: {valid_indicators}. "
            "Please retry the tool call using ONLY indicators from this list."
        )'''

if old not in code:
    print("ERRO: padrao nao encontrado - o ficheiro pode ter mudado. NADA foi alterado.")
else:
    code = code.replace(old, new)
    with open(path, "w") as f:
        f.write(code)
    print("PATCH APLICADO COM SUCESSO!")
