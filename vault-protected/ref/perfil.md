---
tags: [perfil]
created: 2026-10-06
updated: 2026-10-06
---

# Perfil — Francisco Lousa

[[Formação]] | [[Vyra]] | [[Python]] | [[Desenvolvimento Web]] | [[Bases de Dados]] | [[Inteligência Artificial]] | [[Infraestrutura e Redes]]

## 1. Nível técnico

**Domina:**
- **[[Python]] aplicado** (trajetória `formacao/python`: de `ficha1/exercicio1` com 7 linhas e `input()` nu até `ProjetoFinal/Projetofinal.py` com 4 classes de domínio + app Tkinter com 4 abas + pandas/matplotlib). Usa `csv.DictReader`, `try/except` sistemático, `match/case`, NumPy/pandas com conhecimento da API.
- **Backend web em dois mundos:** ASP.NET WebForms/C# com SQL Server parametrizado (`Inscricao.aspx.cs:79-85` `@RegimeId`) **e** FastAPI moderno no [[Vyra]] (`backend/app/main.py`, 591 linhas de tick + 8+ endpoints, `BackgroundTasks`, CORS, Swagger).
- **[[Bases de Dados]] em dois registos:** SQL normalizado (dump `lojadeinformatica.sql`: 11 tabelas `gs_*`, FKs, `utf8mb4`, `DECIMAL`, auditoria) **e** NoSQL append-only ([[Firestore]] `indicacoes` com `gravar_indicacao` no BUY + `atualizar_resultado` no SELL — design de experimento A/B observacional por `fonte`).
- **[[Desenvolvimento Web]] funcional:** de HTML com `<b>/<i>` a site final com CSS externo, Lightbox, `IntersectionObserver` (725 linhas) e no [[Vyra]] React com polling sem recriar gráfico + lightweight-charts com série de previsão.
- **Infra real ([[Infraestrutura e Redes]]):** WSL2 ARM64, venvs dedicados, Docker Compose com healthcheck, TimescaleDB com PK `(time,symbol,timeframe)`, seed idempotente.

**Ainda em aprendizagem / dívida assumida:**
- Estado em ficheiro (`bot_state.json`) em vez de DB/fila; `SECRET_KEY` hardcoded (depois movido para env na profissionalização do repo); `requirements.txt` desatualizado; `GET /api/forecast` faz HTTP para si próprio; lógica LONG/SHORT duplicada; zero testes automatizados; `stream()` full-collection no Firestore sem paginação.

## 2. Estilo de código e de trabalho

- **Português europeu sem acentos, sempre:** `snake_case` PT (`criar_ficheiro`, `previsao`, `indicacao`), classes em `PascalCase`, logs prefixados (`[KRONOS]`, `[FIREBASE]`, `[WORKER]`).
- **Honestidade confessional nos comentários:** *"não sei se está bem, mas funciona"*; PDF "não é PDF verdadeiro" admitido no comentário; fonte `backtest` isolada por design. Registar o erro é valor, não fraqueza.
- **Organização por iteração, não por git:** pastas `Projeto05` / `Projeto05_2` / `_backup`, ficheiros `.bak` como "arqueologia de bugs".
- **Defensive programming a partir da Ficha 3:** `try/except` sistemático, loops de validação, SQL parametrizado. No [[Vyra]]: cada fonte externa isolada no seu `try/except`.
- **Documentação = código + enunciados, não READMEs** (na formação; no [[Vyra]] um `README.md` denso de 38 linhas).

## 3. História de aprendizagem (erros → melhorias)

1. **`str` vs `int` no `input()`** — 7 erros numerados com correção. Virou padrão permanente de validação na fronteira.
2. **CSV ingénuo → `csv.DictReader`** — de `split(",")` para acesso por nome. Eco no [[Vyra]]: Firestore com campos nomeados.
3. **Cache sem chave de ativo** — `forecaster.py.bak` usava só o tempo, devolvia previsão de BTC a pedido de ETH; corrigido para `símbolo+tempo`.
4. **Relógio errado no cooldown** — tempo da vela → `time.time()` real, com comentário `CORRIGIDO`.
5. **Scheduler 30s vs polling 5s** — throttle de 25s + `THROTTLED`. Lição: idempotência.
6. **Fonte hardcoded `so-rsi`** — experimento nasceria inútil; a etiqueta do experimento é tão importante como o modelo.
7. **Dívidas à vista** — login `ADMIN/123`, SMTP exemplo, PDF-falso. Protótipo honesto primeiro, endurecer depois.

## 4. Decisões recorrentes

- **Honestidade científica sobre números bonitos:** banda ±0,3% com `NEUTRO`, neutros e testes excluídos da precisão.
- **Separar stores por caso de uso:** série temporal em TimescaleDB, log de decisões em [[Firestore]].
- **Camadas com custos diferentes:** indicadores baratos a cada tick, [[Kronos]] caro com cache, agentes lentos em background.
- **Falha isolada, nunca cascata:** cada fonte/job com o seu `try/except`. Degradar em vez de morrer.
- **Disciplina sobre oportunismo:** Kronos indisponível **bloqueia** compra por defeito.

## 5. Como trabalhar comigo

- **Explicação antes de código**, uma coisa de cada vez, fase a fase validada com evidência.
- **Perguntar antes de assumir** (fontes, schemas, trade-offs).
- **Reportar o que foi feito no PC** (ficheiros, comandos, portas). Sem ações invisíveis.
- **Regras de segurança como contrato** (ver Regras operacionais abaixo).
- **Valorizar o registo:** erros documentados, veredictos, precisão por fonte.

## Regras operacionais

- Projetos: [[Vyra]] (produção pessoal — nunca modificar, apagar ou reiniciar; vive em `C:\Users\franc\vyra`), football-ai (novo, isolado em `C:\Users\franc\football-ai`).
- Stack: [[Python]] + FastAPI, React + TS, [[Firestore]], APScheduler. Ambiente: Windows + WSL2 ARM64.
- Nunca parar containers `vyra-*`; portas 8000/5432/5173 proibidas (football-ai usa 8010/5180/5433).
- Chaves só no `.env` próprio; comandos destrutivos só com confirmação; só serviços gratuitos.
