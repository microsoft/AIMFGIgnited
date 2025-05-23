from typing import List, Literal, Optional, Dict, TypedDict
from pydantic import BaseModel


class SearchConfig(TypedDict):
    """Configuration for search parameters."""

    chunk_count: int = 10
    openai_api_mode: Literal["chat_completions"] = "chat_completions"
    use_semantic_ranker: bool = False
    use_streaming: bool = False
    use_knowledge_agent: bool = False


class SearchRequestParameters(TypedDict):
    """Structure for search request payload."""

    search: str
    top: int = 10
    vector_queries: Optional[List[Dict[str, str]]] = None
    semantic_configuration_name: Optional[str] = None
    search_fields: Optional[List[str]] = None


class GroundingResult(TypedDict):
    """Structure for individual grounding results."""

    ref_id: str
    content: dict
    content_type: Literal["text", "image"]


class GroundingResults(TypedDict):
    """Structure for grrounding results with references and queries."""

    references: List[GroundingResult]
    search_queries: List[str]


class AnswerFormat(BaseModel):
    """Format for chat completion responses."""

    answer: str
    text_citations: List[str] = []
    image_citations: List[str] = []


class MessageContent(TypedDict):
    text: str
    type: Literal["text"]


class Message(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: List[MessageContent]
