# Tensor Parallelism vs Concurrency

## ⚠️ Quan trọng: Tensor Parallelism yêu cầu NHIỀU GPUs

### Tensor Parallelism là gì?

**Tensor Parallelism (TP)** là kỹ thuật chia nhỏ model weights ra nhiều GPUs để:
- Load models lớn hơn (vượt quá memory của 1 GPU)
- Tăng tốc inference bằng cách tính toán song song trên nhiều GPUs

### Yêu cầu resources cho Tensor Parallelism:

```yaml
tensor_parallel_size: 1  # Yêu cầu: 1 GPU
tensor_parallel_size: 2  # Yêu cầu: 2 GPUs
tensor_parallel_size: 4  # Yêu cầu: 4 GPUs
```

**CHÚ Ý:** vLLM với `tensor_parallel_size: 1` vẫn yêu cầu **2 GPUs** vì:
1. 1 GPU cho model
2. 1 GPU cho placement group (Ray internal)

### ❌ Lỗi khi dùng TP trên single GPU:

```
Error: No available node types can fulfill resource request 
{'CPU': 2.0, 'GPU': 2.0}
```

Lỗi này xuất hiện khi:
- Set `tensor_parallel_size: 1`
- Nhưng cluster chỉ có 1 GPU
- vLLM yêu cầu 2 GPUs → **không đủ resources**

---

## ✅ Concurrency KHÔNG cần nhiều GPUs

### Concurrency là gì?

**Concurrency** (đồng thời) là khả năng xử lý nhiều requests cùng lúc trên **CÙNG 1 replica**.

### Cách tăng concurrency trên single GPU:

```yaml
deployment_config:
  ray_actor_options:
    num_cpus: 2  # Tăng CPU để handle nhiều requests
    num_gpus: 0.95  # Vẫn chỉ dùng 1 GPU
  max_ongoing_requests: 256  # Cho phép 256 requests đồng thời

engine_kwargs:
  tensor_parallel_size: 0  # KHÔNG dùng TP
  max_num_seqs: 256  # Batch nhiều requests lại
  max_num_batched_tokens: 32768  # Tăng batch size
  enforce_eager: false  # Dùng CUDA graphs → faster
```

### Lợi ích:

✅ **Không cần thêm GPU**
✅ **Tăng throughput** (requests/second)
✅ **Giảm latency** nhờ batching
✅ **Tối ưu GPU utilization**

---

## 📊 So sánh

| Feature | Tensor Parallelism | Concurrency |
|---------|-------------------|-------------|
| **Yêu cầu GPUs** | 2+ GPUs | 1 GPU |
| **Mục đích** | Load large models | Handle nhiều requests |
| **Tăng throughput** | Có (nếu có nhiều GPUs) | Có (trên 1 GPU) |
| **Setup** | Phức tạp | Đơn giản |
| **Single GPU node** | ❌ Không dùng được | ✅ Dùng được |

---

## 🎯 Khuyến nghị cho single-GPU node

### Config tối ưu:

```yaml
applications:
  - name: "falcon3-1b-instruct-app"
    import_path: "ray.serve.llm:build_openai_app"
    route_prefix: "/v1"
    args:
      llm_configs:
        - model_loading_config:
            model_id: "falcon3-1b-instruct"
            model_source: "tiiuae/Falcon3-1B-Instruct"
          deployment_config:
            name: "falcon3-1b-deployment"
            ray_actor_options:
              num_cpus: 2  # Tăng CPU cho concurrency
              num_gpus: 0.95  # Single GPU
            autoscaling_config:
              min_replicas: 1
              max_replicas: 1  # Single replica trên 1 GPU
            max_ongoing_requests: 256  # High concurrency
          engine_kwargs:
            tensor_parallel_size: 0  # KHÔNG dùng TP
            dtype: "float16"
            gpu_memory_utilization: 0.90
            max_model_len: 8192
            enforce_eager: false  # CUDA graphs
            max_num_seqs: 256  # Batch size
            max_num_batched_tokens: 32768
            trust_remote_code: true
```

### Kết quả mong đợi:

- ✅ Deploy thành công trên 1 GPU
- ✅ Handle 256 concurrent requests
- ✅ High throughput nhờ batching
- ✅ Low latency nhờ CUDA graphs
- ✅ GPU utilization ~90%

---

## 🔧 Khi nào nên dùng Tensor Parallelism?

Chỉ dùng TP khi:

1. **Model quá lớn** (không fit vào 1 GPU)
   - Ví dụ: Llama 70B, Falcon 180B
2. **Có nhiều GPUs** (2+)
   - Ví dụ: 2× A100, 4× V100
3. **Cần extreme throughput**
   - Serving production với high traffic

Với **Falcon 1B-3B models** trên **single GPU**:
- ❌ KHÔNG cần TP
- ✅ Tăng concurrency thay vì

---

## 📝 Testing

### Test concurrency:

```bash
# Deploy với concurrency config
python3 app_v5.py single_model_optimized.yaml

# Test với nhiều requests đồng thời
for i in {1..10}; do
  curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "falcon3-1b-instruct",
      "messages": [{"role": "user", "content": "Hello '$i'"}],
      "temperature": 0.7
    }' &
done
wait

# Check throughput
echo "All 10 requests completed"
```

### Monitor GPU:

```bash
watch -n 1 nvidia-smi
```

Bạn sẽ thấy:
- GPU utilization ~90%
- Memory usage stable
- Multiple requests được batch lại

---

## 🚀 Tóm tắt

**Single GPU node:**
- ✅ Use `tensor_parallel_size: 0`
- ✅ Increase `max_ongoing_requests`
- ✅ Increase `max_num_seqs`
- ✅ Use `enforce_eager: false`
- ❌ DO NOT use `tensor_parallel_size: 1+`

**Multi-GPU node:**
- ✅ Use `tensor_parallel_size: <num_gpus>`
- ✅ Increase `num_gpus` in `ray_actor_options`
- ✅ Adjust `gpu_memory_utilization` accordingly

