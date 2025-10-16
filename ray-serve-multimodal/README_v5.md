# Ray Serve Multi-Model Deployment V5 (app_v5.py)

## 🎯 Cải tiến so với V4

### 1. **Concurrent Deployment (Deploy đồng thời)**
- ✅ Deploy nhiều models cùng lúc thay vì tuần tự
- ✅ Nhanh hơn đáng kể khi có nhiều models
- ✅ Không bị block khi một model load lâu

### 2. **Per-Replica Resource Allocation (Tài nguyên chính xác)**
- ✅ Mỗi replica chỉ dùng đúng số CPUs/GPUs được chỉ định
- ✅ Không chiếm full node resources
- ✅ Tự động map `num_cpus/cpus` và `num_gpus/gpus` vào `ray_actor_options`

## 🚀 Cách sử dụng

### Chạy cơ bản:
```bash
python3 app_v5.py multi_model_config.yaml
```

### Output mẫu:
```
🔧 Initializing Ray and Ray Serve...
📖 Loading config from: multi_model_config.yaml
📦 Found 2 application(s) to deploy
🔄 Starting concurrent deployment...

🚀 Deploying: falcon3-1b-instruct-app
   📦 Model ID: falcon3-1b-instruct
   🌐 Route: /falcon3-1b
   📊 Mapped resources to ray_actor_options: {'num_cpus': 1.0, 'num_gpus': 0.45}
   ✅ Deployed successfully: falcon3-1b-instruct-app

🚀 Deploying: falcon-h1-0.5b-instruct-app
   📦 Model ID: falcon-h1-0.5b-instruct
   🌐 Route: /falcon-h1-0.5b
   📊 Mapped resources to ray_actor_options: {'num_cpus': 1.0, 'num_gpus': 0.45}
   ✅ Deployed successfully: falcon-h1-0.5b-instruct-app

================================================================================
✅ Deployment Summary
================================================================================
Total applications deployed: 2/2

📋 Successfully Deployed Applications:
--------------------------------------------------------------------------------

• falcon3-1b-instruct-app
   Model: tiiuae/Falcon3-1B-Instruct
   Model ID: falcon3-1b-instruct
   Resources per replica: 1.0 CPUs, 0.45 GPUs
   Replicas: 1 → 3 (autoscaling)
   Base URL: http://localhost:8000/falcon3-1b
   Endpoints:
     • POST /falcon3-1b/v1/chat/completions
     • POST /falcon3-1b/v1/completions
     • GET  /falcon3-1b/v1/models

• falcon-h1-0.5b-instruct-app
   Model: tiiuae/falcon-h1-0.5b-instruct
   Model ID: falcon-h1-0.5b-instruct
   Resources per replica: 1.0 CPUs, 0.45 GPUs
   Replicas: 1 → 5 (autoscaling)
   Base URL: http://localhost:8000/falcon-h1-0.5b
   Endpoints:
     • POST /falcon-h1-0.5b/v1/chat/completions
     • POST /falcon-h1-0.5b/v1/completions
     • GET  /falcon-h1-0.5b/v1/models

================================================================================
🔥 All deployments completed!
💡 Ray Dashboard: http://localhost:8265
💡 Check deployment status and resource usage in the dashboard
================================================================================
```

## 📝 Config YAML

### Format hiện tại (tự động được xử lý):
```yaml
applications:
  - name: "falcon3-1b-instruct-app"
    import_path: "ray.serve.llm:build_openai_app"
    route_prefix: "/falcon3-1b"
    args:
      llm_configs:
        - model_loading_config:
            model_id: "falcon3-1b-instruct"
            model_source: "tiiuae/Falcon3-1B-Instruct"
          deployment_config:
            name: "falcon3-1b-deployment"
            ray_actor_options:
              num_cpus: 1        # ← Tự động map vào ray_actor_options
              num_gpus: 0.45     # ← Tự động map vào ray_actor_options
            autoscaling_config:
              min_replicas: 1
              max_replicas: 3
            # ... các config khác
```

### Hoặc dùng keys đơn giản hơn:
```yaml
deployment_config:
  name: "my-deployment"
  num_cpus: 1      # ← app_v5.py sẽ tự động chuyển thành ray_actor_options
  num_gpus: 0.45   # ← app_v5.py sẽ tự động chuyển thành ray_actor_options
```

### Hoặc dùng ray_actor_options trực tiếp (advanced):
```yaml
deployment_config:
  name: "my-deployment"
  ray_actor_options:
    num_cpus: 1
    num_gpus: 0.45
    resources:
      custom_resource: 1
    memory: 2000000000  # 2GB RAM
```

## 🔍 Kiểm tra tài nguyên

### Trong Ray Dashboard (http://localhost:8265):
1. Vào tab **Serve**
2. Click vào application name
3. Xem **Resources** của mỗi replica:
   - ✅ Mỗi replica có đúng 1 CPU + 0.45 GPU
   - ✅ Không có replica nào chiếm full node

### Command line check:
```bash
# Xem status của các deployments
ray serve status

# Xem resource usage
ray status
```

## 📊 So sánh V4 vs V5

| Feature | app_v4.py | app_v5.py |
|---------|-----------|-----------|
| **Deploy mode** | Sequential (tuần tự) | Concurrent (đồng thời) |
| **Speed** | Chậm với nhiều models | Nhanh hơn nhiều |
| **Resource per replica** | ❌ Có thể lấy full node | ✅ Chính xác theo config |
| **Error handling** | Stop khi có lỗi | Continue với models khác |
| **Thread pool** | Không | ✅ ThreadPoolExecutor |
| **Resource mapping** | Manual | ✅ Tự động |

## 🎯 Ví dụ thực tế

### Scenario 1: Node có 8 CPUs, 2 GPUs

**V4 behavior (có thể xảy ra):**
```
Model 1: Lấy 8 CPUs + 2 GPUs → Model 2 không deploy được!
```

**V5 behavior (chính xác):**
```
Model 1: 1 CPU + 0.45 GPU (per replica)
Model 2: 1 CPU + 0.45 GPU (per replica)
→ Có thể chạy nhiều replicas trên cùng node!
```

### Scenario 2: Deploy 5 models cùng lúc

**V4:**
```
Model 1 (3 phút) → Model 2 (3 phút) → Model 3 (3 phút) → Model 4 (3 phút) → Model 5 (3 phút)
= Tổng: 15 phút
```

**V5:**
```
Model 1 (3 phút) ┐
Model 2 (3 phút) ├─ Deploy song song
Model 3 (3 phút) ├─ Deploy song song  
Model 4 (3 phút) ├─ Deploy song song
Model 5 (3 phút) ┘
= Tổng: ~3 phút (nếu đủ resources)
```

## ⚙️ Advanced Options

### Giới hạn số threads deploy đồng thời:
Mặc định: `min(số_models, max(2, số_CPU_cores))`

Để thay đổi, edit trong `app_v5.py`:
```python
max_workers = 4  # Force 4 concurrent deployments
```

### Thêm custom resources:
```yaml
deployment_config:
  ray_actor_options:
    num_cpus: 1
    num_gpus: 0.45
    resources:
      my_custom_resource: 2
      accelerator_type:A100: 1
```

## 🐛 Troubleshooting

### Lỗi: "Insufficient resources"
**Nguyên nhân:** Node không đủ tài nguyên cho tất cả replicas

**Giải pháp:**
1. Giảm `min_replicas` trong config
2. Giảm `num_gpus` hoặc `num_cpus` per replica
3. Thêm nodes vào Ray cluster

### Lỗi: Model load lâu và timeout
**Giải pháp:**
1. Tăng timeout trong Ray config
2. Pre-download models trước khi deploy
3. Dùng local model path thay vì download từ HuggingFace

### Một số models deploy failed
**V5 advantage:** Không ảnh hưởng các models khác!

Check logs để xem lỗi cụ thể:
```bash
# Xem logs của deployment cụ thể
ray logs --follow deployment-name
```

## 📈 Best Practices

### 1. Resource Planning
```yaml
# Ví dụ: Node có 2 GPUs
# Muốn chạy 4 replicas → Mỗi replica dùng 0.5 GPU
deployment_config:
  ray_actor_options:
    num_gpus: 0.5
  autoscaling_config:
    min_replicas: 2
    max_replicas: 4
```

### 2. Autoscaling Config
```yaml
autoscaling_config:
  min_replicas: 1              # Start với 1 replica
  max_replicas: 5              # Scale up tối đa 5
  target_ongoing_requests: 85  # Scale khi có >85 requests
```

### 3. Testing Strategy
```bash
# 1. Test với 1 model trước
python3 app_v5.py test_single_model.yaml

# 2. Sau đó deploy tất cả
python3 app_v5.py multi_model_config.yaml
```

## 🚀 Quick Start Checklist

- [ ] Ray đã được cài đặt và start: `ray start --head`
- [ ] Config YAML đã sẵn sàng với resource specs
- [ ] Node có đủ resources (check `ray status`)
- [ ] Run: `python3 app_v5.py multi_model_config.yaml`
- [ ] Check dashboard: http://localhost:8265
- [ ] Test endpoints với curl hoặc Postman

## 📚 Additional Resources

- Ray Dashboard: http://localhost:8265
- Ray Serve Docs: https://docs.ray.io/en/latest/serve/
- Config examples: `multi_model_config.yaml`
- Old version: `app_v4.py` (for comparison)

## 🎉 Summary

**app_v5.py = Concurrent + Per-Replica Resources**

Đây là version production-ready với:
- ✅ Deploy nhanh hơn (concurrent)
- ✅ Resource allocation chính xác (per-replica)
- ✅ Error handling robust
- ✅ Detailed logging và monitoring
- ✅ Tương thích với config hiện tại

Enjoy! 🚀
