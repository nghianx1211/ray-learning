# CPU_RESOURCE_ISSUE.md
# Giải thích vấn đề CPU Resource Contention

## 🔍 Vấn đề hiện tại

Mặc dù bạn đã set `num_cpus: 0.5` cho mỗi model replica, nhưng cluster vẫn hết 4/4 CPU. Tại sao?

### Phân tích chi tiết:

```
Mỗi application tạo ra 2 loại deployments:
1. LLMServer (model server)  -> 0.5 CPU (đã config)
2. LLMRouter (request router) -> 1 CPU × 2 replicas = 2 CPU (mặc định của Ray Serve)

App 1 (falcon3-1b):
  - LLMServer: 0.5 CPU
  - LLMRouter: 2 × 1 CPU = 2 CPU
  - Tổng: 2.5 CPU

App 2 (falcon-h1-0.5b):
  - LLMServer: 0.5 CPU
  - LLMRouter: 2 × 1 CPU = 2 CPU
  - Tổng: 2.5 CPU

TỔNG CỘNG: 5 CPU
Available: 4 CPU
❌ Thiếu: 1 CPU
```

### Log từ `ray status`:
```
Total Usage:
 4.0/4.0 CPU (2.0 used of 2.0 reserved in placement groups)
 0.8/1.0 GPU (0.8 used of 0.8 reserved in placement groups)

Total Demands:
 {'CPU': 1.0}: 2+ pending tasks/actors  # <- 2 LLMRouter replicas đang chờ CPU
```

## ✅ Giải pháp

### Option 1: Deploy 1 model duy nhất (KHUYẾN NGHỊ cho single-GPU node)

```bash
python3 app_v5.py single_model_optimized.yaml
```

**Lợi ích:**
- Đủ resources cho 1 model + LLMRouter
- Tối ưu hóa GPU utilization (0.9)
- Tăng throughput với batch size lớn hơn
- Không bị resource contention

**Resource allocation:**
```
LLMServer: 1 CPU + 0.9 GPU
LLMRouter: 2 CPU (2 replicas × 1 CPU)
Tổng: 3 CPU + 0.9 GPU
Còn dư: 1 CPU cho Ray system ✅
```

### Option 2: Deploy 2 models với resources giảm (Có thể gặp performance issues)

File hiện tại: `multi_model_config.yaml` đã được update với:
- `max_replicas: 1` (giảm từ 2-3)
- `router_config` thêm để giới hạn LLMRouter

**Lưu ý:** `router_config` có thể không được hỗ trợ bởi `build_openai_app`. 
Nếu vẫn gặp lỗi, LLMRouter sẽ vẫn sử dụng 2 replicas × 1 CPU.

### Option 3: Tăng số node hoặc CPU/GPU

```bash
# Thêm worker node
ray start --address='<head-node-ip>:6379' --num-cpus=4 --num-gpus=1

# Hoặc sử dụng cloud autoscaling
```

## 📝 Testing

### 1. Test với 1 model:
```bash
# Shutdown deployment hiện tại
serve shutdown -y

# Deploy 1 model
python3 app_v5.py single_model_optimized.yaml

# Kiểm tra status
serve status
ray status

# Test endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "falcon3-1b-instruct",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7
  }'
```

### 2. Test với 2 models (nếu muốn thử):
```bash
serve shutdown -y
python3 app_v5.py multi_model_config.yaml
```

**Dự đoán:** Vẫn sẽ gặp lỗi CPU contention do LLMRouter mặc định 2 replicas.

## 🎯 Khuyến nghị cuối cùng

Với single-GPU node (4 CPU, 1 GPU), **nên deploy 1 model duy nhất** để:
1. Tránh resource contention
2. Tối ưu hóa performance
3. Dễ dàng monitor và debug

Nếu cần deploy nhiều models:
- Scale horizontally: Thêm worker nodes
- Scale vertically: Upgrade node specs (more CPUs)
- Hoặc deploy models theo kiểu "on-demand" (load/unload theo request)

## 📚 References

- Ray Serve docs: https://docs.ray.io/en/latest/serve/
- Resource allocation: https://docs.ray.io/en/latest/ray-core/scheduling/resources.html
- Placement groups: https://docs.ray.io/en/latest/ray-core/scheduling/placement-group.html
