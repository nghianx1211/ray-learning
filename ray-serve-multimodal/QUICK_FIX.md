# 🚨 Quick Fix Guide - Single GPU Node

## Problem Summary

Bạn đang chạy trên node có **1 GPU** nhưng Ray LLM's vLLM engine tự động tạo placement groups yêu cầu nhiều GPU hơn.

### Resource Request Breakdown:
```
Required per model:
  - Actor bundle: {"CPU": 1.0, "GPU": 0.45}
  - Engine bundle: {"GPU": 1.0}  ← vLLM tự động tạo
  Total: 1.45 GPU ❌

Available: 1.0 GPU ❌
```

## ✅ Solutions

### Option 1: Deploy Only ONE Model (Recommended for 1 GPU)

Edit `multi_model_config.yaml` - comment out model thứ 2:

```yaml
applications:
  - name: "falcon3-1b-instruct-app"
    # ... keep this

  # - name: "falcon-h1-0.5b-instruct-app"  ← Comment out
  #   ... comment all of this
```

Then run:
```bash
python3 app_v5.py multi_model_config.yaml
```

###Option 2: Use Simpler Deployment (No vLLM Placement Groups)

Thử config đơn giản hơn mà tôi đã tạo:

```bash
python3 app_v5.py multi_model_config_simple.yaml
```

Config này:
- Dùng `num_gpus` thay vì `ray_actor_options`
- Giảm resources: 0.4 GPU per replica
- Có thể chạy 2 replicas trên 1 GPU

### Option 3: Add More GPU Nodes

Nếu cần chạy nhiều models, add thêm nodes vào cluster:

```bash
# On another machine with GPU:
ray start --address='<head-node-ip>:6379'
```

### Option 4: Sequential Deployment (Backup Plan)

Nếu vẫn không được, quay lại `app_v4.py`:

```bash
# Deploy model 1
python3 app_v4.py config_model1_only.yaml

# Wait for it to finish, then deploy model 2
python3 app_v4.py config_model2_only.yaml
```

## 🔧 Debugging Commands

### Check available resources:
```bash
ray status
```

Look for:
```
Resources
---------------------------------------------------------------
Total Usage:
 X/4.0 CPU
 Y/1.0 GPU  ← Should show available GPU
```

### Check Serve status:
```bash
# In Python:
from ray import serve
print(serve.status())
```

### Shutdown and retry:
```bash
# Shutdown all deployments
python3 -c "from ray import serve; import ray; ray.init(); serve.shutdown()"

# Try again
python3 app_v5.py multi_model_config_simple.yaml
```

## 📝 Working Config for 1 GPU Node

Create `single_model_config.yaml`:

```yaml
applications:
  - name: "falcon3-1b-app"
    import_path: "ray.serve.llm:build_openai_app"
    route_prefix: "/v1"
    args:
      llm_configs:
        - model_loading_config:
            model_id: "falcon3-1b"
            model_source: "tiiuae/Falcon3-1B-Instruct"
          deployment_config:
            name: "falcon3-1b"
            num_cpus: 1
            num_gpus: 0.9  # Use most of the GPU
            autoscaling_config:
              min_replicas: 1
              max_replicas: 1  # Only 1 replica on 1 GPU
          engine_kwargs:
            dtype: "float16"
            gpu_memory_utilization: 0.9
            max_model_len: 8192
            enforce_eager: true
            trust_remote_code: true
```

Run:
```bash
python3 app_v5.py single_model_config.yaml
```

## 🎯 Best Practice for Your Setup

**With 1 GPU node:**
- ✅ Deploy 1 large model OR
- ✅ Deploy 2 small models sequentially OR  
- ✅ Use simple config without placement groups

**Don't:**
- ❌ Try to deploy 2 models concurrently with vLLM engine
- ❌ Use `tensor_parallel_size > 0` on single GPU
- ❌ Set `ray_actor_options` with vLLM (causes placement group issues)

## 🚀 Next Steps

1. **Try Option 1** (single model) first
2. If that works, try `multi_model_config_simple.yaml`
3. If you need concurrent multi-model, add more GPU nodes

Let me know which option you want to try!
