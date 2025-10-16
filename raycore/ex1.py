import ray

ray.init()

########## Example ##################
# Define the square task.
@ray.remote
def square(x):
    return x * x

# Launch four parallel square tasks.
futures = [square.remote(i) for i in range(4)]

# Retrieve results.
print(ray.get(futures))
# -> [0, 1, 4, 9]

# python3 ./ex1.py
# 2025-10-16 11:14:57,425 INFO worker.py:2013 -- Started a local Ray instance.
# /home/ubuntu/ray-learning/venv/lib/python3.12/site-packages/ray/_private/worker.py:2052: FutureWarning: Tip: In future versions of Ray, Ray will no longer override accelerator visible devices env var if num_gpus=0 or num_gpus=None (default). To enable this behavior and turn off this error message, set RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO=0
#   warnings.warn(
# [0, 1, 4, 9]