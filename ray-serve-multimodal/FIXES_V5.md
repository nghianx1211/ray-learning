# 🐛 Fixes Applied to app_v5.py and Config

## Issues Found

### 1. ❌ placement_group_strategy Error
**Error Message:**
```
ValueError: placement_group_bundles and placement_group_strategy must not be specified in deployment_config. 
Use scaling_config to configure replica placement group.
```

**Root Cause:**
- Config had `placement_group_strategy: "STRICT_PACK"` in `deployment_config`
- Ray LLM automatically manages placement groups based on `engine_kwargs`
- User shouldn't specify these directly

**Fix Applied:**
- ✅ Removed `placement_group_strategy` from `multi_model_config.yaml`
- ✅ Updated `app_v5.py` to not include these keys in `allowed_deployment_keys`
- ✅ Added comment explaining Ray handles this automatically

### 2. ❌ Insufficient GPU Resources Error
**Error Message:**
```
Error: No available node types can fulfill resource request {'CPU': 1.0, 'GPU': 1.45}
Resources required for each replica: [{"CPU": 1.0, "GPU": 0.45}, {"GPU": 1.0}]
```

**Root Cause:**
- Node has only **1 GPU** total
- Config requested: `num_gpus: 0.45` (actor) + `tensor_parallel_size: 1` (engine) = **1.45 GPUs**
- `tensor_parallel_size: 1` creates additional placement bundle requiring 1 GPU

**Why This Happens:**
```python
# Ray creates bundles like this:
bundles = [
    {"CPU": 1.0, "GPU": 0.45},  # For actor (from ray_actor_options)
    {"GPU": 1.0}                # For tensor parallel (from tensor_parallel_size)
]
# Total: 1.45 GPU required!
```

**Fix Applied:**
- ✅ Removed `tensor_parallel_size: 1` from `engine_kwargs` in both models
- ✅ Now only requires 0.45 GPU per replica (fits in 1 GPU node)
- ✅ Updated `app_v5.py` to pass all `engine_kwargs` without filtering

## Updated Files

### 1. `multi_model_config.yaml`
**Changes:**
```yaml
# BEFORE (WRONG):
deployment_config:
  placement_group_strategy: "STRICT_PACK"  # ❌ Not allowed
  ray_actor_options:
    num_gpus: 0.45
engine_kwargs:
  tensor_parallel_size: 1  # ❌ Requires extra GPU

# AFTER (CORRECT):
deployment_config:
  # placement_group_strategy removed - Ray handles automatically
  ray_actor_options:
    num_gpus: 0.45
engine_kwargs:
  # tensor_parallel_size: 1 commented out
```

### 2. `app_v5.py`
**Changes:**
```python
# BEFORE:
allowed_deployment_keys = {
    "placement_group_strategy",  # ❌ Not allowed by Ray
    "placement_group_bundles",   # ❌ Not allowed by Ray
    ...
}

# AFTER:
allowed_deployment_keys = {
    # placement_group_* removed with comment
    # Ray LLM handles these automatically
    ...
}

# BEFORE:
allowed_engine_keys = {...}  # Limited set
engine_kwargs = filter_keys(raw_model_cfg.get("engine_kwargs", {}), allowed_engine_keys)

# AFTER:
allowed_engine_keys = None  # Don't filter
engine_kwargs = raw_model_cfg.get("engine_kwargs", {})  # Pass all through
```

## Resource Calculation Explained

### With Node: 1 GPU, 4 CPUs

**Scenario 1: tensor_parallel_size = 1 (WRONG)**
```
Model 1 requires:
  - Actor bundle: {"CPU": 1.0, "GPU": 0.45}
  - TP bundle:    {"GPU": 1.0}
  Total: 1.45 GPU ❌ FAIL (only have 1 GPU)
```

**Scenario 2: No tensor_parallel_size (CORRECT)**
```
Model 1 requires:
  - Actor bundle: {"CPU": 1.0, "GPU": 0.45}
  Total: 0.45 GPU ✅ SUCCESS

Can run 2 replicas on 1 GPU:
  - Replica 1: 0.45 GPU
  - Replica 2: 0.45 GPU
  Total: 0.9 GPU ✅ Fits!
```

## Testing the Fix

### 1. Check current resources:
```bash
ray status
```

Expected output:
```
Resources
---------------------------------------------------------------
Total Usage:
 X/4.0 CPU
 0.0/1.0 GPU  # ← Should have available GPU
```

### 2. Run app_v5.py:
```bash
python3 app_v5.py multi_model_config.yaml
```

Expected output:
```
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
```

### 3. Verify in Ray Dashboard:
- Go to http://localhost:8265
- Tab **Serve** → Check both apps are RUNNING
- Tab **Cluster** → Check GPU usage ~0.9 (2 replicas × 0.45)

## When to Use tensor_parallel_size

### Use tensor_parallel_size when:
✅ You have **multiple GPUs** per node (2+)
✅ Model is **very large** (70B+ parameters)
✅ Need to **split model** across GPUs

### Example for 2 GPU node:
```yaml
deployment_config:
  ray_actor_options:
    num_gpus: 2  # Reserve both GPUs
engine_kwargs:
  tensor_parallel_size: 2  # Split model across 2 GPUs
```

### Don't use tensor_parallel_size when:
❌ Single GPU node (like current setup)
❌ Small models (< 7B parameters)
❌ Want to run multiple replicas on same GPU

## Summary

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| placement_group error | User specified in deployment_config | Removed from config |
| GPU resource error | tensor_parallel_size requires extra GPU | Removed tensor_parallel_size |
| Filtering too strict | Lost important engine_kwargs | Pass all engine_kwargs through |

**Result:** ✅ Both models can now deploy on 1 GPU node with 0.45 GPU each!
