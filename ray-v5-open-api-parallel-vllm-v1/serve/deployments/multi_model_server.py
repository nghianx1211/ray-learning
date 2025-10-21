# servers/multimodel_server.py
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from ray.llm._internal.serve.observability.logging import get_logger

from servers.base_engine import BaseEngine
from configs.server_models import MultiModelConfig

logger = get_logger(__name__)

ENGINE_REGISTRY = {}

def register_engine(engine_type: str):
    """Decorator to register new engine classes."""
    def wrapper(cls):
        ENGINE_REGISTRY[engine_type.upper()] = cls
        return cls
    return wrapper

# Import all engine implementations to trigger their registration
# Must be imported AFTER register_engine is defined to avoid circular import
import servers.vllm_engine
# import servers.audio_engine
# import servers.vision_engine
# import servers.video_engine


class MultiModelServer:
    """
    Generalized version of LLMServer that can load multiple models of different types.
    Supported types: VLLM, AUDIO, VISION, VIDEO, CUSTOM.
    """

    def __init__(self, llm_configs: List[MultiModelConfig]):
        self.llm_configs = llm_configs
        self.models: Dict[str, BaseEngine] = {}
        self.ready = asyncio.Event()

    async def start(self):
        """Load all models concurrently."""
        logger.info(f"Starting MultiModelServer with {len(self.llm_configs)} models...")
        tasks = [self._start_model(cfg) for cfg in self.llm_configs]
        await asyncio.gather(*tasks)
        self.ready.set()
        logger.info("All models initialized and ready.")

    async def _start_model(self, cfg: MultiModelConfig):
        """Helper to start a single model."""
        model_id = cfg.model_loading_config["model_id"]
        model_source = cfg.model_loading_config.get("model_source", model_id)
        model_type = cfg.model_loading_config.get("type", "VLLM").upper()
        engine_cls = ENGINE_REGISTRY.get(model_type)

        if not engine_cls:
            raise ValueError(f"Unsupported engine type '{model_type}' for {model_id}")

        engine = engine_cls(model_id=model_id, model_source=model_source, **cfg.engine_kwargs)
        await engine.start()
        self.models[model_id] = engine
        logger.info(f"Loaded {model_type} model: {model_id}")

    async def infer(self, model_id: str, request: Any) -> AsyncGenerator[Any, None]:
        """Dispatch inference to correct engine."""
        await self.ready.wait()
        logger.info(f"Received inference request for model_id: {model_id}")
        if model_id not in self.models:
            logger.error(f"Model '{model_id}' not found")
            raise ValueError(f"Model '{model_id}' not found")
        engine = self.models[model_id]
        logger.info(f"Dispatching inference to engine: {engine.__class__.__name__} for model_id: {model_id}")
        try:
            async for chunk in engine.infer(request):
                logger.debug(f"Inference chunk from {model_id}: {chunk}")
                yield chunk
            logger.info(f"Inference completed for model_id: {model_id}")
        except Exception as e:
            logger.error(f"Inference failed for model_id: {model_id}: {e}")
            raise

    async def chat_completions(self, model_id: str, request: Any) -> AsyncGenerator[Any, None]:
        """Dispatch chat completions to correct engine."""
        await self.ready.wait()
        logger.info(f"Received chat completions request for model_id: {model_id}")
        if model_id not in self.models:
            logger.error(f"Model '{model_id}' not found")
            raise ValueError(f"Model '{model_id}' not found")
        engine = self.models[model_id]
        logger.info(f"Dispatching chat completions to engine: {engine.__class__.__name__} for model_id: {model_id}")
        try:
            async for chunk in engine.chat_completions(request):
                logger.debug(f"Chat completion chunk from {model_id}: {chunk}")
                yield chunk
            logger.info(f"Chat completions completed for model_id: {model_id}")
        except Exception as e:
            logger.error(f"Chat completions failed for model_id: {model_id}: {e}")
            raise

    async def completions(self, model_id: str, request: Any) -> AsyncGenerator[Any, None]:
        """Dispatch completions to correct engine."""
        await self.ready.wait()
        logger.info(f"Received completions request for model_id: {model_id}")
        if model_id not in self.models:
            logger.error(f"Model '{model_id}' not found")
            raise ValueError(f"Model '{model_id}' not found")
        engine = self.models[model_id]
        logger.info(f"Dispatching completions to engine: {engine.__class__.__name__} for model_id: {model_id}")
        try:
            async for chunk in engine.completions(request):
                logger.debug(f"Completion chunk from {model_id}: {chunk}")
                yield chunk
            logger.info(f"Completions completed for model_id: {model_id}")
        except Exception as e:
            logger.error(f"Completions failed for model_id: {model_id}: {e}")
            raise

    async def check_health(self):
        """Check all models' health."""
        for mid, engine in self.models.items():
            try:
                await engine.check_health()
            except Exception as e:
                logger.error(f"Health check failed for {mid}: {e}")
                raise
