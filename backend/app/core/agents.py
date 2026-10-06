"""Motor multi-agente — invocado via subprocess (venv isolado)."""
import subprocess
import json

RUNNER = "/home/francfrancisco/vyra-ia/run_agents_teste.py"
PYTHON = "/home/francfrancisco/vyra-ia/venv/bin/python"


def correr_agentes(symbol: str, trade_date: str) -> dict:
    """Corre os agentes num processo isolado e devolve o veredicto."""
    r = subprocess.run(
        [PYTHON, RUNNER, symbol, trade_date],
        capture_output=True, text=True, timeout=2400,
    )
    for linha in r.stdout.splitlines():
        if "AGENT_RESULT_JSON:" in linha:
            payload = linha.split("AGENT_RESULT_JSON:", 1)[1]
            return json.loads(payload)

    cauda_erro = (r.stderr or "")[-400:]
    raise RuntimeError(f"Agentes sem resultado (exit {r.returncode}): {cauda_erro}")
