import ray
from common.base_pydantic import BaseModelExtended
from cloud.cloud_utils import CloudMirrorConfig
from pydantic import Field
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

class ModelLoadingConfig(BaseModelExtended):
    model_id: str = Field(
        description="The ID that should be used by end users to access this model.",
    )
    
    model_source: Optional[Union[str, CloudMirrorConfig]] = Field(
        default=None,
        description=(
            "Where to obtain the model weights from. "
            "Should be a HuggingFace model ID, S3 mirror config, GCS mirror config, "
            "or a local path. When omitted, defaults to the model_id as a "
            "HuggingFace model ID."
        ),
    )

    tokenizer_source: Optional[str] = Field(
        default=None,
        description=(
            "Where to obtain the tokenizer from. If None, tokenizer is "
            "obtained from the model source. Only HuggingFace IDs are "
            "supported for now."
        ),
    )

    type: Optional[str] = Field(
        default="VLLM",
        description=(
            "Where to obtain type of model. If None, Type default"
            "Type (VLLM, VISION, AUDIO, VIDEO)"
            "supported for now."
        ),
    )


class MultiModelConfig(BaseModelExtended):
    model_loading_config: Union[Dict[str, Any], ModelLoadingConfig] = Field(
        description="The settings for how to download and expose the model. Validated against ModelLoadingConfig."
    )

    engine_kwargs: Dict[str, Any] = Field(
        default={},
        description=(
            "Additional keyword arguments for the engine. In case of vLLM, "
            "this will include all the configuration knobs they provide out "
            "of the box, except for tensor-parallelism which is set "
            "automatically from Ray Serve configs."
        ),
    )

    deployment_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
            The Ray @server.deployment options.
            Supported fields are:
            `name`, `num_replicas`, `ray_actor_options`, `max_ongoing_requests`,
            `autoscaling_config`, `max_queued_requests`, `user_config`,
            `health_check_period_s`, `health_check_timeout_s`,
            `graceful_shutdown_wait_loop_s`, `graceful_shutdown_timeout_s`,
            `logging_config`, `request_router_config`.
            For more details, see the `Ray Serve Documentation <https://docs.ray.io/en/latest/serve/configure-serve-deployment.html>`_.
        """,
    )
