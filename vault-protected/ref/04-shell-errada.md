# Erro 04 — recaída: comandos Linux na shell Windows

- O que tentaste: `sha256sum` e `ls -la` direto na tool shell (Windows/PowerShell).
- O que correu mal: `CommandNotFound`, mais `2>/dev/null` interpretado como ficheiro `C:\dev\null`. Segunda ocorrência do mesmo padrão do Erro 01.
- Causa raiz: a regra "ficheiros em vez de inline" não chega — falta a segunda metade: SABER EM QUE SHELL ESTÁS antes de escrever o comando. A tool `shell` corre PowerShell; só `wsl ...` corre Linux.
- O que farás diferente: regra das duas perguntas antes de cada comando shell: (1) Windows ou WSL? (2) inline curto ou ficheiro? Se WSL: `wsl <ficheiro.sh>` ou `wsl <comando-simples-sem-aspas-aninhadas>`. Se Windows: só cmdlets PowerShell (`Get-FileHash`, não `sha256sum`).
