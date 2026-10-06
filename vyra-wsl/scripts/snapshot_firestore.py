"""Snapshot diário do Firestore — protege os dados do experimento.

Só leitura: exporta `indicacoes` + `agent_reports` para JSON datado.
Destino fora do git: C:\\Users\\franc\\football-ai\\snapshots\\ (via /mnt/c no WSL).
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/mnt/c/Users/franc/vyra/backend")
os.environ.setdefault("FIREBASE_KEY_PATH", "/home/francfrancisco/vyra-firebase-key.json")

DESTINO = os.getenv(
    "VYRA_SNAPSHOT_DIR",
    "/mnt/c/Users/franc/football-ai/snapshots",
)

from app.core.firebase import get_firestore


def main():
    db = get_firestore()
    dados = {}
    for colecao in ("indicacoes", "agent_reports", "alertas"):
        try:
            docs = [{"id": d.id, **d.to_dict()} for d in db.collection(colecao).stream()]
        except Exception as e:
            docs = {"erro": str(e)}
        dados[colecao] = docs
    os.makedirs(DESTINO, exist_ok=True)
    nome = "snapshot_%s.json" % datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    caminho = os.path.join(DESTINO, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1, default=str)
    resumo = {k: (len(v) if isinstance(v, list) else v) for k, v in dados.items()}
    print("snapshot: " + caminho)
    print("resumo: " + json.dumps(resumo, ensure_ascii=False))
    return caminho


if __name__ == "__main__":
    main()
