# Ray Serve Multi-Model Deployment (app_v4.py)

## Tổng quan

`app_v4.py` hỗ trợ deploy nhiều LLM models cùng lúc với Ray Serve. Mỗi model:
- Có route riêng biệt
- Có config riêng (GPU, CPU, autoscaling, ...)
- OpenAI-compatible API endpoints
- Có thể thêm/xóa bằng cách chỉnh YAML

## Cấu trúc YAML Config

```yaml
applications:
  - name: "model-app-name"              # Tên application (unique)
    import_path: "ray.serve.llm:build_openai_app"
    route_prefix: "/model-route"        # Route prefix cho model này
    args:
      llm_configs:
        - model_loading_config:
            model_id: "model-id"        # ID model (tùy chọn)
            model_source: "org/model"   # Nguồn model (HF, S3, local)
          deployment_config:
            name: "deployment-name"     # Tên deployment
            ray_actor_options:
              num_cpus: 2               # Số CPU
              num_gpus: 1               # Số GPU
            autoscaling_config:
              min_replicas: 1           # Min replicas
              max_replicas: 3           # Max replicas
              target_ongoing_requests: 85
            max_ongoing_requests: 100
          engine_kwargs:
            tensor_parallel_size: 1
            dtype: "float16"
            gpu_memory_utilization: 0.9
            max_model_len: 8192
            # ... các tham số vLLM khác
```

## Cách sử dụng

### 1. Deploy multi-model

```bash
python app_v4.py multi_model_config.yaml
```

### 2. Test endpoints

Mỗi model có endpoint riêng với route prefix:

**Model 1: Falcon 3-1B** (route: `/falcon3-1b`)
```bash
# Chat completions
curl -X POST http://localhost:8000/falcon3-1b/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "falcon3-1b-instruct",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Text completions
curl -X POST http://localhost:8000/falcon3-1b/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "falcon3-1b-instruct",
    "prompt": "Hello"
  }'

# List models
curl http://localhost:8000/falcon3-1b/v1/models
```

**Model 2: Falcon H1-0.5B** (route: `/falcon-h1-0.5b`)
```bash
curl -X POST http://localhost:8000/falcon-h1-0.5b/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "falcon-h1-0.5b-instruct",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 3. Thêm model mới

Để thêm model mới, chỉ cần thêm block mới vào `applications` trong YAML:

```yaml
applications:
  # ... models hiện tại ...
  
  # Model mới
  - name: "new-model-app"
    import_path: "ray.serve.llm:build_openai_app"
    route_prefix: "/new-model"
    args:
      llm_configs:
        - model_loading_config:
            model_id: "new-model-id"
            model_source: "org/new-model"
          deployment_config:
            name: "new-model-deployment"
            ray_actor_options:
              num_cpus: 4
              num_gpus: 1
            autoscaling_config:
              min_replicas: 1
              max_replicas: 3
              target_ongoing_requests: 85
            max_ongoing_requests: 100
          engine_kwargs:
            tensor_parallel_size: 1
            dtype: "float16"
            gpu_memory_utilization: 0.9
            max_model_len: 8192
            enforce_eager: true
            max_num_seqs: 64
            max_num_batched_tokens: 8192
            trust_remote_code: true
            disable_custom_all_reduce: true
```

Sau đó stop và restart application:

```bash
# Stop
Ctrl+C

# Restart với config mới
python app_v4.py multi_model_config.yaml
```

### 4. Monitor deployments

Ray Dashboard: http://localhost:8265

## Tính năng

✅ **Multi-model support**: Deploy nhiều models cùng lúc
✅ **Độc lập route**: Mỗi model có route riêng
✅ **Dynamic config**: Thêm/xóa model bằng YAML
✅ **Autoscaling**: Tự động scale theo traffic
✅ **OpenAI-compatible**: API tương thích OpenAI
✅ **Resource management**: Cấu hình CPU/GPU riêng cho từng model

## Lưu ý

- Mỗi model cần đủ GPU/CPU resources
- `tensor_parallel_size: 1` để tránh lỗi multi-GPU
- Route prefix phải unique cho mỗi model
- Application name phải unique
- Deployment name phải unique

## Ví dụ use case

**Use case 1: Multi-size models**
- Model nhỏ (0.5B) cho tasks đơn giản
- Model lớn (7B) cho tasks phức tạp
- Frontend routing dựa vào độ phức tạp

**Use case 2: A/B testing**
- Model A: phiên bản stable
- Model B: phiên bản experimental
- So sánh performance

**Use case 3: Specialized models**
- Model 1: Chat/conversation
- Model 2: Code generation
- Model 3: Summarization
