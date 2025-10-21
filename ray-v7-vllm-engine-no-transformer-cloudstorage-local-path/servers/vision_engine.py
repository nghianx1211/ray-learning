from serve.deployments.multi_model_server import register_engine
from servers.base_engine import BaseEngine

@register_engine("VISION")
class VisionEngine(BaseEngine):
    async def start(self):
        from lavis.models import load_model_and_preprocess
        self.model, _, self.vis_processors = load_model_and_preprocess(
            "blip_caption", "base", device="cuda"
        )

    async def infer(self, request):
        img_path = request["image"]
        caption = self.model.generate({"image": img_path})
        yield {"caption": caption}

    async def check_health(self):
        if not hasattr(self, "model"):
            raise RuntimeError("Vision model not loaded.")
