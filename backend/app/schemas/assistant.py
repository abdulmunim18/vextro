"""Schemas for the grounded conversational shopping assistant."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssistantInputModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ConversationCreate(AssistantInputModel):
    """Create a private assistant conversation."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
    )


class AssistantMessageCreate(AssistantInputModel):
    """Submit one user message."""

    content: str = Field(
        min_length=1,
        max_length=2000,
    )


class AssistantMessageResponse(BaseModel):
    """Stored user or assistant message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    intent: str | None
    entities: dict[str, object] = Field(default_factory=dict)
    grounded_data: dict[str, object] = Field(default_factory=dict)
    data_timestamp: datetime | None
    created_at: datetime


class ConversationResponse(BaseModel):
    """Conversation metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    context: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(ConversationResponse):
    """Conversation with its ordered messages."""

    messages: list[AssistantMessageResponse] = Field(
        default_factory=list,
    )


class ConversationListResponse(BaseModel):
    """Authenticated user's conversations."""

    total: int = Field(ge=0)
    items: list[ConversationResponse] = Field(default_factory=list)


class AssistantTurnResponse(BaseModel):
    """The persisted user message and grounded assistant response."""

    conversation: ConversationResponse
    user_message: AssistantMessageResponse
    assistant_message: AssistantMessageResponse
