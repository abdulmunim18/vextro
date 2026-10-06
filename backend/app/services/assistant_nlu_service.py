"""Optional Gemini-backed natural-language understanding for the assistant.

The model is deliberately kept outside the factual answer path. It may decide
which catalog operation the user wants and extract filters, but product facts,
availability and prices are always read from VEXTRO's PostgreSQL data.
"""

import json
import logging
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import settings


logger = logging.getLogger(__name__)


AssistantIntent = Literal[
    "set_price_alert",
    "comparison",
    "price_history",
    "buy_or_wait",
    "recommendation",
    "product_details",
    "lowest_price",
    "greeting",
    "acknowledgement",
    "product_search",
]

RequestedField = Literal[
    "ram",
    "storage",
    "camera",
    "battery",
    "processor",
    "display",
    "price",
    "rating",
]


class AssistantNLUResult(BaseModel):
    """Strict, validated interpretation returned by the language model."""

    intent: AssistantIntent
    budget_min: int | None = Field(default=None, ge=1000)
    budget_max: int | None = Field(default=None, ge=1000)
    category: Literal[
        "Mobile Phones",
        "Laptops",
        "Tablets",
        "Smart Watches",
        "Audio and Earbuds",
        "Power Banks",
        "Mobile Accessories",
    ] | None = None
    brand: str | None = Field(default=None, max_length=80)
    ram_gb: int | None = Field(default=None, ge=1, le=128)
    storage_gb: int | None = Field(default=None, ge=1, le=8192)
    preference: Literal["camera"] | None = None
    reference: Literal["first", "second", "current", "all"] | None = None
    requested_fields: list[RequestedField] = Field(default_factory=list)
    needs_clarification: bool = False

    def extracted_entities(self) -> dict[str, object]:
        """Return only values understood by the deterministic catalog layer."""

        result: dict[str, object] = {}
        for field in (
            "budget_min",
            "budget_max",
            "category",
            "brand",
            "ram_gb",
            "storage_gb",
            "preference",
            "reference",
        ):
            value = getattr(self, field)
            if value is not None:
                result[field] = str(value) if field.startswith("budget_") else value
        if self.requested_fields:
            result["requested_fields"] = list(dict.fromkeys(self.requested_fields))
        if self.needs_clarification:
            result["needs_clarification"] = True
        return result


class GeminiAssistantNLUService:
    """Interpret shopping messages with Gemini and fail closed on API errors."""

    @property
    def is_configured(self) -> bool:
        return bool(settings.assistant_ai_enabled and settings.gemini_api_key)

    def analyze(
        self,
        message: str,
        *,
        context: dict[str, object] | None = None,
    ) -> AssistantNLUResult | None:
        if not self.is_configured:
            return None

        safe_context = {
            key: value
            for key, value in (context or {}).items()
            if key in {
                "last_intent",
                "product_ids",
                "product_names",
                "selected_product_id",
                "comparison_product_ids",
                "budget_min",
                "budget_max",
                "category",
                "brand",
                "ram_gb",
                "storage_gb",
                "preference",
            }
        }
        prompt = (
            "Classify this VEXTRO shopping-assistant message. Understand English, "
            "Urdu and informal Roman Urdu, including spelling mistakes. Extract only "
            "facts explicitly present in the message or an unambiguous reference to "
            "the supplied conversation context. Use recommendation for budget/category "
            "requests such as '60k ke andar mobile dikhao'. Use product_details for a "
            "requested specification such as RAM. Use buy_or_wait for questions such "
            "as 'kya mujhe ye phone abhi lena chahiye?'. When multiple remembered "
            "products exist and the target is not clear, set "
            "needs_clarification=true. Never "
            "invent a product, brand, price, or specification.\n\n"
            f"Conversation context: {json.dumps(safe_context, ensure_ascii=True)}\n"
            f"User message: {message}"
        )

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            try:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=AssistantNLUResult,
                        automatic_function_calling=(
                            types.AutomaticFunctionCallingConfig(disable=True)
                        ),
                    ),
                )
                if isinstance(response.parsed, AssistantNLUResult):
                    return response.parsed
                if response.text:
                    return AssistantNLUResult.model_validate_json(response.text)
            finally:
                client.close()
        except Exception as error:  # API/network/quota errors must not break chat.
            logger.warning(
                "Gemini assistant interpretation failed; using local fallback: %s",
                type(error).__name__,
            )
        return None
