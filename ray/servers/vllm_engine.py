from serve.deployments.multi_model_server import register_engine
from servers.base_engine import BaseEngine
from vllm import LLM, SamplingParams
import asyncio
import os
import logging

@register_engine("VLLM")
class VLLMEngine(BaseEngine):
    async def start(self):
        # Log current CUDA_VISIBLE_DEVICES
        cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', 'NOT SET')
        logging.info(f"🎮 VLLMEngine starting with CUDA_VISIBLE_DEVICES={cuda_devices}")
        
        # Fix tensor_parallel_size if it's 0
        kwargs = self.kwargs.copy()
        if kwargs.get('tensor_parallel_size', 1) == 0:
            kwargs.pop('tensor_parallel_size', None)
        
        loop = asyncio.get_event_loop()
        self.model = await loop.run_in_executor(None, lambda: LLM(self.model_source, **kwargs))
        logging.info(f"✅ VLLMEngine loaded: {self.model_id}")

    async def infer(self, request):
        logging.info("infer: Received request: %s", request)
        prompt = request.get("prompt") or request.get("input")
        if not prompt:
            logging.warning("infer: Missing 'prompt' or 'input' in request")
            yield {"error": "Missing 'prompt' or 'input' in request"}
            return
        
        # Get params and create SamplingParams object for VLLM
        params = request.get("params", {})
        
        # Extract VLLM-compatible sampling parameters
        sampling_params = SamplingParams(
            max_tokens=params.get("max_tokens", 256),
            temperature=params.get("temperature", 0.7),
            top_p=params.get("top_p", 1.0),
            top_k=params.get("top_k", -1),
            frequency_penalty=params.get("frequency_penalty", 0.0),
            presence_penalty=params.get("presence_penalty", 0.0),
        )
        
        logging.info("infer: Using sampling_params: %s", sampling_params)
        
        # Run the blocking generate call in a thread pool
        loop = asyncio.get_event_loop()
        logging.info("infer: Calling self.model.generate with prompt: %s", prompt)
        
        try:
            outputs = await loop.run_in_executor(
                None, 
                lambda: self.model.generate(prompt, sampling_params=sampling_params)
            )
            logging.info("infer: self.model.generate returned %d outputs", len(outputs))
            
            # VLLM returns a list of RequestOutput objects
            for idx, output in enumerate(outputs):
                generated_text = output.outputs[0].text
                logging.info("infer: Output %d: %s", idx, generated_text)
                yield {
                    "text": generated_text,
                    "model_id": self.model_id,
                    "finish_reason": output.outputs[0].finish_reason
                }
        except Exception as e:
            logging.error("infer: Error during generation: %s", e)
            yield {"error": str(e)}
    
    async def check_health(self):
        if not hasattr(self, "model"):
            raise RuntimeError("Model not loaded.")
