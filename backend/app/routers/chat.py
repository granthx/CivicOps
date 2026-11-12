"""Guardrailed CivicOps waste-management chatbot endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..config import settings
from ..deps import DbSession
from ..schemas import ChatRequest, ChatResponse
from ..services.chatbot import handle_chat_message
from ..services.rate_limit import enforce_chat_rate_limit

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat_with_assistant(
    payload: ChatRequest, request: Request, db: DbSession
) -> ChatResponse:
    """Answer citizen or operator questions strictly within CivicOps waste-management scope."""
    client_ip = request.client.host if request.client else "unknown"
    enforce_chat_rate_limit(client_ip, settings.chat_rate_limit_per_hour)
    return handle_chat_message(db, payload)

