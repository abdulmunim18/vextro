"""Authenticated routes for the grounded shopping assistant."""

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies.roles import consumer_or_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.assistant import (
    AssistantMessageCreate,
    AssistantTurnResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
)
from app.services.assistant_service import AssistantService


router = APIRouter(
    prefix="/api/v1/assistant",
    tags=["shopping-assistant"],
)
assistant_service = AssistantService()


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_endpoint(
    payload: ConversationCreate,
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> ConversationResponse:
    """Create a private multi-turn conversation."""

    return assistant_service.create_conversation(
        database_session,
        user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
)
def list_conversations_endpoint(
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> ConversationListResponse:
    """List the authenticated user's conversations."""

    return assistant_service.list_conversations(
        database_session,
        user_id=current_user.id,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def read_conversation_endpoint(
    conversation_id: int = Path(ge=1),
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> ConversationDetailResponse:
    """Return one private conversation and its messages."""

    return assistant_service.get_conversation(
        database_session,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AssistantTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assistant_message_endpoint(
    payload: AssistantMessageCreate,
    conversation_id: int = Path(ge=1),
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> AssistantTurnResponse:
    """Persist a user message and return a grounded response."""

    return assistant_service.add_user_message(
        database_session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        payload=payload,
    )
