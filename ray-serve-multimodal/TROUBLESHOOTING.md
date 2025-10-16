# Troubleshooting: Slow Deployment Initialization

## Vấn đề hiện tại

Deployment mất **hơn 13 phút** vẫn không khởi tạo thành công, liên tục báo warning:
```
Deployment 'LLMServer:falcon3-1b-deployment' has 1 replicas that have taken more than 30s to initialize.
This may be caused by a slow __init__ or reconfigure method.
```

## Phân tích

### 1. Resources KHÔNG phải là vấn đề:
```
Total Usage:
 3.0/8.0 CPU (1.0 used of 1.0 reserved in placement groups)
 0.8/1.0 GPU (0.8 used of 0.8 reserved in placement groups)
```
- Cluster còn 5 CPU và 0.2 GPU trống
- Deployment chỉ cần 1 CPU + 0.8 GPU → đủ resources

### 2. Model đã được cache:
```
~/.cache/huggingface/hub/models--tiiuae--Falcon3-1B-Instruct
~/.cache/huggingface/hub/models--tiiuae--falcon3-1b-instruct
```
- Model đã được download trước đó
- Không phải vấn đề network/download

### 3. vLLM initialization đang bị block:
- Log cuối cùng: "Downloading the tokenizer"
- Sau đó không có log nào khác
- vLLM engine có thể đang:
  - Load model weights vào GPU
  - Initialize CUDA kernels
  - Build KV cache
  - Hoặc bị stuck ở một bước nào đó

## Các nguyên nhân có thể

### A. CUDA/GPU Issues
- CUDA out of memory
- GPU compatibility issues
- CUDA drivers/toolkit version mismatch

### B. vLLM Configuration Issues
- `gpu_memory_utilization` quá cao (0.8)
- `max_model_len` quá lớn (8192)
- `enforce_eager=true` có thể gây chậm

### C. Model Issues
- Model format không tương thích với vLLM
- Tokenizer issues
- Model config thiếu hoặc sai

### D. Ray Serve Issues
- Placement groups đang block resources
- Ray actors không thể communicate
- Deadlock trong initialization sequence

## Giải pháp đề xuất

### Solution 1: Giảm GPU memory và model length
```yaml
engine_kwargs:
  dtype: "float16"
  gpu_memory_utilization: 0.5  # Giảm từ 0.8 xuống 0.5
  max_model_len: 2048          # Giảm từ 8192 xuống 2048
  enforce_eager: false         # Cho phép CUDA graphs
  max_num_seqs: 32
  max_num_batched_tokens: 4096
  trust_remote_code: true
```

### Solution 2: Check vLLM logs trực tiếp
```bash
# Find the replica actor PID
ps aux | grep "falcon3-1b-deployment"

# Check Ray logs
tail -f /tmp/ray/session_latest/logs/serve/*.log

# hoặc check từ Ray dashboard
# http://localhost:8265
```

### Solution 3: Test vLLM directly (không qua Ray Serve)
```python
from vllm import LLM

llm = LLM(
    model="tiiuae/Falcon3-1B-Instruct",
    dtype="float16",
    gpu_memory_utilization=0.5,
    max_model_len=2048,
    enforce_eager=True,
    trust_remote_code=True,
)

output = llm.generate("Hello, my name is", max_tokens=20)
print(output)
```

Nếu test này fail → vấn đề ở vLLM setup, không phải Ray Serve.

### Solution 4: Check GPU status
```bash
# Check GPU memory
nvidia-smi

# Check CUDA version
nvcc --version

# Check vLLM can access GPU
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.device_count())"
```

### Solution 5: Restart Ray cluster hoàn toàn
```bash
# Stop everything
serve shutdown -y
ray stop

# Clear Ray temp files
rm -rf /tmp/ray/*

# Restart Ray
ray start --head \
  --num-cpus=8 \
  --num-gpus=1 \
  --object-store-memory=4000000000

# Deploy lại
python3 app_v5.py single_model_optimized.yaml
```

### Solution 6: Try a simpler model first
Thử deploy model nhỏ hơn để xác nhận setup hoạt động:
```yaml
model_source: "facebook/opt-125m"  # Model rất nhỏ, khởi tạo nhanh
```

## Next Steps

1. **Ưu tiên cao**: Check vLLM logs để xem stuck ở đâu
2. **Test vLLM directly**: Xác nhận vLLM hoạt động độc lập
3. **Check GPU**: Đảm bảo GPU không bị OOM
4. **Giảm config**: Giảm `gpu_memory_utilization` và `max_model_len`
5. **Restart Ray**: Clean slate deployment

## Commands to run

```bash
# 1. Check Ray logs
ls -lht /tmp/ray/session_latest/logs/serve/ | head -10
tail -100 /tmp/ray/session_latest/logs/serve/serve_controller.log

# 2. Check GPU
nvidia-smi

# 3. Test vLLM directly
python3 -c "from vllm import LLM; llm = LLM('tiiuae/Falcon3-1B-Instruct', dtype='float16', gpu_memory_utilization=0.5, max_model_len=2048); print('Success!')"

# 4. Restart deployment với config giảm
serve shutdown -y
# Edit config to reduce gpu_memory_utilization and max_model_len
python3 app_v5.py single_model_optimized.yaml
```
