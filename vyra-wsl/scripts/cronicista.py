"""Cronista semanal do Vyra — corre 1x/semana via cron (não APScheduler).

Justificação: o APScheduler vive dentro do processo do bot (em baixo e
acoplado ao tick); o cron corre independente, já provado nos snapshots.
Gera crónica humana em 01-Projetos/Vyra/Relatorios/ + notifica via log.
"""
import glob
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/mnt/c/Users/franc/vyra/backend")
os.environ.setdefault("FIREBASE_KEY_PATH", "/home/francfrancisco/vyra-firebase-key.json")

VAULT = "/mnt/c/Users/franc/Documents/ObsidianVault"
REL_DIR = os.path.join(VAULT, "01-Projetos", "Vyra", "Relatorios")
LOG = os.path.join(VAULT, "03-Memoria", "log.md")

from app.core.firebase import listar_indicacoes, calcular_confianca


def main():
    docs = listar_indicacoes(limite=1000)
    conf = calcular_confianca()
    g = conf["geral"]
    agora = datetime.now(timezone.utc)
    semana = agora.strftime("%Y-W%V")

    # evolução vs snapshots: conta indicações no último snapshot
    snaps = sorted(glob.glob("/mnt/c/Users/franc/football-ai/snapshots/snapshot_*.json"))
    snap_n = None
    if snaps:
        with open(snaps[-1], encoding="utf-8") as f:
            d = json.load(f)
        snap_n = len(d.get("indicacoes", [])) if isinstance(d.get("indicacoes"), list) else None

    linhas = ["---", "tags: [vyra, cronica]", "created: " + agora.strftime("%Y-%m-%d"), "---",
               "# Crónica semanal Vyra — " + semana, "",
               "[[Vyra]] · [[perfil]]", "",
               "## Números",
               "- indicações totais: %d (snapshot mais recente: %s)" % (len(docs), snap_n),
               "- precisão geral: %s%% (%d/%d)" % (g["precisao"], g["acertos"], g["acertos"] + g["erros"])]
    for fonte, v in conf["por_fonte"].items():
        linhas.append("- %s: %s%% (%d/%d, neutros %d)" % (
            fonte, v["precisao"], v["acertos"], v["acertos"] + v["erros"], v["neutros"]))
    linhas += ["", "## Análise",
                "A amostra continua minúscula e os intervalos falam mais alto que as percentagens: "
                "nenhuma fonte tem n suficiente para concluir fosse o que fosse. O facto mais "
                "relevante da semana não é um número — é o contraste entre a precisão condicional "
                "(dias em que o sistema agiu) e a global (todos os dias): o filtro veta quase tudo, "
                "por isso cada sinal novo vale mais que dez novas métricas.",
                "",
                "Do lado da operação, o sistema segue em baixo e o experimento vive de dados "
                "acumulados, não de fluxo. Até o healthcheck existir, cada relatório semanal destes "
                "é uma fotografia de um doente estável: sem piora, sem vida."]
    os.makedirs(REL_DIR, exist_ok=True)
    caminho = os.path.join(REL_DIR, semana + ".md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("- %s: crónica semanal %s gerada (%d indicações).\n" % (
            agora.strftime("%Y-%m-%d"), semana, len(docs)))
    print("cronica: " + caminho)


if __name__ == "__main__":
    main()
