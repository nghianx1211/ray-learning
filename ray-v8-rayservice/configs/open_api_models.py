"""This module contains the wrapper classes for vLLM's OpenAI implementation.

If there are any major differences in the interface, the expectation is that
they will be upstreamed to vLLM.
"""

from typing import TYPE_CHECKING, AsyncGenerator, Union

from pydantic import (
    ConfigDict,
    Field,
)
from vllm.entrypoints.openai.protocol import (
    ChatCompletionRequest as vLLMChatCompletionRequest,
    ChatCompletionResponse as vLLMChatCompletionResponse,
    ChatCompletionStreamResponse as vLLMChatCompletionStreamResponse,
    CompletionRequest as vLLMCompletionRequest,
    CompletionResponse as vLLMCompletionResponse,
    CompletionStreamResponse as vLLMCompletionStreamResponse,
    EmbeddingChatRequest as vLLMEmbeddingChatRequest,
    EmbeddingCompletionRequest as vLLMEmbeddingCompletionRequest,
    EmbeddingResponse as vLLMEmbeddingResponse,
    ErrorResponse as vLLMErrorResponse,
)
from vllm.utils import random_uuid


class ChatCompletionRequest(vLLMChatCompletionRequest):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ChatCompletionResponse(vLLMChatCompletionResponse):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ChatCompletionStreamResponse(vLLMChatCompletionStreamResponse):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ErrorResponse(vLLMErrorResponse):
    model_config = ConfigDict(arbitrary_types_allowed=True)


# TODO: Upstream
class CompletionRequest(vLLMCompletionRequest):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    request_id: str = Field(
        default_factory=lambda: f"{random_uuid()}",
        description=(
            "The request_id related to this request. If the caller does "
            "not set it, a random_uuid will be generated. This id is used "
            "through out the inference process and return in response."
        ),
    )


class CompletionResponse(vLLMCompletionResponse):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class CompletionStreamResponse(vLLMCompletionStreamResponse):
    model_config = ConfigDict(arbitrary_types_allowed=True)


# TODO: Upstream
class EmbeddingCompletionRequest(vLLMEmbeddingCompletionRequest):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    request_id: str = Field(
        default_factory=lambda: f"{random_uuid()}",
        description=(
            "The request_id related to this request. If the caller does "
            "not set it, a random_uuid will be generated. This id is used "
            "through out the inference process and return in response."
        ),
    )


class EmbeddingChatRequest(vLLMEmbeddingChatRequest):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class EmbeddingResponse(vLLMEmbeddingResponse):
    model_config = ConfigDict(arbitrary_types_allowed=True)


EmbeddingRequest = Union[EmbeddingCompletionRequest, EmbeddingChatRequest]

LLMEmbeddingsResponse = Union[
    AsyncGenerator[Union[EmbeddingResponse, ErrorResponse], None],
]

LLMChatResponse = Union[
    AsyncGenerator[Union[str, ChatCompletionResponse, ErrorResponse], None],
]

LLMCompletionsResponse = Union[
    AsyncGenerator[
        Union[CompletionStreamResponse, CompletionResponse, ErrorResponse], None
    ],
]
