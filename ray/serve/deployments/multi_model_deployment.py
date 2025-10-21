# deployments/multimodel_deployment.py
from ray import serve
import asyncio
import os
from typing import AsyncGenerator, Any, Dict, List
from ray.llm._internal.serve.configs.server_models import LLMConfig
from ray.llm._internal.serve.observability.logging import get_logger

from serve.deployments.multi_model_server import MultiModelServer

logger = get_logger(__name__)


@serve.deployment(
    autoscaling_config={
        "min_replicas": 1,
        "initial_replicas": 1,
        "max_replicas": 2,
        "target_ongoing_requests": 50,
    },
    max_ongoing_requests=256,
    health_check_period_s=10,
    health_check_timeout_s=5,
)
class MultiModelDeployment:
    """
    Deployment host nhiều loại model (VLLM, AUDIO, VISION, VIDEO) trong cùng server.
    Mỗi model sẽ có metadata riêng, router sẽ dùng get_config() để đăng ký model.
    """

    def __init__(self, llm_configs: List[LLMConfig]):
        # CRITICAL: Ensure CUDA_VISIBLE_DEVICES is set in actual OS environment
        # This is required for VLLM multiprocessing.spawn to work properly
        cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '')
        if not cuda_devices:
            # If not set, default to GPU 0
            cuda_devices = '0'
            os.environ['CUDA_VISIBLE_DEVICES'] = cuda_devices
        
        logger.info(f"⚙️ CUDA_VISIBLE_DEVICES={cuda_devices}")
        
        # Server quản lý nhiều model khác nhau
        self.server = MultiModelServer(llm_configs)
        self.models: Dict[str, Dict[str, Any]] = {}

        for cfg in llm_configs:
            model_id = cfg.model_loading_config.get("model_id", "unknown-model")
            model_type = cfg.model_loading_config.get("type", "VLLM").upper()
            self.models[model_id] = {
                "model_id": model_id,
                "type": model_type,
                "engine_kwargs": cfg.engine_kwargs,
                "deployment_config": cfg.deployment_config,
            }

            logger.info(
                f"🧩 Registered model in deployment: {model_id} ({model_type})"
            )

        # Khởi động async server - đợi cho đến khi hoàn tất
        self._start_task = None

    async def _ensure_started(self):
        """Ensure server is started before processing requests."""
        if self._start_task is None:
            self._start_task = asyncio.create_task(self.server.start())
        await self._start_task

    # ------------------------------------------------------------------
    # Public API (Router sẽ gọi qua DeploymentHandle)
    # ------------------------------------------------------------------
    async def get_config(self) -> Dict[str, Any]:
        """
        Return metadata cho router biết model_id và type.
        Router sẽ tự động gọi hàm này khi đăng ký model.
        """
        return {
            "models": list(self.models.values()),
            "deployment_name": self.__class__.__name__,
        }

    async def check_health(self) -> Dict[str, Any]:
        """Kiểm tra health của tất cả model."""
        await self._ensure_started()
        status = await self.server.check_health()
        return {"status": "healthy", "models": list(self.models.keys())}

    async def infer(self, request: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        """
        Unified inference entrypoint — dùng cho mọi loại model.
        Expect body: {"model_id": "...", "input": "...", "params": {...}}
        """
        logger.info(f"Received inference request: {request}")

        model_id = request.get("model_id")
        if not model_id:
            logger.warning("Missing model_id in request")
            yield {"error": "Missing model_id in request"}
            return

        if model_id not in self.models:
            logger.warning(f"Model {model_id} not found in deployment")
            yield {"error": f"Model {model_id} not found in deployment"}
            return

        logger.info(f"🔁 Running inference for model {model_id}")
        
        # Ensure server is started
        await self._ensure_started()
        logger.info(f"Server is ready, dispatching inference...")

        try:
            async for chunk in self.server.infer(model_id, request):
                logger.debug(f"Yielding chunk for model {model_id}: {chunk}")
                yield chunk
            logger.info(f"Inference completed for model {model_id}")
        except Exception as e:
            logger.error(f"❌ Inference failed for {model_id}: {e}")
            yield {"error": str(e)}
