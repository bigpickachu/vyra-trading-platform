# Erro 03 — edit com oldString que era cabeçalho de secção

- O que tentaste: inserir o bloco `/api/auth/me` usando como âncora o comentário `# ===== Agentes multi-IA =====`.
- O que correu mal: o `oldString` era SÓ o cabeçalho — a inserção apagou-o. Ficheiro ficou sem o separador de secção.
- Causa raiz: âncora mal escolhida (linha de conteúdo alheio em vez de ponto de inserção neutro).
- O que farás diferente: âncoras de edit devem ser linhas que SE MANTÊM no resultado (ex: incluir o cabeçalho também no `newString`), e reler sempre o resultado do edit. Apanhado e revertido no minuto seguinte, sem dano.
