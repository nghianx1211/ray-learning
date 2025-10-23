from serve.deployments.multi_model_server import register_engine
from servers.base_engine import BaseEngine
import torch
import whisper


@register_engine("AUDIO")
class AudioEngine(BaseEngine):
    async def start(self):
        self.model = whisper.load_model(self.model_id)

    async def infer(self, request):
        result = self.model.transcribe(request["audio_path"])
        yield {"text": result["text"]}

    async def check_health(self):
        if not hasattr(self, "model"):
            raise RuntimeError("Whisper model not loaded.")
