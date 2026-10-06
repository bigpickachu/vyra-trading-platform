"""Teste do Kronos: eu busco velas da Binance, o Kronos prevê as próximas 24."""
import pandas as pd
import requests
from model import Kronos, KronosTokenizer, KronosPredictor

PRED_LEN = 24

# 1. EU busco os dados (o Kronos recebe — não vai a lado nenhum)
print("A buscar velas do BTC à Binance...")
raw = requests.get(
    "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=400",
    timeout=30,
).json()

df = pd.DataFrame(raw, columns=["open_time","open","high","low","close","volume",
                                 "close_time","amount","trades","taker_base","taker_quote","ignore"])
df["timestamps"] = pd.to_datetime(df["open_time"].astype(int), unit="ms")
for c in ["open","high","low","close","volume","amount"]:
    df[c] = df[c].astype(float)
df = df[["timestamps","open","high","low","close","volume","amount"]]

# A última vela ainda está a formar-se (a hora não fechou) — removo-a
df = df.iloc[:-1].reset_index(drop=True)
print(f"{len(df)} velas completas. Ultima: {df.timestamps.iloc[-1]}")

# 2. Carregar modelo (combinação exata do exemplo oficial)
print("A carregar o Kronos (ja esta em cache, demora ~20 segundos)...")
tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)

# 3. Preparar dados (mesmas colunas do exemplo oficial)
x_df = df[["open","high","low","close","volume","amount"]]
x_timestamp = df["timestamps"]

# CORREÇÃO: envolver o date_range em pd.Series() — o Kronos precisa
# de receber as datas como coluna (Series), não como índice
y_timestamp = pd.Series(pd.date_range(
    x_timestamp.iloc[-1] + pd.Timedelta(hours=1),
    periods=PRED_LEN, freq="h"
))

# 4. Prever (parâmetros exatos do exemplo oficial)
print("A prever 24 velas no CPU...")
pred_df = predictor.predict(
    df=x_df,
    x_timestamp=x_timestamp,
    y_timestamp=y_timestamp,
    pred_len=PRED_LEN,
    T=1.0,
    top_p=0.9,
    sample_count=1,
    verbose=True,
)

# 5. Ver o veredicto
ultimo = float(df["close"].iloc[-1])
futuro = float(pred_df["close"].iloc[-1])
print("\n" + "=" * 55)
print(f"Ultimo preco real   : ${ultimo:,.2f}")
print(f"Previsto daqui a 24h: ${futuro:,.2f}")
print(f"Variacao prevista   : {(futuro/ultimo - 1)*100:+.2f}%")
print("=" * 55)
print("\nPrimeiras previsoes (close):")
print(pred_df["close"].head())
