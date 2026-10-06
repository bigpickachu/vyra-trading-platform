"""Runner FALSO — simula o output para testar o pipeline sem gastar quota."""
import sys
import json

ticker = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"

print("agentes a simular...")
print("AGENT_RESULT_JSON:" + json.dumps({
    "symbol": ticker,
    "trade_date": "2026-09-14",
    "decision": "SELL (teste do pipeline)",
}))

