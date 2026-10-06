"""Previsao de velas com o Kronos, com cache por vela."""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent))

from model import Kronos, KronosTokenizer, KronosPredictor

PRED_LEN = 24


class Forecaster:
    _instance = None

    def __init__(self):
        print("[FORECASTER] A carregar modelo Kronos...")
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        self.predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
        self._cache_key = None
        self._cache_trend = None
        self._cache_series = None
        print("[FORECASTER] Modelo pronto")

    def forecast(self, candles, symbol="BTCUSDT"):
        """Recebe velas da binance e devolve trend (+1/-1) e a serie prevista.
        So recalcula quando entra uma vela nova."""
        if not candles or len(candles) < 100:
            raise ValueError(f"Poucas velas: {len(candles)} (minimo 100)")

        chave = f"{symbol}_{candles[-1]['time']}"
        if chave == self._cache_key:
            return {"trend": self._cache_trend, "series": self._cache_series, "cached": True}

        df = pd.DataFrame(candles)
        df["amount"] = df["close"] * df["volume"]
        df["timestamps"] = pd.to_datetime(df["time"], unit="s")
        df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]].iloc[:-1].reset_index(drop=True)

        x_df = df[["open", "high", "low", "close", "volume", "amount"]]
        y_time = pd.Series(pd.date_range(
            df["timestamps"].iloc[-1] + pd.Timedelta(hours=1),
            periods=PRED_LEN, freq="h"
        ))

        pred = self.predictor.predict(
            df=x_df, x_timestamp=df["timestamps"], y_timestamp=y_time,
            pred_len=PRED_LEN, T=1.0, top_p=0.9, sample_count=1, verbose=False,
        )

        ultimo = float(df["close"].iloc[-1])
        futuro = float(pred["close"].iloc[-1])
        trend = 1 if futuro > ultimo else -1

        # o primeiro ponto ancora a previsao ao ultimo preco real
        series = [{"time": candles[-1]["time"], "value": round(ultimo, 2)}]
        for ts, row in pred.iterrows():
            series.append({"time": int(ts.timestamp()), "value": round(float(row["close"]), 2)})

        self._cache_key = chave
        self._cache_trend = trend
        self._cache_series = series

        return {"trend": trend, "series": series, "cached": False}


def get_forecaster():
    if Forecaster._instance is None:
        Forecaster._instance = Forecaster()
    return Forecaster._instance
