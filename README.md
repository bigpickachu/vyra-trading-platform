# Vyra
Plataforma de trading algorítmico com confluência de três fontes de inteligência e medição científica da precisão por fonte.

O conceito: o bot decide em três camadas, cada uma na sua frequência — indicadores técnicos (RSI/EMA) a cada tick, o modelo preditivo Kronos a cada vela de 1h (com cache por símbolo+timestamp), e agentes de contexto em background via subprocess. Uma compra só acontece quando os indicadores e o Kronos concordam (a indisponibilidade do Kronos bloqueia a compra por defeito: disciplina sobre oportunismo). Cada decisão é gravada no Firestore com a fonte que a gerou e recebe depois um veredicto contra a cotação real — por isso o sistema mede-se a si próprio.

## Demo (6 gestos, sem ler código)
1. Abre o dashboard (`frontend-react`, `npm run dev` → http://localhost:5173).
2. Repara na **linha roxa tracejada** sobre o gráfico: são as próximas 24 velas previstas pelo Kronos.
3. Abre o painel de IA: precisão geral e **por fonte** (`kronos+rsi` vs `so-rsi`).
4. Abre o histórico de indicações: cada decisão com fonte, preço de entrada e veredicto.
5. Força um ciclo: compra em confluência → vê a indicação gravada → corre o worker → vê o veredicto `ACERTOU`/`ERROU`.
6. Confirma no console do Firestore: coleções `indicacoes` (decisões) e `agent_reports` (veredictos dos agentes).

## Stack
Backend: Python + FastAPI · Frontend: React + TypeScript · Velas: PostgreSQL/TimescaleDB · Decisões: Firebase Firestore · IA: Kronos (previsão das próximas 24 velas) + TradingAgents (análise multi-agente) · Autonomia: APScheduler (tick a cada 30s, com throttle anti-duplicação de 25s contra o polling de 5s do frontend) · DB local: Docker Compose.

## Arquitetura
Tick → indicadores + filtro Kronos → decisão BUY/SHORT/HOLD → Firestore `indicacoes` (campo `fonte`: `kronos+rsi` ou `so-rsi`) → worker diário compara cada indicação pendente com o preço real (banda ±0,3%) → veredicto `ACERTOU`/`ERROU`/`NEUTRO` → `GET /api/confianca` agrega precisão geral e por fonte. Os agentes correm isolados (timeout próprio) e gravam em `agent_reports`, sem bloquear o tick. Se uma fonte falha (Kronos, Postgres, Binance, Firestore), o sistema degrada em vez de morrer: Postgres em baixo → Binance; Firestore em baixo → o trade prossegue e só regista o erro no log.

## Como executar
Backend (dentro do WSL, com venv próprio):
```
cd backend
source venv-vyra/bin/activate
export FIREBASE_KEY_PATH="/home/<user>/vyra-firebase-key.json"
export SECRET_KEY="<segredo-local>"
uvicorn app.main:app --reload
```
Frontend:
```
cd frontend-react && npm install && npm run dev   # http://localhost:5173
```
DB:
```
cd docker && docker compose up -d   # PostgreSQL em :5432
```

## Ferramentas WSL
Testes isolados das IAs e scripts de operação (pasta `vyra-wsl/`, correm dentro do WSL): `ia-tests/teste_kronos.py` (previsão standalone de 24 velas), `ia-tests/run_agents_teste.py` (runner falso que testa o pipeline sem gastar quota), a simulação de 30 dias (`backend/simulacao_retroativa.py`, fonte isolada), `scripts/arrancar_vyra.sh` (arranque do backend com venv + `FIREBASE_KEY_PATH`) e `scripts/patch*.py` (patches idempotentes ao venv dos TradingAgents: tool budget e fundamentals crypto-aware).

## Endpoints principais
| Método | Rota | Para quê |
| GET | /api/candles | Velas (Postgres com fallback Binance, ordem cronológica corrigida) |
| GET | /api/forecast | Previsão Kronos das próximas 24 velas, com cache |
| GET | /api/confianca | Precisão geral e por fonte de decisão |
| GET | /api/indicacoes | Histórico de decisões com veredicto |
| POST | /api/backtest | Backtest histórico (estratégia de 5 indicadores) |
| GET/POST | /api/paper-trade/* | Paper trading ao vivo (start/stop/status/tick) |
| POST/GET | /api/agents/analyze, /api/agents/status/{symbol} | Pipeline multi-agente em background |
| POST | /api/worker/fecho-diario | Atribui veredictos às indicações pendentes |
Swagger automático em /docs.

## O experimento
Duas medições separadas, sem misturar:
- **Tempo real:** cada indicação é etiquetada pela fonte (`kronos+rsi` vs `so-rsi`); o worker atribui veredicto com banda de ±0,3% (dentro da banda é `NEUTRO` e fica fora da precisão). Amostra inicial, a crescer: ~75% em 4 decisões.
- **Simulação retroativa:** o script `simulacao_retroativa.py` corre o filtro Kronos sobre 30 dias de histórico e grava no Firestore com fonte `backtest`, isolada do experimento em tempo real: 2 indicações.
- **Backtest clássico:** o Backtester de 5 indicadores sobre ~2 anos no PostgreSQL: 396 trades como referência da estratégia sem IA.

Honestidade primeiro: a amostra inicial incluiu um erro da fonte preditiva e está registada como está — neutros e testes de integração excluídos da precisão.

## Agradecimentos
Usa o modelo open-source Kronos para previsão de séries financeiras ([shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)) e o framework open-source TradingAgents ([TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)) para análise multi-agente.

## Segurança
Nenhuma chave vive neste repo: a service key do Firebase entra via `FIREBASE_KEY_PATH` e o `SECRET_KEY` via `SECRET_KEY` (falha explícita se ausente). `bot_state.json`, `.env`, `*.log` e `*-firebase-key.json` estão no `.gitignore`.

## Licença
Projeto pessoal de investigação. Todos os direitos reservados — usa por tua conta e risco; nada aqui é aconselhamento financeiro.
