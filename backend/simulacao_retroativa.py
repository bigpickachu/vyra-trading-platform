"""Simulacao retroativa: gera indicacoes historicas no Firestore.
Fonte: 'backtest' - nao interfere no experimento em tempo real."""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import requests

from app.core.firebase import gravar_indicacao, atualizar_resultado, get_firestore

SYMBOL = "BTCUSDT"
DIAS = int(os.getenv("DIAS", "30"))
FONTE_SIM = os.getenv("FONTE_SIM", "backtest")
RSI_LIMIAR = 45
BANDA = 0.3          # % para ACERTOU/ERROU (igual ao worker!)
FREQUENCIA_FORECAST = 7   # previsao do kronos a cada N dias (custo CPU)

# ---------- dados ----------
print("A buscar velas da Binance...")
velas = []
fim = int(time.time() * 1000)
inicio = fim - DIAS * 24 * 3600 * 1000
while inicio < fim:
    r = requests.get(
        f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval=1d&limit=1000&startTime={inicio}&endTime={fim}",
        timeout=30,
    ).json()
    if not r:
        break
    velas += r
    inicio = int(r[-1][0]) + 1
    time.sleep(0.3)

fechamentos = [float(v[4]) for v in velas]
tempos = [int(v[0]) // 1000 for v in velas]
print(f"{len(fechamentos)} dias de dados")


def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    ganhos, perdas = [], []
    for i in range(1, len(prices)):
        mudanca = prices[i] - prices[i - 1]
        ganhos.append(max(0, mudanca))
        perdas.append(max(0, -mudanca))
    media_g = sum(ganhos[-period:]) / period
    media_p = sum(perdas[-period:]) / period
    if media_p == 0:
        return 100
    return 100 - (100 / (1 + media_g / media_p))


# ---------- loop de decisao ----------
from app.core.forecaster import get_forecaster

forecaster = get_forecaster()
print("Modelo Kronos carregado!")

# a tendencia do kronos, atualizada 1x por semana (custo CPU)
trend_atual = 0
dias_desde_ultima_previsao = FREQUENCIA_FORECAST  # forca prever no dia 1

indicacoes_criadas = 0

# percorre os dias, deixando 1 dia de "futuro" para o veredicto
# começa no dia 14 para o RSI ter historico suficiente
for i in range(14, len(fechamentos) - 1):
    preco_hoje = fechamentos[i]
    preco_amanha = fechamentos[i + 1]
    data_dia = datetime.fromtimestamp(tempos[i], tz=timezone.utc)

    # kronos: so prevê a cada N dias (custo CPU)
    if dias_desde_ultima_previsao >= FREQUENCIA_FORECAST:
        print(f"[{data_dia.date()}] A prever com Kronos...")
        velas_hora = requests.get(
            f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval=1h&limit=400&endTime={tempos[i] * 1000}",
            timeout=30,
        ).json()
        candles_k = [{"time": int(k[0]) // 1000, "open": float(k[1]), "high": float(k[2]),
                      "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                     for k in velas_hora]
        fc = forecaster.forecast(candles_k, SYMBOL)
        trend_atual = fc["trend"]
        dias_desde_ultima_previsao = 0
        print(f"   trend: {trend_atual}")
    dias_desde_ultima_previsao += 1

    # o RSI usa os closes ate hoje (sem olhar o futuro!)
    rsi = calc_rsi(fechamentos[:i + 1])

    # confluencia: igual ao bot em tempo real!
    if rsi < RSI_LIMIAR and trend_atual == 1:
        variacao = round((preco_amanha - preco_hoje) / preco_hoje * 100, 2)
        if variacao >= BANDA:
            resultado = "ACERTOU"
        elif variacao <= -BANDA:
            resultado = "ERROU"
        else:
            resultado = "NEUTRO"

        doc_id = gravar_indicacao(SYMBOL, "BUY", preco_hoje, FONTE_SIM)
        atualizar_resultado(doc_id, preco_amanha, resultado)

        # corrige o timestamp para o dia simulado (nao o dia de hoje!)
        get_firestore().collection("indicacoes").document(doc_id).update({
            "timestamp": datetime.fromtimestamp(tempos[i], tz=timezone.utc).isoformat()
        })

        indicacoes_criadas += 1
        print(f"[{data_dia.date()}] BUY @ {preco_hoje:.2f} -> {variacao:+.2f}% -> {resultado}")
    else:
        # B1 (critica aceite): dias SEM sinal também ficam registados.
        # Sem isto, a precisão seria condicional (só dias de ação) e os
        # vetos invisíveis — com isto há precisão global = acertos/dias.
        doc_id = gravar_indicacao(SYMBOL, "VETO", preco_hoje, FONTE_SIM)
        atualizar_resultado(doc_id, preco_amanha, "SEM SINAL")
        get_firestore().collection("indicacoes").document(doc_id).update({
            "timestamp": datetime.fromtimestamp(tempos[i], tz=timezone.utc).isoformat()
        })

print("=" * 50)
print(f"Simulacao completa: {indicacoes_criadas} indicacoes gravadas!")
