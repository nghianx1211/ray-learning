import ray
from ray import serve
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from ray.llm._internal.serve.configs.openai_api_models import (
    ChatCompletionRequest, CompletionRequest, EmbeddingRequest, EmbeddingResponse
)
from ray.llm._internal.serve.configs.server_models import LLMConfig
from ray.llm._internal.serve.deployments.llm.llm_server import LLMDeployment

app = FastAPI()

@serve.deployment(name="FastAPIWrapper")
@serve.ingress(app)
class FastAPIWrapper:
    @app.post("/v1/chat/completions")
    async def chat_endpoint(self, request: ChatCompletionRequest):
        handle = serve.get_deployment_handle("LLMDeployment", app_name="default")
        stream_mode = getattr(request, "stream", False)
        response_stream = handle.options(stream=True).chat.remote(request)
        if stream_mode:
            async def event_stream():
                async for chunk in response_stream:
                    yield str(chunk)
            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
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
            if hasattr(last_json, "dict"):
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
    async def completions_endpoint(self, request: CompletionRequest):
        handle = serve.get_deployment_handle("LLMDeployment", app_name="default")
        stream_mode = getattr(request, "stream", False)
        response_stream = handle.options(stream=True).completions.remote(request)
        if stream_mode:
            async def event_stream():
                async for chunk in response_stream:
                    yield str(chunk)
            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
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

    @app.post("/v1/embeddings", response_model=EmbeddingResponse)
    async def embeddings_endpoint(self, request: EmbeddingRequest):
        handle = serve.get_deployment_handle("LLMDeployment", app_name="default")
        response_stream = handle.options(stream=True).embeddings.remote(request)
        results = []
        async for chunk in response_stream:
            results.append(chunk)
        return results[-1] if results else {}

if __name__ == "__main__":
    import asyncio
    ray.init()
    serve.start()
    llm_config = LLMConfig(
        model_loading_config={"model_id": "tiiuae/falcon3-1b-instruct"},
        deployment_config={"num_replicas": 1},
    )
    # Deploy LLMDeployment trước
    llm_deployment_handle = LLMDeployment.options(name="LLMDeployment").bind(llm_config)
    serve.run(llm_deployment_handle, name="default", route_prefix="/llm")
    
    # Đợi một chút để LLMDeployment khởi tạo xong
    import time
    time.sleep(5)
    
    # Deploy FastAPIWrapper sau
    serve.run(FastAPIWrapper.bind(), name="api", route_prefix="/")