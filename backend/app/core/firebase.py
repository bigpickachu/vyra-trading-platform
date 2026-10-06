"""Integracao Firestore - base de dados NoSQL das indicacoes do sistema."""
import os
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

_app = None


def get_firestore():
    """Inicializa o Firebase uma unica vez (singleton)."""
    global _app
    if _app is None:
        key_path = os.getenv("FIREBASE_KEY_PATH")
        if not key_path:
            raise RuntimeError("FIREBASE_KEY_PATH nao definida")
        cred = credentials.Certificate(key_path)
        _app = firebase_admin.initialize_app(cred)
    return firestore.client()


def gravar_indicacao(symbol, indicacao, preco_inicio, fonte):
    """Grava uma indicacao do bot. Devolve o id do documento."""
    db = get_firestore()
    doc = db.collection("indicacoes").document()
    doc.set({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "indicacao": indicacao,
        "preco_inicio": preco_inicio,
        "fonte": fonte,
        "preco_fim": None,
        "variacao_real": None,
        "resultado": None,
    })
    return doc.id


def atualizar_resultado(doc_id, preco_fim, resultado):
    """Fecha uma indicacao com o preco e o veredicto."""
    db = get_firestore()
    variacao = None
    snap = db.collection("indicacoes").document(doc_id).get()
    if snap.exists:
        pi = snap.to_dict().get("preco_inicio")
        if pi:
            variacao = round((preco_fim - pi) / pi * 100, 2)
    db.collection("indicacoes").document(doc_id).update({
        "preco_fim": preco_fim,
        "variacao_real": variacao,
        "resultado": resultado,
    })


def obter_pendentes(symbol=None, limite=100):
    """Indicacoes sem resultado ainda (para o worker de fecho)."""
    db = get_firestore()
    q = db.collection("indicacoes").where("resultado", "==", None)
    if symbol:
        q = q.where("symbol", "==", symbol)
    docs = q.limit(limite).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def listar_indicacoes(symbol=None, limite=50):
    """Ultimas indicacoes, mais recentes primeiro."""
    db = get_firestore()
    q = db.collection("indicacoes")
    if symbol:
        q = q.where("symbol", "==", symbol)
    docs = q.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limite).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def calcular_confianca():
    """Agrega os veredictos por fonte de decisao."""
    db = get_firestore()
    docs = db.collection("indicacoes").stream()

    geral = {"total": 0, "acertos": 0, "erros": 0, "neutros": 0}
    por_fonte = {}

    for d in docs:
        data = d.to_dict()
        res = data.get("resultado")
        fonte = data.get("fonte", "desconhecida")

        # sem veredicto ou dados de teste nao contam para a amostra
        if res not in ("ACERTOU", "ERROU", "NEUTRO"):
            continue
        if fonte == "teste-integracao":
            continue

        alvo_geral = geral
        alvo_fonte = por_fonte.setdefault(fonte, {"total": 0, "acertos": 0, "erros": 0, "neutros": 0})
        for alvo in (alvo_geral, alvo_fonte):
            alvo["total"] += 1
            if res == "ACERTOU":
                alvo["acertos"] += 1
            elif res == "ERROU":
                alvo["erros"] += 1
            else:
                alvo["neutros"] += 1

    def com_precisao(d):
        # Melhoria A: a precisao vem com intervalo de Wilson e flag de
        # amostra insuficiente — campos ADITIVOS, veredictos intocados.
        import math
        out = dict(d)
        avaliados = d["acertos"] + d["erros"]
        if avaliados > 0:
            p = d["acertos"] / avaliados
            z, den = 1.96, 1 + 1.96 * 1.96 / avaliados
            centro = p + 1.96 * 1.96 / (2 * avaliados)
            margem = 1.96 * math.sqrt(p * (1 - p) / avaliados + 1.96 * 1.96 / (4 * avaliados * avaliados))
            out["precisao"] = round(p * 100, 1)
            out["ic95"] = [round(max(0.0, (centro - margem) / den) * 100, 1),
                           round(min(1.0, (centro + margem) / den) * 100, 1)]
        else:
            out["precisao"] = None
            out["ic95"] = None
        out["amostra_suficiente"] = avaliados >= 10
        return out

    return {
        "geral": com_precisao(geral),
        "por_fonte": {k: com_precisao(v) for k, v in por_fonte.items()},
    }
