"""Auth do Vyra — Firebase ID tokens, sem tocar nas rotas existentes.

Uso futuro: `Depends(get_current_user_obrigatorio)` nas rotas a proteger,
NUMA JANELA DE MANUTENÇÃO (muda comportamento do dashboard em polling).
Hoje: só o módulo + GET /api/auth/me para provar integração.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as fb_auth

from app.core.firebase import get_firestore  # garante app inicializada

_seguranca = HTTPBearer(auto_error=False)


def verificar_token(id_token):
    """Valida o Firebase ID token. Devolve {uid, email} ou lança 401."""
    try:
        get_firestore()
        dados = fb_auth.verify_id_token(id_token)
        return {"uid": dados.get("uid"), "email": dados.get("email")}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao invalida — faz login de novo.",
        )


async def get_current_user_opcional(
    cred: HTTPAuthorizationCredentials = Depends(_seguranca),
):
    if cred is None:
        return None
    return verificar_token(cred.credentials)


async def get_current_user_obrigatorio(
    user=Depends(get_current_user_opcional),
):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta o token (Authorization: Bearer <idToken>).",
        )
    return user
