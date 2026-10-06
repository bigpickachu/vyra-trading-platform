"""Alertas do Vyra — avaliados num job APScheduler SEPARADO (alertas_checker).

Nunca corre dentro do tick/worker: se isto rebentar, o bot continua vivo.
Cada regra lê o Firestore, e o disparo vai para a coleção `alertas`
via notificar() — amanhã o Telegram entra só nessa função.
"""
from datetime import datetime, timezone

from app.core.firebase import get_firestore, listar_indicacoes
from firebase_admin import firestore

COLECAO = "alertas"

# (nome, fonte, veredictos_necessarios, tipo)
REGRAS = [
    ("kronos-3-erros-seguidos", "kronos+rsi", ["ERROU", "ERROU", "ERROU"]),
    ("rsi-3-acertos-seguidos", "so-rsi", ["ACERTOU", "ACERTOU", "ACERTOU"]),
]


def ultimos_veredictos(fonte, n=3):
    """Últimos n veredictos da fonte (mais recentes primeiro)."""
    vistos = []
    for d in listar_indicacoes(limite=200):
        if d.get("fonte") == fonte and d.get("resultado") in ("ACERTOU", "ERROU"):
            vistos.append(d.get("resultado"))
            if len(vistos) == n:
                break
    return vistos


def ja_disparado(nome, data_ref):
    """Evita repetir o mesmo alerta para a mesma sequência."""
    db = get_firestore()
    docs = db.collection(COLECAO).where("regra", "==", nome).limit(5).stream()
    for d in docs:
        if d.to_dict().get("data_ref") == data_ref:
            return True
    return False


def notificar(alerta):
    """ÚNICO ponto de saída: hoje log + Firestore, amanhã Telegram aqui."""
    print(f"[ALERTAS] {alerta['regra']}: {alerta['mensagem']}")
    db = get_firestore()
    db.collection(COLECAO).add(alerta)
    return True


def avaliar_regras():
    """Corre as regras e devolve os alertas disparados (sem rebentar)."""
    disparados = []
    try:
        for nome, fonte, seq in REGRAS:
            n = len(seq)
            vistos = ultimos_veredictos(fonte, n)
            if vistos == seq:
                data_ref = datetime.now(timezone.utc).date().isoformat()
                if not ja_disparado(nome, data_ref):
                    alerta = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "regra": nome,
                        "fonte": fonte,
                        "sequencia": vistos,
                        "data_ref": data_ref,
                        "mensagem": f"{fonte}: {n}x {seq[0]} seguidos",
                    }
                    notificar(alerta)
                    disparados.append(alerta)
    except Exception as e:
        print(f"[ALERTAS] avaliacao falhou (bot intacto): {e}")
    return disparados


def alertas_checker():
    """Job APScheduler: wrapper à prova de bala — nunca propaga exceção."""
    try:
        return avaliar_regras()
    except Exception as e:
        print(f"[ALERTAS] checker falhou (bot intacto): {e}")
        return []


def ultimos_alertas(limite=20):
    """Lê a coleção separada (para o endpoint, sem tocar no tick)."""
    docs = get_firestore().collection(COLECAO).order_by(
        "timestamp", direction=firestore.Query.DESCENDING).limit(limite).stream()
    return [d.to_dict() for d in docs]
