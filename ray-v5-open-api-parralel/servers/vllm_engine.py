from serve.deployments.multi_model_server import register_engine
from servers.base_engine import BaseEngine
from vllm import SamplingParams
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
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
from typing import AsyncGenerator, Union
from vllm.utils import random_uuid

@register_engine("VLLM")
class VLLMEngine(BaseEngine):

    async def start(self):
        # Log current CUDA_VISIBLE_DEVICES
        cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', 'NOT SET')
        logging.info(f"VLLMEngine starting with CUDA_VISIBLE_DEVICES={cuda_devices}")
        
        # Fix tensor_parallel_size if it's 0
        kwargs = self.kwargs.copy()
        if kwargs.get('tensor_parallel_size', 1) == 0:
            kwargs.pop('tensor_parallel_size', None)
        
        # Create AsyncEngineArgs
        engine_args = AsyncEngineArgs(
            model=self.model_source,
            **kwargs
        )
        
        # Create AsyncLLMEngine
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        logging.info(f"VLLMEngine (Async) loaded: {self.model_id}")

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
        
        request_id = random_uuid()
        
        try:
            # Use AsyncLLMEngine.generate for streaming
            async for request_output in self.engine.generate(prompt, sampling_params, request_id):
                if request_output.finished:
                    generated_text = request_output.outputs[0].text
                    logging.info("infer: Final output: %s", generated_text)
                    yield {
                        "text": generated_text,
                        "model_id": self.model_id,
                        "finish_reason": request_output.outputs[0].finish_reason
                    }
        except Exception as e:
            logging.error("infer: Error during generation: %s", e)
            yield {"error": str(e)}

    async def chat_completions(self, request: ChatCompletionRequest) -> AsyncGenerator[Union[ChatCompletionResponse, ChatCompletionStreamResponse], None]:
        """OpenAI-compatible chat completions endpoint."""
        logging.info(f"chat_completions: Received request for model: {request.model}")
        
        # Convert chat messages to prompt
        prompt = self._messages_to_prompt(request.messages)
        
        # Create sampling params from request
        sampling_params = SamplingParams(
            max_tokens=request.max_tokens or 256,
            temperature=request.temperature or 0.7,
            top_p=request.top_p or 1.0,
            frequency_penalty=request.frequency_penalty or 0.0,
            presence_penalty=request.presence_penalty or 0.0,
            n=request.n or 1,
            stop=request.stop,
        )
        
        request_id = f"chatcmpl-{random_uuid()}"
        
        try:
            if request.stream:
                # True streaming response with AsyncLLMEngine
                previous_text = ""
                async for request_output in self.engine.generate(prompt, sampling_params, request_id):
                    current_text = request_output.outputs[0].text
                    delta_text = current_text[len(previous_text):]
                    previous_text = current_text
                    
                    if delta_text:
                        chunk = ChatCompletionStreamResponse(
                            id=request_id,
                            model=self.model_id,
                            choices=[{
                                "index": 0,
                                "delta": {
                                    "role": "assistant" if not previous_text or len(previous_text) == len(delta_text) else None,
                                    "content": delta_text,
                                },
                                "finish_reason": None,
                            }]
                        )
                        yield chunk
                    
                    # Final chunk with finish_reason
                    if request_output.finished:
                        final_chunk = ChatCompletionStreamResponse(
                            id=request_id,
                            model=self.model_id,
                            choices=[{
                                "index": 0,
                                "delta": {},
                                "finish_reason": request_output.outputs[0].finish_reason,
                            }]
                        )
                        yield final_chunk
            else:
                # Non-streaming response - collect all outputs
                final_output = None
                async for request_output in self.engine.generate(prompt, sampling_params, request_id):
                    if request_output.finished:
                        final_output = request_output
                        break
                
                if final_output:
                    response = ChatCompletionResponse(
                        id=request_id,
                        model=self.model_id,
                        choices=[{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": final_output.outputs[0].text,
                            },
                            "finish_reason": final_output.outputs[0].finish_reason,
                        }],
                        usage={
                            "prompt_tokens": len(final_output.prompt_token_ids),
                            "completion_tokens": len(final_output.outputs[0].token_ids),
                            "total_tokens": len(final_output.prompt_token_ids) + len(final_output.outputs[0].token_ids),
                        }
                    )
                    yield response
        except Exception as e:
            logging.error(f"chat_completions: Error during generation: {e}")
            yield {"error": str(e)}

    async def completions(self, request: CompletionRequest) -> AsyncGenerator[Union[CompletionResponse, CompletionStreamResponse], None]:
        """OpenAI-compatible completions endpoint."""
        logging.info(f"completions: Received request for model: {request.model}")
        
        # Create sampling params from request
        sampling_params = SamplingParams(
            max_tokens=request.max_tokens or 256,
            temperature=request.temperature or 0.7,
            top_p=request.top_p or 1.0,
            frequency_penalty=request.frequency_penalty or 0.0,
            presence_penalty=request.presence_penalty or 0.0,
            n=request.n or 1,
            stop=request.stop,
        )
        
        request_id = f"cmpl-{random_uuid()}"
        
        try:
            if request.stream:
                # True streaming response with AsyncLLMEngine
                previous_text = ""
                async for request_output in self.engine.generate(request.prompt, sampling_params, request_id):
                    current_text = request_output.outputs[0].text
                    delta_text = current_text[len(previous_text):]
                    previous_text = current_text
                    
                    if delta_text:
                        chunk = CompletionStreamResponse(
                            id=request_id,
                            model=self.model_id,
                            choices=[{
                                "index": 0,
                                "text": delta_text,
                                "finish_reason": None,
                                "logprobs": None,
                            }]
                        )
                        yield chunk
                    
                    # Final chunk with finish_reason
                    if request_output.finished:
                        final_chunk = CompletionStreamResponse(
                            id=request_id,
                            model=self.model_id,
                            choices=[{
                                "index": 0,
                                "text": "",
                                "finish_reason": request_output.outputs[0].finish_reason,
                                "logprobs": None,
                            }]
                        )
                        yield final_chunk
            else:
                # Non-streaming response - collect all outputs
                final_output = None
                async for request_output in self.engine.generate(request.prompt, sampling_params, request_id):
                    if request_output.finished:
                        final_output = request_output
                        break
                
                if final_output:
                    response = CompletionResponse(
                        id=request_id,
                        model=self.model_id,
                        choices=[{
                            "index": 0,
                            "text": final_output.outputs[0].text,
                            "finish_reason": final_output.outputs[0].finish_reason,
                            "logprobs": None,
                        }],
                        usage={
                            "prompt_tokens": len(final_output.prompt_token_ids),
                            "completion_tokens": len(final_output.outputs[0].token_ids),
                            "total_tokens": len(final_output.prompt_token_ids) + len(final_output.outputs[0].token_ids),
                        }
                    )
                    yield response
        except Exception as e:
            logging.error(f"completions: Error during generation: {e}")
            yield {"error": str(e)}

    def _messages_to_prompt(self, messages):
        """Convert OpenAI chat messages to a single prompt string."""
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
    
    async def check_health(self):
        if not hasattr(self, "engine"):
            raise RuntimeError("Engine not loaded.")
