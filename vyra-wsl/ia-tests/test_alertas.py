"""Teste positivo dos alertas — prova que uma condição que DEVE disparar, dispara.

Sem escritas reais: listar_indicacoes e notificar são substituídos por
stubs em memória. Se a regra dos 3 ERROU não disparar aqui, o dry-run
anterior era falso-negativo.
"""
import sys
sys.path.insert(0, "/mnt/c/Users/franc/vyra/backend")
import os
os.environ.setdefault("FIREBASE_KEY_PATH", "/home/francfrancisco/vyra-firebase-key.json")

from app.core import alertas

FEITAS = [
    {"fonte": "kronos+rsi", "resultado": "ERROU"},
    {"fonte": "kronos+rsi", "resultado": "ERROU"},
    {"fonte": "kronos+rsi", "resultado": "ERROU"},
]
CAPTURADOS = []

alertas.listar_indicacoes = lambda limite=200: list(FEITAS)
alertas.notificar = lambda a: CAPTURADOS.append(a) or True
alertas.ja_disparado = lambda nome, data_ref: False

r = alertas.avaliar_regras()
assert len(r) == 1, r
assert r[0]["regra"] == "kronos-3-erros-seguidos", r
assert len(CAPTURADOS) == 1, CAPTURADOS
print("positivo-ok: 3xERROU dispara kronos-3-erros-seguidos")

# E o negativo continua negativo: 2 ERROU não chegam.
FEITAS.pop()
CAPTURADOS.clear()
r2 = alertas.avaliar_regras()
assert r2 == [] and CAPTURADOS == [], (r2, CAPTURADOS)
print("negativo-ok: 2xERROU nao dispara")
