from ray import serve
import random, asyncio

RESPONSES = [
    "Hello! I'm your fake LLM 🤖",
    "I totally understood your question (trust me 😅).",
    "The answer is... 42.",
    "I'm only pretending to be smart, but it works!",
    "Yes! Scaling is working 🚀"
]

# Mỗi replica 1 CPU => ép scale ra nhiều worker pod khi vượt sức 1 pod
@serve.deployment(ray_actor_options={"num_cpus": 1})
class FakeLLM:
    async def __call__(self, request):
        data = await request.json()
        prompt = data.get("prompt", "")
        await asyncio.sleep(0.5)
        return {"response": f"Q: {prompt}\nA: {random.choice(RESPONSES)}"}

deployment_graph = FakeLLM.bind()