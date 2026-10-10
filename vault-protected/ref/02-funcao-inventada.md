# Erro 02 — função inventada no endpoint de alertas

- O que tentaste: no `GET /api/alertas` chamaste `get_firestore_collection_desc()`, que não existe em lado nenhum.
- O que correu mal: erro de referência que só o dry-run apanharia; se tivesse ido direto a commit sem validar, o endpoint nascia partido.
- Causa raiz: pressa a escrever o endpoint antes de decidir onde vive a lógica (main vs módulo). Escreveste o uso antes da definição.
- O que farás diferente: regra nova — NUNCA chamar função que ainda não existe no disco; primeiro o módulo com tudo (lógica + leitura), depois o endpoint fino que só delega. E validar sempre com dry-run antes do commit (foi o que salvou desta vez).
