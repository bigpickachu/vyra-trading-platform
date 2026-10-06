from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx
import json
import os
import time
from datetime import datetime, timezone

from app.core.firebase import gravar_indicacao, atualizar_resultado, listar_indicacoes, obter_pendentes, calcular_confianca, get_firestore
from app.core.agents import correr_agentes
from app.core.forecaster import get_forecaster
from app.core.alertas import alertas_checker
from app.db.database import get_db
from app.models.ohlcv import OHLCV
from app.core.backtester import Backtester
from apscheduler.schedulers.asyncio import AsyncIOScheduler

app = FastAPI(title="Vyra Trading API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE_FILE = "bot_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return None

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

@app.get("/api/db/test")
def test_db(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT COUNT(*) FROM ohlcv")).scalar()
        return {"status": "ok", "total_registos": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preco")
async def get_live_price(symbol: str = "BTCUSDT"):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
            data = response.json()
            return {"symbol": symbol, "preco": float(data["price"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.get("/api/candles")
async def get_candles(symbol: str, interval: str, limit: int = 500, db: Session = Depends(get_db)):
    try:
        # tenta o postgres; se nao existir, segue para a binance
        candles_db = []
        try:
            candles_db = db.query(OHLCV).filter(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == interval
            ).order_by(OHLCV.time.desc()).limit(limit).all()
            candles_db.reverse()  # devolve em ordem cronologica (antiga -> nova)
        except Exception as e:
            print(f"[CANDLES] postgres indisponivel: {e}")

        if candles_db:
            return {
                "data": [
                    {
                        "time": int(c.time.timestamp()),
                        "open": float(c.open),
                        "high": float(c.high),
                        "low": float(c.low),
                        "close": float(c.close),
                        "volume": float(c.volume)
                    }
                    for c in candles_db
                ]
            }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
            )
            data = response.json()

            if isinstance(data, list):
                return {
                    "data": [
                        {
                            "time": int(int(k[0]) / 1000),
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5])
                        }
                        for k in data
                    ]
                }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.post("/api/backtest")
async def run_backtest(symbol: str, interval: str, initial_capital: float = 10000, db: Session = Depends(get_db)):
    try:
        query = db.query(OHLCV).filter(
            OHLCV.symbol == symbol,
            OHLCV.timeframe == interval
        ).order_by(OHLCV.time.asc())

        candles_db = query.all()

        if not candles_db:
            return {"error": f"Sem dados para {symbol} {interval}"}

        data = [
            {
                "time": int(c.time.timestamp()),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume)
            }
            for c in candles_db
        ]

        backtester = Backtester(initial_capital=initial_capital)
        backtester.strategy_aggressive_5indicators(data, fast_period=12, slow_period=26, rsi_period=14)

        return backtester.get_results()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.get("/api/paper-trade/status")
def get_paper_trade_status():
    state = load_state()
    if state and state.get("active"):
        return {"active": True, "state": state}
    return {"active": False, "state": None}

@app.post("/api/paper-trade/start")
def start_paper_trade(
    symbol: str = "BTCUSDT",
    capital: float = 10000,
    stop_loss: float = 2.0,
    take_profit: float = 5.0,
    rsi_buy: float = 45.0,
    rsi_sell: float = 55.0,
    direction: str = "LONG"
):
    state = load_state()

    if state and state.get("active"):
        return {"status": "already_running", "state": state}

    new_state = {
        "active": True,
        "symbol": symbol,
        "direction": direction.upper(),
        "initial_capital": float(capital),
        "capital": float(capital),
        "position": 0.0,
        "position_type": "NONE",
        "entry_price": 0.0,
        "trades": [],
        "equity": float(capital),
        "start_time": time.time(),
        "peak_equity": float(capital),
        "max_drawdown_pct": 0.0,
        "win_streak": 0,
        "lose_streak": 0,
        "current_streak": 0,
        "total_pnl": 0.0,
        "stop_loss_pct": float(stop_loss) / 100,
        "take_profit_pct": float(take_profit) / 100,
        "rsi_buy_threshold": float(rsi_buy),
        "rsi_sell_threshold": float(rsi_sell),
        "last_trade_time": None,
        "cooldown_seconds": 600,
        "firebase_doc_id": None
    }

    save_state(new_state)
    print(f"Bot iniciado: {symbol} | Direção: {direction}")
    return {"status": "started", "state": new_state}

@app.post("/api/paper-trade/stop")
def stop_paper_trade():
    clear_state()
    print("Bot parado e estado limpo")
    return {"status": "stopped"}


# ============================================================
# LOGICA DO BOT — chamada pelo endpoint E pelo scheduler
# ============================================================
async def executar_tick():
    state = load_state()

    if not state or not state.get("active"):
        return {"active": False}

    # guard anti-duplicacao: se o ultimo tick foi recente, nao recalcula
    # (o scheduler corre a cada 30s e o frontend pinga a cada 5s)
    agora = time.time()
    ultimo_tick = state.get("last_tick_time")
    if ultimo_tick and (agora - ultimo_tick) < 25:
        return {
            "active": True,
            "state": state,
            "metrics": {"total_trades": 0, "winning_trades": 0, "losing_trades": 0, "win_rate": 0, "profit_factor": 0, "avg_win": 0, "avg_loss": 0, "max_drawdown_pct": 0, "total_pnl": 0, "current_streak": 0},
            "market": {"price": 0, "rsi": 0, "action": "THROTTLED", "kronos_trend": 0, "signals": {}},
            "throttled": True
        }
    state["last_tick_time"] = agora

    if state.get("start_time") and (time.time() - state["start_time"]) < 20:
        return {
            "active": True,
            "state": state,
            "metrics": {"total_trades": 0, "winning_trades": 0, "losing_trades": 0, "win_rate": 0, "profit_factor": 0, "avg_win": 0, "avg_loss": 0, "max_drawdown_pct": 0, "total_pnl": 0, "current_streak": 0},
            "market": {"price": 0, "rsi": 0, "action": "INITIALIZING", "kronos_trend": 0, "signals": {}}
        }

    symbol = state["symbol"]

    # tendencia prevista pelo kronos (vem com cache, quase instantaneo)
    kronos_trend = 0  # 0 = neutro/indisponivel -> bloqueia BUY (disciplina)
    try:
        async with httpx.AsyncClient() as client:
            fr = await client.get(f"http://127.0.0.1:8000/api/forecast?symbol={symbol}", timeout=180)
        if fr.status_code == 200 and "trend" in fr.json():
            kronos_trend = fr.json()["trend"]
    except Exception as e:
        print(f"[KRONOS] indisponivel: {e}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50")
            klines = resp.json()
    except Exception:
        return {"error": "Falha Binance"}

    closes = [float(k[4]) for k in klines]
    current_price = closes[-1]
    current_time = int(time.time())  # relogio real (cooldowns em segundos)

    def calc_rsi(prices, period=14):
        if len(prices) < period + 1: return 50
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calc_ema(prices, period):
        k = 2 / (period + 1)
        ema = [prices[0]]
        for p in prices[1:]:
            ema.append(p * k + ema[-1] * (1 - k))
        return ema[-1]

    ema_fast = calc_ema(closes, 12)
    ema_slow = calc_ema(closes, 26)
    rsi = calc_rsi(closes, 14)
    ema_bullish = ema_fast > ema_slow

    action = "HOLD"
    direction = state["direction"]
    pos_type = state["position_type"]

    last_trade = state.get("last_trade_time")
    cooldown = state.get("cooldown_seconds", 600)

    if last_trade and (current_time - last_trade) < cooldown:
        action = "HOLD"
    else:
        if direction in ["LONG", "BOTH"] and pos_type == "LONG":
            entry = state["entry_price"]
            pnl_pct = (current_price - entry) / entry
            if pnl_pct <= -state["stop_loss_pct"]: action = "STOP_LOSS"
            elif pnl_pct >= state["take_profit_pct"]: action = "TAKE_PROFIT"
            elif rsi > state["rsi_sell_threshold"] or not ema_bullish: action = "SELL"

        if direction in ["LONG", "BOTH"] and pos_type == "NONE" and action == "HOLD":
            if rsi < state["rsi_buy_threshold"] and kronos_trend == 1: action = "BUY"

        if direction in ["SHORT", "BOTH"] and pos_type == "SHORT":
            entry = state["entry_price"]
            pnl_pct = (entry - current_price) / entry
            if pnl_pct <= -state["stop_loss_pct"]: action = "STOP_LOSS"
            elif pnl_pct >= state["take_profit_pct"]: action = "TAKE_PROFIT"
            elif rsi < state["rsi_buy_threshold"] or ema_bullish: action = "COVER"

        if direction in ["SHORT", "BOTH"] and pos_type == "NONE" and action == "HOLD":
            if rsi > state["rsi_sell_threshold"]: action = "SHORT"

    if action == "BUY" and pos_type == "NONE":
        exec_price = current_price * 1.0005
        max_position_value = state["capital"] * 0.10
        qty = max_position_value / exec_price
        if qty > 0:
            state["position"] = qty
            state["position_type"] = "LONG"
            state["entry_price"] = exec_price
            state["capital"] -= max_position_value
            state["last_trade_time"] = current_time
            state["trades"].append({"type": "BUY", "time": current_time, "price": round(exec_price, 2), "quantity": round(qty, 6), "rsi_at_entry": round(rsi, 2), "reason": f"LONG RSI {rsi:.1f}"})

            # Firebase (UC00610): regista a indicacao com a fonte da decisao
            try:
                fonte_fb = "kronos+rsi" if kronos_trend == 1 else "so-rsi"
                doc_id = gravar_indicacao(symbol, "BUY", exec_price, fonte_fb)
                state["firebase_doc_id"] = doc_id
            except Exception as e:
                print(f"[FIREBASE] erro ao gravar: {e}")

            save_state(state)

    elif action in ["SELL", "STOP_LOSS", "TAKE_PROFIT"] and pos_type == "LONG":
        exec_price = current_price * 0.9995
        sell_value = state["position"] * exec_price
        cost_basis = state["position"] * state["entry_price"]
        pnl = sell_value - cost_basis
        pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
        state["capital"] += sell_value
        state["total_pnl"] += pnl
        state["last_trade_time"] = current_time
        state["trades"].append({"type": action, "time": current_time, "price": round(exec_price, 2), "quantity": round(state["position"], 6), "pnl": round(pnl, 2), "pnl_percent": round(pnl_pct, 2), "reason": action})

        # Firebase (UC00610): fecha a indicacao com o resultado
        try:
            if state.get("firebase_doc_id"):
                resultado_fb = "ACERTOU" if pnl > 0 else "ERROU"
                atualizar_resultado(state["firebase_doc_id"], exec_price, resultado_fb)
                state["firebase_doc_id"] = None
        except Exception as e:
            print(f"[FIREBASE] erro ao atualizar: {e}")

        state["position"] = 0
        state["position_type"] = "NONE"
        save_state(state)

    elif action == "SHORT" and pos_type == "NONE":
        exec_price = current_price * 0.9995
        max_position_value = state["capital"] * 0.10
        qty = max_position_value / exec_price
        if qty > 0:
            state["position"] = qty
            state["position_type"] = "SHORT"
            state["entry_price"] = exec_price
            state["capital"] -= max_position_value
            state["last_trade_time"] = current_time
            state["trades"].append({"type": "SHORT", "time": current_time, "price": round(exec_price, 2), "quantity": round(qty, 6), "rsi_at_entry": round(rsi, 2), "reason": f"SHORT RSI {rsi:.1f}"})

            # Firebase (UC00610): regista a indicacao SHORT
            try:
                fonte_fb = "kronos+rsi" if kronos_trend == 1 else "so-rsi"
                doc_id = gravar_indicacao(symbol, "SHORT", exec_price, fonte_fb)
                state["firebase_doc_id"] = doc_id
            except Exception as e:
                print(f"[FIREBASE] erro ao gravar: {e}")

            save_state(state)

    elif action in ["COVER", "STOP_LOSS", "TAKE_PROFIT"] and pos_type == "SHORT":
        exec_price = current_price * 1.0005
        buy_cost = state["position"] * exec_price
        initial_value = state["position"] * state["entry_price"]
        pnl = initial_value - buy_cost
        pnl_pct = (pnl / initial_value) * 100 if initial_value > 0 else 0
        state["capital"] = state["capital"] + (initial_value - buy_cost) + (state["position"] * state["entry_price"])
        state["total_pnl"] += pnl
        state["last_trade_time"] = current_time
        state["trades"].append({"type": action, "time": current_time, "price": round(exec_price, 2), "quantity": round(state["position"], 6), "pnl": round(pnl, 2), "pnl_percent": round(pnl_pct, 2), "reason": action})

        # Firebase (UC00610): fecha a indicacao SHORT
        try:
            if state.get("firebase_doc_id"):
                resultado_fb = "ACERTOU" if pnl > 0 else "ERROU"
                atualizar_resultado(state["firebase_doc_id"], exec_price, resultado_fb)
                state["firebase_doc_id"] = None
        except Exception as e:
            print(f"[FIREBASE] erro ao atualizar: {e}")

        state["position"] = 0
        state["position_type"] = "NONE"
        save_state(state)

    if state["position_type"] == "LONG":
        state["equity"] = state["capital"] + (state["position"] * current_price)
    elif state["position_type"] == "SHORT":
        unrealized_pnl = (state["entry_price"] - current_price) * state["position"]
        state["equity"] = state["capital"] + unrealized_pnl + (state["position"] * state["entry_price"])
    else:
        state["equity"] = state["capital"]

    if state["equity"] > state["peak_equity"]:
        state["peak_equity"] = state["equity"]

    current_drawdown = (state["peak_equity"] - state["equity"]) / state["peak_equity"] * 100
    if current_drawdown > state["max_drawdown_pct"]:
        state["max_drawdown_pct"] = current_drawdown

    total_trades = len([t for t in state["trades"] if t["type"] in ["SELL", "STOP_LOSS", "TAKE_PROFIT", "COVER"]])
    winning_trades = len([t for t in state["trades"] if t["type"] in ["SELL", "STOP_LOSS", "TAKE_PROFIT", "COVER"] and t.get("pnl", 0) > 0])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    avg_win = sum([t["pnl"] for t in state["trades"] if t["type"] in ["SELL", "STOP_LOSS", "TAKE_PROFIT", "COVER"] and t.get("pnl", 0) > 0]) / winning_trades if winning_trades > 0 else 0
    avg_loss = sum([abs(t["pnl"]) for t in state["trades"] if t["type"] in ["SELL", "STOP_LOSS", "TAKE_PROFIT", "COVER"] and t.get("pnl", 0) < 0]) / losing_trades if losing_trades > 0 else 0
    profit_factor = (avg_win * winning_trades) / (avg_loss * losing_trades) if losing_trades > 0 and avg_loss > 0 else 0

    save_state(state)

    return {
        "active": True,
        "state": state,
        "metrics": {"total_trades": total_trades, "winning_trades": winning_trades, "losing_trades": losing_trades, "win_rate": round(win_rate, 2), "profit_factor": round(profit_factor, 2), "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2), "max_drawdown_pct": round(state["max_drawdown_pct"], 2), "total_pnl": round(state["total_pnl"], 2), "current_streak": state["current_streak"]},
        "market": {"price": current_price, "rsi": round(rsi, 2), "action": action, "kronos_trend": kronos_trend, "signals": {"ema": "BULLISH" if ema_bullish else "BEARISH", "rsi": "OK" if rsi < state["rsi_buy_threshold"] else "HIGH"}}
    }


@app.get("/api/paper-trade/tick")
async def paper_trade_tick():
    return await executar_tick()


# ===== Firebase (UC00610) =====
@app.post("/api/firebase/teste")
def firebase_teste():
    """Grava uma indicacao de teste no Firestore e le-a de volta."""
    doc_id = gravar_indicacao(
        symbol="BTCUSDT",
        indicacao="BUY",
        preco_inicio=75990.20,
        fonte="teste-integracao",
    )
    docs = listar_indicacoes(symbol="BTCUSDT", limite=5)
    return {"doc_criado": doc_id, "ultimas_indicacoes": docs}


@app.get("/api/indicacoes")
def get_indicacoes(symbol: str = None, limite: int = 50):
    """Historico de indicacoes (futuro: botao Historico do frontend)."""
    return listar_indicacoes(symbol=symbol, limite=limite)

@app.post("/api/worker/fecho-diario")
async def worker_fecho_diario(symbol: str = None):
    """Avalia indicacoes pendentes contra a cotacao real. Resultado: ACERTOU/ERROU/NEUTRO."""
    pendentes = obter_pendentes(symbol)
    if not pendentes:
        return {"avaliadas": 0, "mensagem": "Sem indicacoes pendentes."}

    precos = {}
    resultados = []

    async with httpx.AsyncClient() as client:
        for doc in pendentes:
            sym = doc.get("symbol")
            if not sym or not doc.get("preco_inicio"):
                continue

            if sym not in precos:
                try:
                    r = await client.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}")
                    precos[sym] = float(r.json()["price"])
                except Exception as e:
                    print(f"[WORKER] falha Binance {sym}: {e}")
                    precos[sym] = None

            preco_fim = precos.get(sym)
            if preco_fim is None:
                continue

            pi = doc["preco_inicio"]
            variacao = round((preco_fim - pi) / pi * 100, 2)

            ind = doc.get("indicacao", "BUY")
            if ind == "SHORT":
                resultado = "ACERTOU" if variacao <= -0.3 else ("ERROU" if variacao >= 0.3 else "NEUTRO")
            else:
                resultado = "ACERTOU" if variacao >= 0.3 else ("ERROU" if variacao <= -0.3 else "NEUTRO")

            try:
                atualizar_resultado(doc["id"], preco_fim, resultado)
                resultados.append({"id": doc["id"], "indicacao": ind,
                                   "preco_inicio": pi, "preco_fim": preco_fim,
                                   "variacao": variacao, "resultado": resultado})
            except Exception as e:
                print(f"[WORKER] erro ao atualizar {doc['id']}: {e}")

    return {"avaliadas": len(resultados), "detalhes": resultados}

# ===== Grau de Confianca (Fase 4) =====
@app.get("/api/confianca")
def get_confianca():
    """Grau de confianca do sistema: precisao geral e por fonte de decisao."""
    return calcular_confianca()

# ===== Kronos Forecaster (Fase 3) =====
@app.get("/api/forecast")
async def get_forecast(symbol: str = "BTCUSDT"):
    """Previsao do kronos para as proximas 24 velas."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=400",
                timeout=30,
            )
            raw = r.json()
        candles = [{"time": int(k[0]) // 1000, "open": float(k[1]), "high": float(k[2]),
                    "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                   for k in raw]
        resultado = get_forecaster().forecast(candles, symbol)
        return resultado
    except Exception as e:
        return {"erro": str(e), "tipo": type(e).__name__}

# ===== Scheduler: autonomia do bot =====
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def arrancar_scheduler():
    scheduler.add_job(executar_tick, "interval", seconds=30, id="tick_bot")
    # Job SEPARADO de alertas (5 min): se rebentar, o tick continua vivo.
    scheduler.add_job(alertas_checker, "interval", minutes=5, id="alertas_checker")
    scheduler.start()
    print("[SCHEDULER] bot autonomo ativo (a cada 30s) + alertas (a cada 5min)")


@app.get("/api/alertas")
def get_alertas(limite: int = 20):
    """Ultimos alertas disparados (colecao separada, nunca toca no tick)."""
    try:
        from app.core.alertas import ultimos_alertas
        return ultimos_alertas(limite)
    except Exception as e:
        return {"erro": str(e)}


@app.on_event("shutdown")
async def parar_scheduler():
    scheduler.shutdown()

# ===== Agentes multi-IA (Fase 3b) =====
estado_agentes = {}


def _tarefa_agentes(symbol: str, trade_date: str):
    """Corre os agentes em background e grava o veredicto no Firestore."""
    try:
        estado_agentes[symbol] = {"status": "a correr"}
        resultado = correr_agentes(symbol, trade_date)
        decisao = resultado.get("decision", "?")
        get_firestore().collection("agent_reports").add({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "decisao": decisao,
            "trade_date": trade_date,
        })
        estado_agentes[symbol] = {"status": "feito", "decisao": decisao}
        print(f"[AGENTES] veredicto gravado: {decisao}")
    except Exception as e:
        estado_agentes[symbol] = {"status": "erro", "erro": str(e)}
        print(f"[AGENTES] erro: {e}")


@app.post("/api/agents/analyze")
def agents_analyze(background_tasks: BackgroundTasks,
                   symbol: str = "BTC-USD", trade_date: str = "2026-09-14"):
    """Dispara a analise multi-agente (em background)."""
    background_tasks.add_task(_tarefa_agentes, symbol, trade_date)
    return {"status": "iniciado", "mensagem": "Agentes a trabalhar"}


@app.get("/api/agents/status/{symbol}")
def agents_status(symbol: str = "BTC-USD"):
    st = estado_agentes.get(symbol, {"status": "idle"})
    docs = get_firestore().collection("agent_reports") \
        .where("symbol", "==", symbol).limit(1).stream()
    ultimo = None
    for d in docs:
        ultimo = d.to_dict()
    return {"estado": st, "ultimo_veredicto": ultimo}