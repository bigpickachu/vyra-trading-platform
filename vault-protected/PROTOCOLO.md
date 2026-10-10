# PROTOCOLO L1 — ficheiros críticos, escrita só-humana

Técnica escolhida: **detetiva, não preventiva** (justificação abaixo). Vale desde 2026-10-06.

## O que é protegido
`backend/app/core/firebase.py`, `backend/app/core/agents.py`, `backend/bot_state.json`,
`ObsidianVault/03-Memoria/perfil.md`, `ObsidianVault/03-Memoria/erros/` (append-only:
acrescentar notas novas sim, editar/apagar existentes nunca).

## Regra para o agente
Ler tudo. Escrever nestes ficheiros: NUNCA sem plano aprovado que os nomeie.
`bot_state.json`: só o processo do bot escreve (a cada tick); o agente nem lê para
editar — lê só para diagnóstico. Exceção: missão que ordene explicitamente o arranque.

## Porque não chmod/utilizador separado hoje
O agente opera como o mesmo utilizador WSL — `chmod` seria teatro (quem restringe
pode desfazer). Separação real exige utilizador de serviço `agente` + grupo do bot,
receita pronta quando quiseres (pedir: "implementa L1-preventivo"). Até lá, a
proteção é detetiva: L3 (âncora de hashes guardada pelo humano) + L2 (testemunha) +
`git status` antes de cada push.

## ref/ — cópias de integridade deste instante
Cópias ponto-a-ponto dos ficheiros acima. `bot_state.json` muda a cada tick com o
bot vivo — a cópia aqui prova o estado do experimento NESTE instante, não "o" estado.
