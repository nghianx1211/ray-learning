#!/usr/bin/env python3
"""
test_vllm_direct.py - Test vLLM directly without Ray Serve
"""

print("Testing vLLM initialization...")
print("=" * 80)

try:
    print("\n1. Importing vLLM...")
    from vllm import LLM
    print("   ✓ vLLM imported successfully")
    
    print("\n2. Checking CUDA...")
    import torch
    print(f"   CUDA available: {torch.cuda.is_available()}")
    print(f"   CUDA devices: {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"   CUDA device 0: {torch.cuda.get_device_name(0)}")
        print(f"   CUDA version: {torch.version.cuda}")
    
    print("\n3. Initializing vLLM with Falcon3-1B-Instruct...")
    print("   This may take a few minutes...")
    
    llm = LLM(
        model="tiiuae/Falcon3-1B-Instruct",
        dtype="float16",
        gpu_memory_utilization=0.5,  # Conservative
        max_model_len=2048,          # Small
        enforce_eager=True,
        trust_remote_code=True,
    )
    
    print("   ✓ vLLM initialized successfully!")
    
    print("\n4. Testing inference...")
    outputs = llm.generate(
        ["Hello, my name is"],
        max_tokens=20,
        temperature=0.7,
    )
    
    print("   ✓ Inference successful!")
    print(f"   Output: {outputs[0].outputs[0].text}")
    
    print("\n" + "=" * 80)
    print("✅ All tests passed! vLLM is working correctly.")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 80)
    print("⚠️  vLLM test failed! Check the error above.")
    print("=" * 80)
