import { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { createChart, CandlestickSeries, ColorType } from 'lightweight-charts';

const fmt = (val: any, digits: number = 2) => {
  if (val === undefined || val === null || isNaN(Number(val))) return '-';
  return Number(val).toFixed(digits);
};

function App() {
  const [mode, setMode] = useState<'backtest' | 'paper'>('backtest');
  const [data, setData] = useState<any>(null);
  const [candles, setCandles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);

  const [ptState, setPtState] = useState<any>(null);
  const [ptMetrics, setPtMetrics] = useState<any>(null);
  const [ptMarket, setPtMarket] = useState<any>(null);
  const [livePrice, setLivePrice] = useState<number>(0);

  const [symbol, setSymbol] = useState<string>('BTCUSDT');
  const [interval, setInterval] = useState<string>('1h');
  const [capital, setCapital] = useState<number>(10000);
  const [stopLoss, setStopLoss] = useState<number>(2);
  const [takeProfit, setTakeProfit] = useState<number>(5);
  const [rsiBuy, setRsiBuy] = useState<number>(45);
  const [rsiSell, setRsiSell] = useState<number>(55);
  const [direction, setDirection] = useState<string>('LONG');

  const symbols = [
    { value: 'BTCUSDT', label: 'Bitcoin (BTC)' },
    { value: 'ETHUSDT', label: 'Ethereum (ETH)' },
    { value: 'SOLUSDT', label: 'Solana (SOL)' },
    { value: 'XAUTUSDT', label: 'Ouro (XAUT)' },
  ];

  const fetchData = () => {
    const safeSymbol = String(symbol || 'BTCUSDT');
    const safeInterval = String(interval || '1h');
    const safeCapital = Number(capital) || 10000;
    setLoading(true);
    setError(null);
    setData(null);
    setCandles([]);
    axios.post(`/api/backtest?symbol=${safeSymbol}&interval=${safeInterval}&initial_capital=${safeCapital}`)
      .then(res => {
        if (res.data && res.data.error) { setError(res.data.error); setLoading(false); return; }
        setData(res.data);
        return axios.get(`/api/candles?symbol=${safeSymbol}&interval=${safeInterval}&limit=500`);
      })
      .then(res => { if (res && res.data) setCandles(res.data.data || res.data); setLoading(false); })
      .catch(err => { setError(err.message || 'Erro'); setLoading(false); });
  };

  const startPaperTrade = () => {
    axios.post(`/api/paper-trade/start?symbol=${symbol}&capital=${capital}&stop_loss=${stopLoss}&take_profit=${takeProfit}&rsi_buy=${rsiBuy}&rsi_sell=${rsiSell}&direction=${direction}`)
      .then(res => {
        // Atualiza o estado IMEDIATAMENTE
        if (res.data.state) setPtState(res.data.state);
        // Carrega o gráfico
        return axios.get(`/api/candles?symbol=${symbol}&interval=1m&limit=50`);
      })
      .then(res => {
        if (res && res.data) setCandles(res.data.data || []);
      })
      .catch(err => setError('Erro ao iniciar bot'));
  };

  const stopPaperTrade = () => {
    axios.post('/api/paper-trade/stop')
      .then(() => {
        // Limpa o estado IMEDIATAMENTE
        setPtState(null);
        setPtMetrics(null);
        setPtMarket(null);
        setLivePrice(0);
      })
      .catch(err => console.error('Erro:', err));
  };

  // POLLING - Atualiza apenas os números em tempo real (não mexe no gráfico)
  useEffect(() => {
    const poll = () => {
      axios.get('/api/paper-trade/status')
        .then(res => {
          if (res.data && res.data.active && res.data.state) {
            // Só atualiza se houver mudança para evitar re-renders desnecessários
            setPtState(prev => JSON.stringify(prev) !== JSON.stringify(res.data.state) ? res.data.state : prev);
            return axios.get('/api/paper-trade/tick');
          } else {
            setPtState(null);
            setPtMetrics(null);
            setPtMarket(null);
          }
        })
        .then(res => {
          if (res && res.data && res.data.active) {
            setPtMetrics(res.data.metrics);
            setPtMarket(res.data.market);
            const sym = res.data.state.symbol;
            return axios.get(`/api/preco?symbol=${sym}`);
          }
        })
        .then(res => {
          if (res && res.data) setLivePrice(res.data.preco || 0);
        })
        .catch(err => console.error('Erro no polling:', err));
    };

    poll();
    const intervalId = setInterval(poll, 5000);
    return () => clearInterval(intervalId);
  }, []);

  // GRÁFICO - Só recria quando as velas mudam
  useEffect(() => {
    if (!chartRef.current || candles.length === 0) return;
    try {
      if (chartInstance.current) { chartInstance.current.remove(); chartInstance.current = null; }
      const chart = createChart(chartRef.current, {
        layout: { background: { type: ColorType.Solid, color: '#0f111a' }, textColor: '#8b949e' },
        grid: { vertLines: { color: '#1e212b' }, horzLines: { color: '#1e212b' } },
        width: chartRef.current.clientWidth, height: 450,
      });
      chartInstance.current = chart;
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#26a69a', downColor: '#ef5350', borderUpColor: '#26a69a', borderDownColor: '#ef5350', wickUpColor: '#26a69a', wickDownColor: '#ef5350',
      });
      candleSeries.setData(candles);
      const trades = mode === 'backtest' ? (data?.trades || []) : (ptState?.trades || []);
      trades.forEach((t: any) => {
        let color = '#ef5350';
        let title = 'SELL';
        if (t.type === 'BUY') { color = '#26a69a'; title = 'BUY'; }
        else if (t.type === 'SHORT' || t.type === 'COVER') { color = '#ff9800'; title = t.type; }
        candleSeries.createPriceLine({
          price: Number(t.price) || 0, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title,
        });
      });
      chart.timeScale().fitContent();
      const handleResize = () => { if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth }); };
      window.addEventListener('resize', handleResize);
      return () => { window.removeEventListener('resize', handleResize); };
    } catch (err) { console.error("Erro gráfico:", err); }
  }, [candles]); // Dependência simplificada

  const isProfit = mode === 'backtest' ? (data && !data.error ? Number(data.total_return) >= 0 : false) : (ptState ? (ptState.equity - ptState.initial_capital) >= 0 : false);
  const currentReturn = mode === 'backtest' ? (data ? Number(data.total_return) : 0) : (ptState ? ((ptState.equity - ptState.initial_capital) / ptState.initial_capital) * 100 : 0);

  const cardStyle: React.CSSProperties = { backgroundColor: '#161822', border: '1px solid #2d2d3a', borderRadius: 6, padding: 20 };
  const labelStyle: React.CSSProperties = { color: '#8b949e', fontSize: 12, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 };
  const inputStyle: React.CSSProperties = { width: '100%', padding: 10, backgroundColor: '#0f111a', color: '#e2e8f0', border: '1px solid #2d2d3a', borderRadius: 4, fontSize: 14, boxSizing: 'border-box' };

  return (
    <div style={{ minHeight: '100vh', padding: 40, backgroundColor: '#0a0b10', color: '#e2e8f0', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif' }}>
      <div style={{ maxWidth: 1440, margin: '0 auto' }}>
        
        <header style={{ marginBottom: 40, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 600, color: '#e2e8f0', margin: 0, letterSpacing: -0.5 }}>VYRA TRADING PLATFORM</h1>
            <p style={{ color: '#8b949e', fontSize: 13, marginTop: 8 }}>Estratégia: EMA Cross + RSI Filter + MACD + Bollinger + Stochastic</p>
          </div>
          <div style={{ display: 'flex', backgroundColor: '#161822', borderRadius: 4, padding: 4, border: '1px solid #2d2d3a' }}>
            <button onClick={() => setMode('backtest')} style={{ padding: '8px 16px', borderRadius: 4, border: 'none', cursor: 'pointer', fontWeight: 500, fontSize: 13, backgroundColor: mode === 'backtest' ? '#2d2d3a' : 'transparent', color: mode === 'backtest' ? '#e2e8f0' : '#8b949e' }}>Backtest Histórico</button>
            <button onClick={() => setMode('paper')} style={{ padding: '8px 16px', borderRadius: 4, border: 'none', cursor: 'pointer', fontWeight: 500, fontSize: 13, backgroundColor: mode === 'paper' ? '#2d2d3a' : 'transparent', color: mode === 'paper' ? '#e2e8f0' : '#8b949e' }}>Paper Trading</button>
          </div>
        </header>

        {mode === 'paper' && ptState?.active && (
          <div style={{ backgroundColor: '#0f291e', border: '1px solid #1e4632', borderRadius: 4, padding: 12, marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#26a69a' }} />
              <span style={{ color: '#26a69a', fontSize: 13, fontWeight: 500 }}>Sistema ativo. Direção: {ptState.direction}</span>
            </div>
            <span style={{ color: '#26a69a', fontSize: 20, fontWeight: 600 }}>${fmt(livePrice)}</span>
          </div>
        )}

        <div style={{ backgroundColor: '#161822', border: '1px solid #2d2d3a', borderRadius: 6, padding: 24, marginBottom: 24, display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 180 }}>
            <label style={labelStyle}>Ativo</label>
            {/* Dropdown NUNCA bloqueia no Backtest */}
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} disabled={mode === 'paper' && ptState?.active} style={{...inputStyle, opacity: (mode === 'paper' && ptState?.active) ? 0.5 : 1}}>
              {symbols.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div style={{ flex: 1, minWidth: 180 }}>
            <label style={labelStyle}>Capital Inicial (USD)</label>
            <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} disabled={mode === 'paper' && ptState?.active} style={{...inputStyle, opacity: (mode === 'paper' && ptState?.active) ? 0.5 : 1}} />
          </div>
          
          {mode === 'backtest' && (
            <>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label style={labelStyle}>Timeframe</label>
                <select value={interval} onChange={(e) => setInterval(String(e.target.value))} style={inputStyle}>
                  <option value="1h">1 Hora</option><option value="4h">4 Horas</option><option value="1d">1 Dia</option>
                </select>
              </div>
              <button onClick={fetchData} disabled={loading} style={{ padding: '10px 24px', backgroundColor: loading ? '#2d2d3a' : '#5b5fc7', color: '#fff', border: 'none', borderRadius: 4, fontWeight: 500, fontSize: 13, cursor: 'pointer' }}>{loading ? 'Processando...' : 'Executar Backtest'}</button>
            </>
          )}
          {mode === 'paper' && !ptState?.active && (
            <button onClick={startPaperTrade} style={{ padding: '10px 24px', backgroundColor: '#26a69a', color: '#fff', border: 'none', borderRadius: 4, fontWeight: 500, fontSize: 13, cursor: 'pointer' }}>Iniciar Bot</button>
          )}
          {mode === 'paper' && ptState?.active && (
            <button onClick={stopPaperTrade} style={{ padding: '10px 24px', backgroundColor: '#ef5350', color: '#fff', border: 'none', borderRadius: 4, fontWeight: 500, fontSize: 13, cursor: 'pointer' }}>Parar Bot</button>
          )}
        </div>

        {mode === 'paper' && !ptState?.active && (
          <div style={{ backgroundColor: '#161822', border: '1px solid #2d2d3a', borderRadius: 6, padding: 24, marginBottom: 24 }}>
            <h3 style={{ color: '#e2e8f0', fontSize: 14, marginBottom: 20, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 0 }}>Configurações da Estratégia</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
              <div><label style={labelStyle}>Stop-Loss (%)</label><input type="number" value={stopLoss} onChange={(e) => setStopLoss(Number(e.target.value))} step="0.5" min="0.5" max="10" style={inputStyle} /></div>
              <div><label style={labelStyle}>Take-Profit (%)</label><input type="number" value={takeProfit} onChange={(e) => setTakeProfit(Number(e.target.value))} step="0.5" min="1" max="20" style={inputStyle} /></div>
              <div><label style={labelStyle}>RSI Compra (&lt;)</label><input type="number" value={rsiBuy} onChange={(e) => setRsiBuy(Number(e.target.value))} step="5" min="30" max="80" style={inputStyle} /></div>
              <div><label style={labelStyle}>RSI Venda (&gt;)</label><input type="number" value={rsiSell} onChange={(e) => setRsiSell(Number(e.target.value))} step="5" min="40" max="90" style={inputStyle} /></div>
              <div><label style={labelStyle}>Direção</label>
                <select value={direction} onChange={(e) => setDirection(e.target.value)} style={inputStyle}>
                  <option value="LONG">Apenas Long</option>
                  <option value="SHORT">Apenas Short</option>
                  <option value="BOTH">Bidirecional</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {mode === 'backtest' && loading && <div style={{ color: '#5b5fc7', padding: 20, textAlign: 'center', backgroundColor: '#161822', borderRadius: 6, marginBottom: 24 }}>A processar dados históricos...</div>}
        {mode === 'backtest' && error && <div style={{ color: '#ef5350', padding: 20, textAlign: 'center', backgroundColor: '#161822', borderRadius: 6, marginBottom: 24, border: '1px solid #ef5350' }}>{error}</div>}

        {((mode === 'backtest' && data && !data.error) || (mode === 'paper' && ptState)) && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
              <div style={cardStyle}>
                <div style={labelStyle}>Retorno Total</div>
                <div style={{ fontSize: 28, fontWeight: 600, color: isProfit ? '#26a69a' : '#ef5350' }}>{isProfit ? '+' : ''}{fmt(currentReturn)}%</div>
                <div style={{ color: '#8b949e', fontSize: 12, marginTop: 8 }}>${fmt(mode === 'backtest' ? data.initial_capital : ptState.initial_capital, 0)} &rarr; ${fmt(mode === 'backtest' ? data.final_equity : ptState.equity)}</div>
              </div>
              {mode === 'paper' && ptMarket && (
                <div style={cardStyle}>
                  <div style={labelStyle}>Estado do Mercado (1m)</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: '#e2e8f0' }}>RSI: <span style={{color: ptMarket.rsi < (ptState?.rsi_buy_threshold || 45) ? '#26a69a' : '#ef5350'}}>{fmt(ptMarket.rsi)}</span></div>
                  <div style={{ fontSize: 12, color: '#8b949e', marginTop: 8 }}>Ação: <span style={{ fontWeight: 600, color: ptMarket.action === 'BUY' ? '#26a69a' : ptMarket.action === 'SELL' ? '#ef5350' : ptMarket.action === 'SHORT' || ptMarket.action === 'COVER' ? '#ff9800' : '#8b949e' }}>{ptMarket.action}</span></div>
                </div>
              )}
              <div style={cardStyle}>
                <div style={labelStyle}>Ordens Totais</div>
                <div style={{ fontSize: 28, fontWeight: 600, color: '#e2e8f0' }}>{fmt(mode === 'backtest' ? data.total_trades : ptMetrics?.total_trades || 0, 0)}</div>
                <div style={{ color: '#8b949e', fontSize: 12, marginTop: 8 }}>Win Rate: {fmt(mode === 'backtest' ? data.win_rate : ptMetrics?.win_rate || 0)}%</div>
              </div>
              {mode === 'paper' && (
                <div style={cardStyle}>
                  <div style={labelStyle}>Posição Aberta</div>
                  <div style={{ fontSize: 28, fontWeight: 600, color: ptState.position_type === 'LONG' ? '#26a69a' : ptState.position_type === 'SHORT' ? '#ff9800' : '#8b949e' }}>
                    {ptState.position_type === 'NONE' ? 'Nenhuma' : ptState.position_type}
                  </div>
                  <div style={{ color: '#8b949e', fontSize: 12, marginTop: 8 }}>{ptState.position > 0 ? `${fmt(ptState.position, 6)} @ $${fmt(ptState.entry_price)}` : 'Em espera...'}</div>
                </div>
              )}
            </div>

            {mode === 'paper' && ptMetrics && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 24 }}>
                <div style={cardStyle}><div style={labelStyle}>Profit Factor</div><div style={{ fontSize: 22, fontWeight: 600, color: ptMetrics.profit_factor >= 1 ? '#26a69a' : '#ef5350' }}>{fmt(ptMetrics.profit_factor)}</div></div>
                <div style={cardStyle}><div style={labelStyle}>Max Drawdown</div><div style={{ fontSize: 22, fontWeight: 600, color: '#ef5350' }}>-{fmt(ptMetrics.max_drawdown_pct)}%</div></div>
                <div style={cardStyle}><div style={labelStyle}>PnL Total</div><div style={{ fontSize: 22, fontWeight: 600, color: ptMetrics.total_pnl >= 0 ? '#26a69a' : '#ef5350' }}>{ptMetrics.total_pnl >= 0 ? '+' : ''}${fmt(ptMetrics.total_pnl)}</div></div>
                <div style={cardStyle}><div style={labelStyle}>Streak Atual</div><div style={{ fontSize: 22, fontWeight: 600, color: ptMetrics.current_streak > 0 ? '#26a69a' : ptMetrics.current_streak < 0 ? '#ef5350' : '#8b949e' }}>{ptMetrics.current_streak > 0 ? `${ptMetrics.current_streak}W` : ptMetrics.current_streak < 0 ? `${Math.abs(ptMetrics.current_streak)}L` : '0'}</div></div>
              </div>
            )}

            <div style={{ backgroundColor: '#161822', border: '1px solid #2d2d3a', borderRadius: 6, padding: 24, marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: 0.5, margin: 0 }}>Gráfico de Velas {mode === 'paper' ? '(1m)' : ''}</h2>
                {mode === 'paper' && ptState?.active && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#26a69a' }} />
                    <span style={{ color: '#26a69a', fontSize: 12, fontWeight: 500 }}>ATIVO • 5s • SL {ptState.stop_loss_pct*100}% • TP {ptState.take_profit_pct*100}%</span>
                  </div>
                )}
              </div>
              <div ref={chartRef} style={{ width: '100%', borderRadius: 4, overflow: 'hidden', minHeight: '450px' }} />
            </div>

            <div style={{ backgroundColor: '#161822', border: '1px solid #2d2d3a', borderRadius: 6, padding: 24 }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 20, marginTop: 0 }}>Histórico de Ordens</h2>
              <div style={{ overflowX: 'auto', maxHeight: '320px', overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: '#161822' }}>
                    <tr style={{ borderBottom: '1px solid #2d2d3a', textAlign: 'left' }}>
                      <th style={{ padding: 12, color: '#8b949e', fontWeight: 500, textTransform: 'uppercase', fontSize: 11 }}>#</th>
                      <th style={{ padding: 12, color: '#8b949e', fontWeight: 500, textTransform: 'uppercase', fontSize: 11 }}>Tipo</th>
                      <th style={{ padding: 12, color: '#8b949e', fontWeight: 500, textTransform: 'uppercase', fontSize: 11 }}>Hora</th>
                      <th style={{ padding: 12, color: '#8b949e', fontWeight: 500, textTransform: 'uppercase', fontSize: 11 }}>Preço</th>
                      <th style={{ padding: 12, color: '#8b949e', fontWeight: 500, textTransform: 'uppercase', fontSize: 11 }}>PnL (USD)</th>
                      <th style={{ padding: 12, color: '#8b949e', fontWeight: 500, textTransform: 'uppercase', fontSize: 11 }}>PnL (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(mode === 'backtest' ? (data.trades || []) : (ptState.trades || [])).map((t: any, i: number) => {
                      let typeColor = '#ef5350';
                      let typeLabel = 'VENDA';
                      if (t.type === 'BUY') { typeColor = '#26a69a'; typeLabel = 'COMPRA'; }
                      else if (t.type === 'SHORT') { typeColor = '#ff9800'; typeLabel = 'SHORT'; }
                      else if (t.type === 'COVER') { typeColor = '#ff9800'; typeLabel = 'COVER'; }
                      
                      const date = new Date(Number(t.time) * 1000);
                      const timeStr = date.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                      const pnlVal = Number(t.pnl || 0);
                      const pnlPctVal = Number(t.pnl_percent || 0);
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid #1e212b' }}>
                          <td style={{ padding: 12, color: '#8b949e' }}>{i + 1}</td>
                          <td style={{ padding: 12, color: typeColor, fontWeight: 600, fontSize: 12 }}>{typeLabel}</td>
                          <td style={{ padding: 12, color: '#e2e8f0' }}>{timeStr}</td>
                          <td style={{ padding: 12, color: '#e2e8f0' }}>${fmt(t.price)}</td>
                          <td style={{ padding: 12, color: pnlVal > 0 ? '#26a69a' : pnlVal < 0 ? '#ef5350' : '#8b949e', fontWeight: 600 }}>{t.pnl !== undefined ? (pnlVal > 0 ? '+' : '') + '$' + fmt(t.pnl) : '-'}</td>
                          <td style={{ padding: 12, color: pnlPctVal > 0 ? '#26a69a' : pnlPctVal < 0 ? '#ef5350' : '#8b949e', fontWeight: 600 }}>{t.pnl_percent !== undefined ? (pnlPctVal > 0 ? '+' : '') + fmt(t.pnl_percent) + '%' : '-'}</td>
                        </tr>
                      );
                    })}
                    {((mode === 'backtest' ? data.trades : ptState.trades)?.length === 0) && (<tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#8b949e' }}>Sem ordens registadas...</td></tr>)}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;