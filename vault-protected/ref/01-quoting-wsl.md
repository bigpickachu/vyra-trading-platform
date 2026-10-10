# Erro 01 — quoting aninhado PowerShell → wsl → sh

- O que tentaste: correr `wsl -e sh -c "...python -c \"...\"..."` inline numa tool call.
- O que correu mal: `Syntax error: Unterminated quoted string` + `tail` interpretado no Windows. Comando morto, uma ronda perdida.
- Causa raiz: três camadas de quoting (PowerShell, wsl, sh) + mistura de ferramentas Windows/WSL no mesmo comando.
- O que farás diferente: SEMPRE escrever o comando num ficheiro `.sh`/`.py` (em `Temp\opencode` ou `/tmp`) e executar o ficheiro com um comando curto. Uma camada de quoting, zero inline aninhado. Válido para toda a série.
