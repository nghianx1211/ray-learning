from serve.deployments.multi_model_server import register_engine
from servers.base_engine import BaseEngine
from configs.open_api_models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    CompletionRequest,
    CompletionResponse,
    CompletionStreamResponse,
)
import os
import logging
import torch
from typing import AsyncGenerator, Union
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread
import uuid

@register_engine("TRANSFORMER")
class TransformerEngine(BaseEngine):
    """
    Engine for running models using HuggingFace Transformers.
    Supports models that VLLM doesn't support (e.g., BitNet quantization).
    """

    async def start(self):
        # Log current CUDA_VISIBLE_DEVICES
        cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', 'NOT SET')
        logging.info(f"TransformerEngine starting with CUDA_VISIBLE_DEVICES={cuda_devices}")
        
        # Get device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"Using device: {self.device}")
        
        # Load tokenizer
        logging.info(f"Loading tokenizer from {self.model_source}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_source,
            trust_remote_code=self.kwargs.get("trust_remote_code", True)
        )
        
        # Load model
        logging.info(f"Loading model from {self.model_source}")
        
        # Prepare model kwargs
        model_kwargs = {
            "trust_remote_code": self.kwargs.get("trust_remote_code", True),
            "torch_dtype": self._get_torch_dtype(self.kwargs.get("dtype", "auto")),
            "device_map": "auto" if self.device == "cuda" else None,
        }
        
        # Add low_cpu_mem_usage for large models
        if self.device == "cuda":
            model_kwargs["low_cpu_mem_usage"] = True
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_source,
            **model_kwargs
        )
        
        # Set model to eval mode
        self.model.eval()
        
        # Set pad token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        logging.info(f"TransformerEngine loaded: {self.model_id}")

    def _get_torch_dtype(self, dtype_str: str):
        """Convert dtype string to torch dtype"""
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
            "auto": "auto",
        }
        return dtype_map.get(dtype_str, "auto")

    async def infer(self, request):
        logging.info("infer: Received request: %s", request)
        prompt = request.get("prompt") or request.get("input")
        if not prompt:
            logging.warning("infer: Missing 'prompt' or 'input' in request")
            yield {"error": "Missing 'prompt' or 'input' in request"}
            return
        
        # Get params
        params = request.get("params", {})
        max_tokens = params.get("max_tokens", 256)
        temperature = params.get("temperature", 0.7)
        top_p = params.get("top_p", 1.0)
        top_k = params.get("top_k", 50)
        
        try:
            # Tokenize input
            inputs = self.tokenizer(prompt, return_tensors="pt", padding=True)
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Remove token_type_ids if present (not used by all models)
            inputs.pop("token_type_ids", None)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    do_sample=temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # Decode output
            generated_text = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            logging.info("infer: Final output: %s", generated_text)
            yield {
                "text": generated_text,
                "model_id": self.model_id,
                "finish_reason": "stop"
            }
        except Exception as e:
            logging.error("infer: Error during generation: %s", e)
            yield {"error": str(e)}

    def _apply_chat_template(self, messages):
        """Apply chat template to messages"""
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
            except Exception as e:
                logging.warning(f"Failed to apply chat template: {e}, falling back to simple format")
        
        # Fallback to simple format
        prompt = ""
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                prompt += f"System: {content}\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"
        prompt += "Assistant: "
        return prompt

    async def chat_completions(self, request: ChatCompletionRequest) -> AsyncGenerator[Union[ChatCompletionResponse, ChatCompletionStreamResponse], None]:
        """OpenAI-compatible chat completions endpoint."""
        logging.info(f"chat_completions: Received request for model: {request.model}")
        
        # Convert messages to prompt
        prompt = self._apply_chat_template(request.messages)
        
        # Generate request ID
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        
        try:
            if request.stream:
                # Streaming response
                inputs = self.tokenizer(prompt, return_tensors="pt", padding=True)
                if self.device == "cuda":
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Remove token_type_ids if present (not used by all models)
                inputs.pop("token_type_ids", None)
                
                # Create streamer
                streamer = TextIteratorStreamer(
                    self.tokenizer,
                    skip_prompt=True,
                    skip_special_tokens=True
                )
                
                # Generation kwargs
                generation_kwargs = {
                    **inputs,
                    "max_new_tokens": request.max_tokens or 256,
                    "temperature": request.temperature or 0.7,
                    "top_p": request.top_p or 1.0,
                    "do_sample": (request.temperature or 0.7) > 0,
                    "pad_token_id": self.tokenizer.pad_token_id,
                    "eos_token_id": self.tokenizer.eos_token_id,
                    "streamer": streamer,
                }
                
                if request.stop:
                    generation_kwargs["stop_strings"] = request.stop if isinstance(request.stop, list) else [request.stop]
                
                # Start generation in a separate thread
                thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
                thread.start()
                
                # Stream the output
                first_chunk = True
                for text in streamer:
                    if text:
                        chunk = ChatCompletionStreamResponse(
                            id=request_id,
                            model=self.model_id,
                            choices=[{
                                "index": 0,
                                "delta": {
                                    "role": "assistant" if first_chunk else None,
                                    "content": text,
                                },
                                "finish_reason": None,
                            }]
                        )
                        first_chunk = False
                        yield chunk
                
                # Wait for thread to finish
                thread.join()
                
                # Send final chunk
                final_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    model=self.model_id,
                    choices=[{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }]
                )
                yield final_chunk
                
            else:
                # Non-streaming response
                inputs = self.tokenizer(prompt, return_tensors="pt", padding=True)
                if self.device == "cuda":
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Remove token_type_ids if present
                inputs.pop("token_type_ids", None)
                
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=request.max_tokens or 256,
                        temperature=request.temperature or 0.7,
                        top_p=request.top_p or 1.0,
                        do_sample=(request.temperature or 0.7) > 0,
                        pad_token_id=self.tokenizer.pad_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                    )
                
                generated_text = self.tokenizer.decode(
                    outputs[0][inputs['input_ids'].shape[1]:],
                    skip_special_tokens=True
                )
                
                response = ChatCompletionResponse(
                    id=request_id,
                    model=self.model_id,
                    choices=[{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": generated_text,
                        },
                        "finish_reason": "stop",
                    }],
                    usage={
                        "prompt_tokens": inputs['input_ids'].shape[1],
                        "completion_tokens": outputs.shape[1] - inputs['input_ids'].shape[1],
                        "total_tokens": outputs.shape[1],
                    }
                )
                yield response
                
        except Exception as e:
            logging.error(f"chat_completions: Error during generation: {e}")
            yield {"error": str(e)}

    async def completions(self, request: CompletionRequest) -> AsyncGenerator[Union[CompletionResponse, CompletionStreamResponse], None]:
        """OpenAI-compatible completions endpoint."""
        logging.info(f"completions: Received request for model: {request.model}")
        
        request_id = f"cmpl-{uuid.uuid4().hex}"
        
        try:
            if request.stream:
                # Streaming response
                inputs = self.tokenizer(request.prompt, return_tensors="pt", padding=True)
                if self.device == "cuda":
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Remove token_type_ids if present
                inputs.pop("token_type_ids", None)
                
                streamer = TextIteratorStreamer(
                    self.tokenizer,
                    skip_prompt=True,
                    skip_special_tokens=True
                )
                
                generation_kwargs = {
                    **inputs,
                    "max_new_tokens": request.max_tokens or 256,
                    "temperature": request.temperature or 0.7,
                    "top_p": request.top_p or 1.0,
                    "do_sample": (request.temperature or 0.7) > 0,
                    "pad_token_id": self.tokenizer.pad_token_id,
                    "eos_token_id": self.tokenizer.eos_token_id,
                    "streamer": streamer,
                }
                
                thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
                thread.start()
                
                for text in streamer:
                    if text:
                        chunk = CompletionStreamResponse(
                            id=request_id,
                            model=self.model_id,
                            choices=[{
                                "index": 0,
                                "text": text,
                                "finish_reason": None,
                                "logprobs": None,
                            }]
                        )
                        yield chunk
                
                thread.join()
                
                final_chunk = CompletionStreamResponse(
                    id=request_id,
                    model=self.model_id,
                    choices=[{
                        "index": 0,
                        "text": "",
                        "finish_reason": "stop",
                        "logprobs": None,
                    }]
                )
                yield final_chunk
                
            else:
                # Non-streaming
                inputs = self.tokenizer(request.prompt, return_tensors="pt", padding=True)
                if self.device == "cuda":
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Remove token_type_ids if present
                inputs.pop("token_type_ids", None)
                
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=request.max_tokens or 256,
                        temperature=request.temperature or 0.7,
                        top_p=request.top_p or 1.0,
                        do_sample=(request.temperature or 0.7) > 0,
                        pad_token_id=self.tokenizer.pad_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                    )
                
                generated_text = self.tokenizer.decode(
                    outputs[0][inputs['input_ids'].shape[1]:],
                    skip_special_tokens=True
                )
                
                response = CompletionResponse(
                    id=request_id,
                    model=self.model_id,
                    choices=[{
                        "index": 0,
                        "text": generated_text,
                        "finish_reason": "stop",
                        "logprobs": None,
                    }],
                    usage={
                        "prompt_tokens": inputs['input_ids'].shape[1],
                        "completion_tokens": outputs.shape[1] - inputs['input_ids'].shape[1],
                        "total_tokens": outputs.shape[1],
                    }
                )
                yield response
                
        except Exception as e:
            logging.error(f"completions: Error during generation: {e}")
            yield {"error": str(e)}

    async def check_health(self):
        if not hasattr(self, "model") or self.model is None:
            raise RuntimeError("Model not loaded.")
        if not hasattr(self, "tokenizer") or self.tokenizer is None:
            raise RuntimeError("Tokenizer not loaded.")
