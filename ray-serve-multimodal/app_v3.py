"""
app_v3.py - Serve LLM model sử dụng ray.llm chính thức từ Ray
Sử dụng các module và class có sẵn trong Ray 2.49.0
"""
import yaml
import ray
from ray import serve
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, List, Optional

# Import các class từ ray.llm (có sẵn trong Ray 2.49.0)
from ray.llm._internal.serve.configs.openai_api_models import (
    ChatCompletionRequest, 
    CompletionRequest
)
from ray.llm._internal.serve.configs.server_models import LLMConfig
from ray.llm._internal.serve.deployments.llm.llm_server import LLMDeployment

# Load config từ YAML và chuyển thành LLMConfig
def load_config(yaml_path: str) -> LLMConfig:
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    # Lấy config của model đầu tiên
    model_config = config['llm_configs'][0]
    
    # Tạo LLMConfig object từ YAML config
    llm_config = LLMConfig(
        model_loading_config=model_config['model_loading_config'],
        deployment_config=model_config.get('deployment_config', {}),
        engine_kwargs=model_config.get('engine_kwargs', {})
    )
    return llm_config

# FastAPI app
app = FastAPI()

@serve.deployment(name="FastAPIWrapper")
@serve.ingress(app)
class FastAPIWrapper:
    def __init__(self, llm_handle):
        self.llm_handle = llm_handle
    
    @app.post("/v1/chat/completions")
    async def chat_completions(self, request: ChatCompletionRequest):
        # Sử dụng LLMDeployment để xử lý chat completion
        stream_mode = getattr(request, "stream", False)
        response_stream = self.llm_handle.options(stream=True).chat.remote(request)
        
        if stream_mode:
            async def event_stream():
                async for chunk in response_stream:
                    yield str(chunk)
            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
            # Collect all chunks
            last_json = None
            async for chunk in response_stream:
                if isinstance(chunk, str) and chunk.startswith("data:"):
                    try:
                        json_str = chunk.split("data:")[1].strip()
                        if json_str != "[DONE]":
                            last_json = json_str
                    except Exception:
                        pass
                else:
                    last_json = chunk
            
            # Return final result
            if hasattr(last_json, "model_dump"):
                return JSONResponse(content=last_json.model_dump())
            elif hasattr(last_json, "dict"):
                return JSONResponse(content=last_json.dict())
            elif isinstance(last_json, str):
                import json
                try:
                    return JSONResponse(content=json.loads(last_json))
                except Exception:
                    return JSONResponse(content={"result": last_json})
            else:
                return JSONResponse(content=last_json if last_json else {})
    
    @app.post("/v1/completions")
    async def completions(self, request: CompletionRequest):
        # Sử dụng LLMDeployment để xử lý completion
        stream_mode = getattr(request, "stream", False)
        response_stream = self.llm_handle.options(stream=True).completions.remote(request)
        
        if stream_mode:
            async def event_stream():
                async for chunk in response_stream:
                    yield str(chunk)
            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
            # Collect all chunks
            last_json = None
            async for chunk in response_stream:
                if isinstance(chunk, str) and chunk.startswith("data:"):
                    try:
                        json_str = chunk.split("data:")[1].strip()
                        if json_str != "[DONE]":
                            last_json = json_str
                    except Exception:
                        pass
                else:
                    last_json = chunk
            
            # Return final result
            if hasattr(last_json, "model_dump"):
                return JSONResponse(content=last_json.model_dump())
            elif hasattr(last_json, "dict"):
                return JSONResponse(content=last_json.dict())
            elif isinstance(last_json, str):
                import json
                try:
                    return JSONResponse(content=json.loads(last_json))
                except Exception:
                    return JSONResponse(content={"result": last_json})
            else:
                return JSONResponse(content=last_json if last_json else {})
    
    @app.get("/v1/models")
    async def list_models(self):
        return JSONResponse(content={
            "object": "list",
            "data": [{
                "id": "tiiuae/falcon3-1b-instruct",
                "object": "model",
                "created": 1677652288,
                "owned_by": "tiiuae"
            }]
        })

if __name__ == "__main__":
    import sys
    import time
    
    if len(sys.argv) < 2:
        print("Usage: python app_v3.py <path_to_yaml_config>")
        print("Example: python app_v3.py model_config.yaml")
        sys.exit(1)
    
    yaml_config_path = sys.argv[1]
    
    # Khởi tạo Ray
    ray.init()
    serve.start()
    
    # Load config từ YAML
    print(f"Loading config from: {yaml_config_path}")
    llm_config = load_config(yaml_config_path)
    
    # Bind LLMDeployment (không run riêng)
    model_id = llm_config.model_loading_config.model_id
    print(f"Deploying application with model: {model_id}")
    llm_deployment = LLMDeployment.options(name="LLMDeployment").bind(llm_config)
    
    # Deploy FastAPI wrapper với LLMDeployment được bind vào
    # Chỉ run 1 lần duy nhất, FastAPIWrapper sẽ tự động deploy LLMDeployment
    app_deployment = FastAPIWrapper.bind(llm_deployment)
    serve.run(app_deployment, name="default", route_prefix="/")
    
    print(f"\n✓ Application deployed successfully!")
    print(f"  - Model: {model_id}")
    print(f"  - OpenAI API endpoints available at: http://localhost:8000")
    print(f"  - POST /v1/chat/completions")
    print(f"  - POST /v1/completions")
    print(f"  - GET /v1/models")
    print(f"\nKeep this running to serve requests...")
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        serve.shutdown()
        ray.shutdown()
