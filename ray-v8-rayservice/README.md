# Ray Serve Multi-Model Deployment Platform

## Overview

Multi-Model Deployment Platform System was built on **Ray Serve** and **VLLM**, allow for manage multiple model (LLM, Audio, Vision, Video) on the same cluster.

### Main feature

- **Multi-Model Support**: support multiple model (VLLM, Audio, Vision, Video)
- **Scalable Architecture**: Scale with Ray Serve
- **Unified API**: Same REST API for all model
- **GPU Optimization**: Optimize for GPU with CUDA graphs
- **Dynamic Routing**: Router route request to right model

### Technology

- **Ray Serve**: Framework serving
- **VLLM**: Engine optimize for LLM inference
- **FastAPI**: Web framework for REST API
- **Pydantic**: Data validation
- **CUDA**: GPU acceleration

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Request                          │
│                  (HTTP POST /v1/chat/completions)           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  MultiModelRouter                           │
│  - Route requests to appropriate deployment                 │
│  - Load balancing across replicas                           │
│  - Health checking                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              MultiModelDeployment                           │
│  - Manages multiple model instances                         │
│  - Handles CUDA device allocation                           │
│  - Coordinates MultiModelServer                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               MultiModelServer                              │
│  - Initializes and manages engines                          │
│  - Dispatches requests to correct engine                    │
│  - Handles concurrent requests                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬────────────┐
          ▼            ▼            ▼            ▼
    ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  VLLM   │  │  Audio   │  │ Vision   │  │  Video   │
    │ Engine  │  │Engine(N) │  │Engine(N) │  │Engine(N) │
    └─────────┘  └──────────┘  └──────────┘  └──────────┘
          │            │            │            │
          └────────────┴────────────┴────────────┘
                       │
                       ▼
                 ┌──────────┐
                 │   GPU    │
                 │  (CUDA)  │
                 └──────────┘
```

---

## Folder structure

```
/home/terraform/ray/
│
├── 📄 model_config.yaml         # Model configure
├── 📄 README.md                 # This docs
├── 📄 deploy_app.py             # deploy application directly (on VM)
├── 📄 .dockerignore             # dockerignore
├── 📄 .Dockerfile               # Dockerfile
├── 📄 requirements.txt          # library need to run
│
├── 📁 builders/                  # application builder folder
│   ├── app_builder.py            # build ray application
│   ├── rayservice_wrapper.py     # build app from yaml config
│
├── 📁 serve/                    # Ray Serve deployments and routing
│   ├── 📁 deployments/
│   │   ├── multi_model_deployment.py   # Ray Serve deployment wrapper
│   │   └── multi_model_server.py       # Server manage multiple engines
│   │
│   └── 📁 router/
│       └── router.py            # FastAPI router, redirect requests
│
├── 📁 servers/                 # Engine implementations
│   ├── base_engine.py          # Abstract base class for all engines
│   ├── vllm_engine.py          # VLLM engine cho LLM models
│   ├── audio_engine.py         # Engine cho audio models (TODO)
│   ├── vision_engine.py        # Engine cho vision models (TODO)
│   └── video_engine.py         # Engine cho video models (TODO)
│
├── 📁 configs/                  # Configuration models
│   ├── server_models.py        # Pydantic models cho LLM config
│   ├── audio_models.py         # Config cho audio models (TODO)
│   ├── vision_models.py        # Config cho vision models (TODO)
│   ├── video_models.py         # Config cho video models (TODO)
│   └── open_api_models.py      # OpenAPI schema definitions
│
├── 📁 common/                   # Shared utilities
│   └── base_pydantic.py        # Base Pydantic configurations
│
├── 📁 cloud/                    # Cloud deployment utilities
│   └── cloud_utils.py          # Utilities cho cloud deployment
│
└── 📁 venv/                     # Python virtual environment
```

---

## Configuration

### model_config.yaml Structure

```yaml
applications:
  - name: "falcon3-1b-instruct-app"
    import_path: "ray.serve.llm:build_openai_app"
    route_prefix: "/falcon3-1b"
    args:
      llm_configs:
        - model_loading_config:
            model_id: "falcon3-1b-instruct"           # Unique identifier
            model_source: "tiiuae/Falcon3-1B-Instruct"  # HuggingFace path
            type: "VLLM"                              # Engine type
          
          deployment_config:
            name: "falcon3-1b-deployment"
            ray_actor_options:
              num_cpus: 1                            # CPUs per replica
              num_gpus: 0.4                          # GPU fraction
            autoscaling_config:
              min_replicas: 1                        # Minimum instances
              max_replicas: 1                        # Maximum instances
              target_ongoing_requests: 50            # Scale trigger
            max_ongoing_requests: 256                # Max concurrent requests
          
          engine_kwargs:
            # VLLM-specific parameters
            tensor_parallel_size: 0                  # Multi-GPU (0 = auto)
            dtype: "float16"                         # Model precision
            gpu_memory_utilization: 0.4              # GPU memory fraction
            max_model_len: 8192                      # Max sequence length
            enforce_eager: false                     # Use CUDA graphs
            max_num_seqs: 256                        # Concurrent sequences
            max_num_batched_tokens: 32768            # Batch size
            trust_remote_code: true                  # Allow custom code
            disable_custom_all_reduce: true          # Disable custom kernels
```
---

## Performance Tuning

### GPU Optimization

```yaml
engine_kwargs:
  # Use CUDA graphs for 2-3x speedup
  enforce_eager: false
  
  # Maximize GPU utilization
  gpu_memory_utilization: 0.9  # Use 90% of GPU memory
  
  # Optimize batch size
  max_num_batched_tokens: 32768  # Higher = better throughput
  max_num_seqs: 256              # More concurrent requests
  
  # Enable chunked prefill
  # (Automatically enabled in VLLM)
```

### Scaling Configuration

```yaml
deployment_config:
  autoscaling_config:
    min_replicas: 2              # Always have 2 instances
    max_replicas: 4              # Scale up to 4 under load
    target_ongoing_requests: 25  # Scale when >25 pending requests
  
  max_ongoing_requests: 100      # Queue up to 100 requests
```

### Network Optimization

```python
# Increase timeout for large responses
DEFAULT_LLM_ROUTER_HTTP_TIMEOUT = 300  # 5 minutes

# Enable connection pooling
# (Handled by Ray Serve automatically)
```
---

### Multi-GPU Deployment

```yaml
engine_kwargs:
  tensor_parallel_size: 2  # Use 2 GPUs per model
  
ray_actor_options:
  num_gpus: 2  # Reserve 2 GPUs per replica
```

```bash
# Set multiple GPUs visible
export CUDA_VISIBLE_DEVICES=0,1

# Ray will distribute work across GPUs
```

### Production Deployment

```yaml
# Use Kubernetes with Ray operator
# Or AWS/GCP managed Ray clusters

deployment_config:
  autoscaling_config:
    min_replicas: 4
    max_replicas: 20
    target_ongoing_requests: 50
  
  # Add resource requests
  ray_actor_options:
    num_cpus: 4
    num_gpus: 1
    memory: 16 * 1024 * 1024 * 1024  # 16GB
    
    # Use placement groups for co-location
    placement_group_bundles: [{"GPU": 1, "CPU": 4}]
```

---