import httpx
from datetime import datetime
from app.db.database import SessionLocal, text
from app.models.ohlcv import OHLCV
from sqlalchemy.dialects.postgresql import insert

def fetch_and_seed_data():
    print("🚀 A iniciar a população da base de dados com dados históricos...")
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    timeframes = ["1h", "4h", "1d"]  # Adicionámos 4h e 1d
    limit = 1000  # ~41 dias para 1h, ~166 dias para 4h, ~1000 dias para 1d
    
    db = SessionLocal()
    total_inseridos = 0

    try:
        # Garantir que a extensão TimescaleDB está ativa
        db.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
        db.commit()
        print("✅ Extensão TimescaleDB verificada.")

        for symbol in symbols:
            for tf in timeframes:
                print(f"📥 A buscar dados de {symbol} ({tf})...")
                
                # Buscar dados públicos da Binance
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit={limit}"
                
                with httpx.Client() as client:
                    resposta = client.get(url)
                    dados = resposta.json()
                
                if not isinstance(dados, list):
                    print(f"⚠️ Erro ao buscar {symbol} ({tf}): {dados}")
                    continue

                # Preparar os registos para inserção
                registos = []
                for k in dados:
                    registos.append({
                        "time": datetime.fromtimestamp(k[0] / 1000),
                        "symbol": symbol,
                        "timeframe": tf,
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5])
                    })
                
                # Inserir ignorando duplicados (graças à Primary Key)
                stmt = insert(OHLCV).values(registos)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['time', 'symbol', 'timeframe']
                )
                
                db.execute(stmt)
                db.commit()
                total_inseridos += len(registos)
                print(f"  ✅ {len(registos)} velas de {symbol} ({tf}) processadas.")

        print(f"\n🎉 SUCESSO! Total de {total_inseridos} registos inseridos/atualizados na base de dados.")
        
    except Exception as e:
        print(f"❌ Erro durante o processo: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fetch_and_seed_data()