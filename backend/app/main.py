from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx
import json
import os
import time

from app.db.database import get_db
from app.models.ohlcv import OHLCV
from app.core.backtester import Backtester

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
        query = db.query(OHLCV).filter(
            OHLCV.symbol == symbol,
            OHLCV.timeframe == interval
        ).order_by(OHLCV.time.asc()).limit(limit)
        
        candles_db = query.all()
        
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
        "cooldown_seconds": 600
    }
    
    save_state(new_state)
    print(f"Bot iniciado: {symbol} | Direção: {direction}")
    return {"status": "started", "state": new_state}

@app.post("/api/paper-trade/stop")
def stop_paper_trade():
    clear_state()
    print("Bot parado e estado limpo")
    return {"status": "stopped"}

@app.get("/api/paper-trade/tick")
async def paper_trade_tick():
    state = load_state()
    
    if not state or not state.get("active"):
        return {"active": False}

    if state.get("start_time") and (time.time() - state["start_time"]) < 20:
        return {
            "active": True,
            "state": state,
            "metrics": {"total_trades": 0, "winning_trades": 0, "losing_trades": 0, "win_rate": 0, "profit_factor": 0, "avg_win": 0, "avg_loss": 0, "max_drawdown_pct": 0, "total_pnl": 0, "current_streak": 0},
            "market": {"price": 0, "rsi": 0, "action": "INITIALIZING", "signals": {}}
        }

    symbol = state["symbol"]
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50")
            klines = resp.json()
    except Exception:
        return {"error": "Falha Binance"}

    closes = [float(k[4]) for k in klines]
    current_price = closes[-1]
    current_time = int(klines[-1][0] / 1000)

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
            if rsi < state["rsi_buy_threshold"]: action = "BUY"

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
        "market": {"price": current_price, "rsi": round(rsi, 2), "action": action, "signals": {"ema": "BULLISH" if ema_bullish else "BEARISH", "rsi": "OK" if rsi < state["rsi_buy_threshold"] else "HIGH"}}
    }