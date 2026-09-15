import pandas as pd
import numpy as np
from typing import List, Dict, Any

class Backtester:
    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0
        self.entry_price = 0
        self.trades = []
        self.equity_curve = []
        
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        ema = [prices[0]]
        multiplier = 2 / (period + 1)
        for price in prices[1:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema
    
    def calculate_macd(self, prices: List[float]) -> tuple:
        ema12 = self.calculate_ema(prices, 12)
        ema26 = self.calculate_ema(prices, 26)
        macd_line = [ema12[i] - ema26[i] for i in range(len(prices))]
        signal_line = self.calculate_ema(macd_line, 9)
        histogram = [macd_line[i] - signal_line[i] for i in range(len(prices))]
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> tuple:
        if len(prices) < period:
            return prices, prices, prices
        
        sma = []
        upper = []
        lower = []
        
        for i in range(len(prices)):
            if i < period - 1:
                sma.append(prices[i])
                upper.append(prices[i])
                lower.append(prices[i])
            else:
                window = prices[i-period+1:i+1]
                mean = sum(window) / period
                variance = sum((x - mean) ** 2 for x in window) / period
                std = variance ** 0.5
                sma.append(mean)
                upper.append(mean + (std_dev * std))
                lower.append(mean - (std_dev * std))
        
        return upper, sma, lower
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        rsi = [50] * period
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        for i in range(period, len(prices)):
            avg_gain = sum(gains[i-period+1:i+1]) / period
            avg_loss = sum(losses[i-period+1:i+1]) / period
            if avg_loss == 0:
                rsi.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
        
        return rsi
    
    def calculate_stochastic(self, highs: List[float], lows: List[float], closes: List[float], k_period: int = 14) -> tuple:
        k_line = []
        d_line = []
        
        for i in range(len(closes)):
            if i < k_period - 1:
                k_line.append(50)
                d_line.append(50)
            else:
                lowest_low = min(lows[i-k_period+1:i+1])
                highest_high = max(highs[i-k_period+1:i+1])
                if highest_high == lowest_low:
                    k_line.append(50)
                else:
                    k = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
                    k_line.append(k)
                
                if i < k_period + 2:
                    d_line.append(50)
                else:
                    d = sum(k_line[i-2:i+1]) / 3
                    d_line.append(d)
        
        return k_line, d_line
    
    def calculate_volume_sma(self, volumes: List[float], period: int = 20) -> List[float]:
        sma = []
        for i in range(len(volumes)):
            if i < period - 1:
                sma.append(volumes[i])
            else:
                avg = sum(volumes[i-period+1:i+1]) / period
                sma.append(avg)
        return sma
    
    def strategy_aggressive_5indicators(self, data: List[Dict[str, Any]], 
                                         fast_period: int = 12, 
                                         slow_period: int = 26,
                                         rsi_period: int = 14):
        """
        ESTRATÉGIA AGRESSIVA COM 5 INDICADORES:
        1. EMA Cross - Tendência
        2. MACD - Momentum
        3. Bollinger Bands - Volatilidade/Breakout
        4. RSI - Sobrecompra/Sobrevenda
        5. Stochastic + Volume - Confirmação
        
        CONDIÇÕES DE COMPRA (mais frequentes):
        - EMA Fast > EMA Slow
        - MACD > Signal OU MACD histograma positivo
        - Preço perto da banda inferior OU rompendo média
        - RSI < 75 (permite entrar mesmo com RSI moderado)
        - Stochastic K < 80 OU Volume acima da média
        
        CONDIÇÕES DE VENDA (saída rápida):
        - EMA Fast < EMA Slow
        - OU RSI > 80 (sobrecompra extrema)
        - OU MACD cruza para baixo
        - OU Preço toca banda superior de Bollinger
        """
        
        prices = [d['close'] for d in data]
        highs = [d['high'] for d in data]
        lows = [d['low'] for d in data]
        volumes = [d['volume'] for d in data]
        
        # Calcular todos os indicadores
        ema_fast = self.calculate_ema(prices, fast_period)
        ema_slow = self.calculate_ema(prices, slow_period)
        macd_line, signal_line, histogram = self.calculate_macd(prices)
        upper_bb, middle_bb, lower_bb = self.calculate_bollinger_bands(prices, 20, 2)
        rsi = self.calculate_rsi(prices, rsi_period)
        stochastic_k, stochastic_d = self.calculate_stochastic(highs, lows, prices, 14)
        volume_sma = self.calculate_volume_sma(volumes, 20)
        
        for i in range(len(data)):
            current_price = prices[i]
            current_time = data[i]['time']
            
            # Verificar se temos dados suficientes
            if i < 30:
                self.equity_curve.append({'time': current_time, 'value': self.capital + (self.position * current_price)})
                continue
            
            # Sinais individuais
            ema_bullish = ema_fast[i] > ema_slow[i]
            macd_bullish = macd_line[i] > signal_line[i] or histogram[i] > 0
            price_near_lower_bb = current_price <= lower_bb[i] * 1.01  # Preço perto ou abaixo da banda inferior
            price_breaking_middle = current_price > middle_bb[i]  # Rompeu a média
            rsi_acceptable = rsi[i] < 75  # Mais permissivo que 65
            stochastic_ok = stochastic_k[i] < 80  # Não extremamente sobrecomprado
            volume_confirmed = volumes[i] > volume_sma[i] * 0.9  # Volume próximo ou acima da média
            
            # CONDIÇÃO DE COMPRA AGRESSIVA
            buy_signal = (
                ema_bullish and
                (macd_bullish or price_breaking_middle) and
                (price_near_lower_bb or price_breaking_middle) and
                rsi_acceptable and
                (stochastic_ok or volume_confirmed)
            )
            
            # CONDIÇÃO DE VENDA AGRESSIVA (múltiplas saídas)
            sell_signal = False
            if self.position > 0:
                # Venda por cruzamento de EMA
                if not ema_bullish:
                    sell_signal = True
                # Venda por sobrecompra extrema
                elif rsi[i] > 80:
                    sell_signal = True
                # Venda por toque na banda superior
                elif current_price >= upper_bb[i] * 0.99:
                    sell_signal = True
                # Venda por MACD negativo
                elif macd_line[i] < signal_line[i] and histogram[i] < 0:
                    sell_signal = True
            
            # Executar compra
            if buy_signal and self.position == 0:
                self.position = self.capital / current_price
                self.entry_price = current_price
                self.capital = 0
                self.trades.append({
                    'type': 'BUY',
                    'time': current_time,
                    'price': current_price,
                    'quantity': self.position,
                    'rsi_at_entry': round(rsi[i], 2),
                    'macd': round(macd_line[i], 2),
                    'bb_position': round((current_price - lower_bb[i]) / (upper_bb[i] - lower_bb[i]) * 100, 1) if upper_bb[i] != lower_bb[i] else 50
                })
            
            # Executar venda
            elif sell_signal and self.position > 0:
                sell_value = self.position * current_price
                cost_basis = self.position * self.entry_price
                pnl = sell_value - cost_basis
                pnl_percent = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
                
                self.capital = sell_value
                self.trades.append({
                    'type': 'SELL',
                    'time': current_time,
                    'price': current_price,
                    'quantity': self.position,
                    'pnl': round(pnl, 2),
                    'pnl_percent': round(pnl_percent, 2)
                })
                self.position = 0
            
            # Atualizar equity curve
            current_equity = self.capital + (self.position * current_price)
            self.equity_curve.append({'time': current_time, 'value': current_equity})
    
    def get_results(self) -> Dict[str, Any]:
        total_trades = len([t for t in self.trades if t['type'] == 'SELL'])
        winning_trades = len([t for t in self.trades if t['type'] == 'SELL' and t.get('pnl', 0) > 0])
        losing_trades = len([t for t in self.trades if t['type'] == 'SELL' and t.get('pnl', 0) <= 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calcular max drawdown
        equity_values = [e['value'] for e in self.equity_curve]
        peak = equity_values[0]
        max_drawdown = 0
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        final_equity = self.capital + (self.position * equity_values[-1] if equity_values else 0)
        total_return = ((final_equity - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_equity': round(final_equity, 2),
            'total_return': round(total_return, 2),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'max_drawdown': round(max_drawdown, 2),
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }