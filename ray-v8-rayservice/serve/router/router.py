# multi_model_router.py
import asyncio
import json
import sys
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response, StreamingResponse
from ray import serve
from ray._common.utils import get_or_create_event_loop
from ray.serve.handle import DeploymentHandle
import async_timeout
from configs.open_api_models import (ChatCompletionRequest,
                                      ChatCompletionResponse,
                                        ChatCompletionStreamResponse,
                                         CompletionRequest,
                                           CompletionResponse,
                                             CompletionStreamResponse,
                                                       ErrorResponse,
                                                       LLMChatResponse,
                                                       LLMCompletionsResponse)

# Optional: can reuse Ray LLM constants for default scaling
from ray.llm._internal.serve.configs.constants import (
    DEFAULT_MAX_ONGOING_REQUESTS,
    DEFAULT_LLM_ROUTER_HTTP_TIMEOUT,
    DEFAULT_ROUTER_TO_MODEL_REPLICA_RATIO,
)

# Replace serve.get_logger with Python's logging module
logger = logging.getLogger("MultiModelRouter")
logging.basicConfig(level=logging.INFO)

# ----------------------------------------------------------------------
# 1️⃣ FastAPI app setup
# ----------------------------------------------------------------------
def init_router_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app

router_app = init_router_app()


# ----------------------------------------------------------------------
# 2️⃣ MultiModelRouter class
# ----------------------------------------------------------------------
class MultiModelRouter:
    """
    A generalized router that can route requests to LLM, Audio, Vision, Video deployments.
    """

    def __init__(self, model_deployments: List[DeploymentHandle]):
        self._handles: Dict[str, DeploymentHandle] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._init_completed = asyncio.Event()
        get_or_create_event_loop().create_task(
            self._setup_handle_map(model_deployments)
        )

    async def _setup_handle_map(self, model_deployments: List[DeploymentHandle]):
        for handle in model_deployments:
            try:
                # 🔧 chỉ gọi get_config()
                model_config = await handle.get_config.remote()

                # Nếu trả về nhiều models (MultiModelDeployment)
                if "models" in model_config:
                    for m in model_config["models"]:
                        model_id = m["model_id"]
                        model_type = m.get("type", "VLLM").upper()
                        self._handles[model_id] = handle
                        self._configs[model_id] = m
                        logger.info(f"Registered model {model_id} ({model_type})")
                else:
                    # Trường hợp đơn model
                    model_id = model_config["model_id"]
                    model_type = model_config.get("type", "VLLM").upper()
                    self._handles[model_id] = handle
                    self._configs[model_id] = model_config
                    logger.info(f"Registered model {model_id} ({model_type})")

            except Exception as e:
                logger.error(f"Failed to register model: {e}")

        self._init_completed.set()


    async def check_health(self):
        await self._init_completed.wait()

    def _get_handle(self, model_id: str) -> DeploymentHandle:
        if model_id not in self._handles:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Model '{model_id}' not found.")
        return self._handles[model_id]

    # ------------------------------------------------------------------
    # Routing logic by model type
    # ------------------------------------------------------------------
    async def infer(self, body: Dict[str, Any]) -> Response:
        """
        Unified inference endpoint for all types.
        Expect: {"model_id": "...", "input": "...", "params": {...}}
        """
        await self._init_completed.wait()
        model_id = body.get("model_id")
        if not model_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing model_id in request")

        handle = self._get_handle(model_id)
        model_cfg = self._configs[model_id]
        model_type = model_cfg.get("type", "VLLM").upper()

        logger.info(f"Routing request to {model_type}:{model_id} via infer")
        logger.debug(f"Request body: {body}")

        try:
            async with async_timeout.timeout(DEFAULT_LLM_ROUTER_HTTP_TIMEOUT):
                generator = handle.options(stream=True).infer.remote(body)
                result = await generator.__anext__()
                logger.debug(f"Model response: {result}")
                return JSONResponse(content=result if isinstance(result, dict) else {"result": result})
        except Exception as e:
            logger.error(f"Error during inference: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Inference failed: {str(e)}")
        
    async def chat_completions(self, request: ChatCompletionRequest) -> Response:
        """
        OpenAI-compatible chat completions endpoint.
        """
        await self._init_completed.wait()
        model_id = request.model
        if not model_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing model in request")

        handle = self._get_handle(model_id)
        model_cfg = self._configs[model_id]
        model_type = model_cfg.get("type", "VLLM").upper()

        logger.info(f"Routing chat completions request to {model_type}:{model_id}")
        logger.debug(f"Request: {request}")

        try:
            # Convert request to dict for serialization
            request_dict = request.model_dump() if hasattr(request, 'model_dump') else request.dict()
            
            async with async_timeout.timeout(DEFAULT_LLM_ROUTER_HTTP_TIMEOUT):
                if request.stream:
                    # Streaming response
                    async def generate():
                        generator = handle.options(stream=True).chat_completions.remote(request_dict)
                        async for chunk in generator:
                            if isinstance(chunk, dict) and "error" in chunk:
                                yield f"data: {json.dumps(chunk)}\n\n"
                            else:
                                chunk_dict = chunk.model_dump() if hasattr(chunk, 'model_dump') else (chunk.dict() if hasattr(chunk, 'dict') else chunk)
                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                        yield "data: [DONE]\n\n"
                    
                    return StreamingResponse(generate(), media_type="text/event-stream")
                else:
                    # Non-streaming response
                    generator = handle.options(stream=True).chat_completions.remote(request_dict)
                    result = await generator.__anext__()
                    logger.debug(f"Model response: {result}")
                    result_dict = result.model_dump() if hasattr(result, 'model_dump') else (result.dict() if hasattr(result, 'dict') else result)
                    return JSONResponse(content=result_dict)
        except Exception as e:
            logger.error(f"Error during chat completions: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Chat completions failed: {str(e)}")

    async def completions(self, request: CompletionRequest) -> Response:
        """
        OpenAI-compatible completions endpoint.
        """
        await self._init_completed.wait()
        model_id = request.model
        if not model_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing model in request")

        handle = self._get_handle(model_id)
        model_cfg = self._configs[model_id]
        model_type = model_cfg.get("type", "VLLM").upper()

        logger.info(f"Routing completions request to {model_type}:{model_id}")
        logger.debug(f"Request: {request}")

        try:
            # Convert request to dict for serialization
            request_dict = request.model_dump() if hasattr(request, 'model_dump') else request.dict()
            
            async with async_timeout.timeout(DEFAULT_LLM_ROUTER_HTTP_TIMEOUT):
                if request.stream:
                    # Streaming response
                    async def generate():
                        generator = handle.options(stream=True).completions.remote(request_dict)
                        async for chunk in generator:
                            if isinstance(chunk, dict) and "error" in chunk:
                                yield f"data: {json.dumps(chunk)}\n\n"
                            else:
                                chunk_dict = chunk.model_dump() if hasattr(chunk, 'model_dump') else (chunk.dict() if hasattr(chunk, 'dict') else chunk)
                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                        yield "data: [DONE]\n\n"
                    
                    return StreamingResponse(generate(), media_type="text/event-stream")
                else:
                    # Non-streaming response
                    generator = handle.options(stream=True).completions.remote(request_dict)
                    result = await generator.__anext__()
                    logger.debug(f"Model response: {result}")
                    result_dict = result.model_dump() if hasattr(result, 'model_dump') else (result.dict() if hasattr(result, 'dict') else result)
                    return JSONResponse(content=result_dict)
        except Exception as e:
            logger.error(f"Error during completions: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Completions failed: {str(e)}")

    # ------------------------------------------------------------------
    # REST endpoints
    # ------------------------------------------------------------------
    @router_app.post("/v1/infer")
    async def infer_api(self, body: Dict[str, Any]):
        """General multimodal inference endpoint."""
        return await self.infer(body)
    
    @router_app.post("/v1/chat/completions", summary="Chat completion endpoint")
    async def chat_completions_api(self, request: ChatCompletionRequest):
        """
        OpenAI-compatible chat completions endpoint.
        """
        return await self.chat_completions(request)
    
    @router_app.post("/v1/completions", summary="Completion endpoint")
    async def completions_api(self, request: CompletionRequest):
        """
        OpenAI-compatible completions endpoint.
        """
        return await self.completions(request)

    @router_app.get("/v1/models")
    async def list_models(self):
        """List all registered models."""
        await self._init_completed.wait()
        return JSONResponse(
            content={"models": list(self._configs.values())}
        )

    @router_app.get("/v1/models/{model_id}")
    async def model_info(self, model_id: str):
        await self._init_completed.wait()
        if model_id not in self._configs:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Model '{model_id}' not found.")
        return JSONResponse(content=self._configs[model_id])

    # ------------------------------------------------------------------
    # Deployment factory
    # ------------------------------------------------------------------
    @classmethod
    def as_deployment(cls, model_configs: Optional[List[Dict[str, Any]]] = None) -> serve.Deployment:
        """Wrap this router into a Ray Serve deployment."""
        min_replicas = 1
        initial_replicas = 1
        max_replicas = 2

        if model_configs:
            min_replicas = max(1, int(len(model_configs) * DEFAULT_ROUTER_TO_MODEL_REPLICA_RATIO))
            initial_replicas = min_replicas
            max_replicas = max(2, min_replicas * 2)

        ingress_cls = serve.ingress(router_app)(cls)
        deployment_cls = serve.deployment(
            autoscaling_config={
                "min_replicas": min_replicas,
                "initial_replicas": initial_replicas,
                "max_replicas": max_replicas,
                "target_ongoing_requests": 50,
            },
            max_ongoing_requests=DEFAULT_MAX_ONGOING_REQUESTS,
        )(ingress_cls)
        return deployment_cls
