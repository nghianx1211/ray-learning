import ray
import time

ray.init()

# A regular Python function.
def normal_function():
    return 1


# By adding the `@ray.remote` decorator, a regular Python function
# becomes a Ray remote function.
@ray.remote
def my_function():
    return 1


# To invoke this remote function, use the `remote` method.
# This will immediately return an object ref (a future) and then create
# a task that will be executed on a worker process.
obj_ref = my_function.remote()

# The result can be retrieved with ``ray.get``.
print(ray.get(obj_ref))


@ray.remote
def slow_function():
    time.sleep(10)
    return 1


# Ray tasks are executed in parallel.
# All computation is performed in the background, driven by Ray's internal event loop.
for _ in range(4):
    # This doesn't block.
    slow_function.remote()

@ray.remote
def function_with_an_argument(value):
    return value + 1


obj_ref1 = my_function.remote()
print(ray.get(obj_ref1))

# You can pass an object ref as an argument to another Ray task.
obj_ref2 = function_with_an_argument.remote(obj_ref1)
print(ray.get(obj_ref2))


# As the second task depends on the output of the first task, Ray will not execute the second task until the first task has finished.
# If the two tasks are scheduled on different machines, the output of the first task (the value corresponding to obj_ref1/objRef1) will be sent over the network to the machine where the second task is scheduled.