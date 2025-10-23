# servers/base_engine.py
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class BaseEngine(ABC):
    """Base interface for all engine types (LLM, Audio, Vision, Video)."""

    def __init__(self, model_id: str, model_source: str = None, **kwargs):
        self.model_id = model_id
        self.model_source = (
            model_source or model_id
        )  # Fallback to model_id if not provided
        self.kwargs = kwargs

    @abstractmethod
    async def start(self):
        """Load model into memory."""
        ...

    @abstractmethod
    async def infer(self, request: Any) -> AsyncGenerator[Any, None]:
        """Run inference."""
        ...

    @abstractmethod
    async def chat_completions(self, request: Any) -> AsyncGenerator[Any, None]:
        """Run Chat completions."""
        ...

    @abstractmethod
    async def completions(self, request: Any) -> AsyncGenerator[Any, None]:
        """Run completions."""
        ...

    @abstractmethod
    async def check_health(self):
        """Verify that model/engine is healthy."""
        ...
