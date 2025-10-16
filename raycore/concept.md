# RAY

- [TASKS](#running-task)
- [ACTOR](#calling-actor)
## Concept
powerful distributed computing framework that provides a small set of essential primitives (tasks, actors, and objects) for building and scaling distributed applications

## Use Ray
```bash
pip install -U ray # Install ray (2.49)

ray.init() # Init Ray
```

## Running task
- Ray enables tasks to specify their resource requirements in terms of CPUs, GPUs, and custom resources
- The cluster scheduler uses these resource requests to distribute tasks across the cluster for parallelized execution.
- Ray enables arbitrary functions to be executed **asynchronously** on **separate** worker processes. Such functions are called **Ray remote functions** and their asynchronous invocations are called **Ray tasks**.
```bash
# simplest way to parallelize your Python functions across a Ray cluster

@ray.remote # decorate for it run remotely
.remote() # call function with instead of a normal function call
ray.get() # retrieve the result from the returned future (Ray object reference)

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
```

### Specifying required resources
```bash
# Specify required resources.
@ray.remote(num_cpus=4, num_gpus=2)
def my_function():
    return 1


# Override the default resource requirements.
my_function.options(num_cpus=3).remote()
```

### Passing object refs to Ray Tasks
```bash
@ray.remote
def function_with_an_argument(value):
    return value + 1


obj_ref1 = my_function.remote()
assert ray.get(obj_ref1) == 1

# You can pass an object ref as an argument to another Ray task.
obj_ref2 = function_with_an_argument.remote(obj_ref1)
assert ray.get(obj_ref2) == 2
```

### Waiting for partial results
- Calling **ray.get** on Ray task results will block until the task finished execution. After launching a number of tasks, you may want to know which ones have finished executing without blocking on all of them.
```bash
object_refs = [slow_function.remote() for _ in range(2)]
# Return as soon as one of the tasks finished execution.
ready_refs, remaining_refs = ray.wait(object_refs, num_returns=1, timeout=None)
```

### Multiple return
```bash
# By default, a Ray task only returns a single Object Ref.
@ray.remote
def return_single():
    return 0, 1, 2


object_ref = return_single.remote()
assert ray.get(object_ref) == (0, 1, 2)


# However, you can configure Ray tasks to return multiple Object Refs.
@ray.remote(num_returns=3)
def return_multiple():
    return 0, 1, 2


object_ref0, object_ref1, object_ref2 = return_multiple.remote()
assert ray.get(object_ref0) == 0
assert ray.get(object_ref1) == 1
assert ray.get(object_ref2) == 2


@ray.remote(num_returns=3)
def return_multiple_as_generator():
    for i in range(3):
        yield i


# NOTE: Similar to normal functions, these objects will not be available
# until the full task is complete and all returns have been generated.
a, b, c = return_multiple_as_generator.remote()
```

### Canceling tasks
```bash
@ray.remote
def blocking_operation():
    time.sleep(10e6)


obj_ref = blocking_operation.remote()
ray.cancel(obj_ref)

try:
    ray.get(obj_ref)
except ray.exceptions.TaskCancelledError:
    print("Object reference was cancelled.")
```

### Scheduling
- For each task, Ray will choose a node to run it and the scheduling decision is based on a few factors like the task’s resource requirements, the specified scheduling strategy and locations of task arguments.

### Fault Tolerance


### RAY API

- [RAY REMOTE API](https://docs.ray.io/en/latest/ray-core/api/doc/ray.remote.html#ray.remote)
- [RAY STATE API](https://docs.ray.io/en/latest/ray-observability/user-guides/cli-sdk.html#state-api-overview-ref)
- [RAY WAIT](https://docs.ray.io/en/latest/ray-core/api/doc/ray.wait.html#ray.wait)
- [RAY GENERATOR](https://docs.ray.io/en/latest/ray-core/ray-generator.html#generators)
- [RAY CANCEL](https://docs.ray.io/en/latest/ray-core/api/doc/ray.cancel.html#ray.cancel)
- [SCHEDULING](https://docs.ray.io/en/latest/ray-core/scheduling/index.html#ray-scheduling)
- [FAULT TOLERANCE](https://docs.ray.io/en/latest/ray-core/fault-tolerance.html#fault-tolerance)

## Calling Actor
While tasks are stateless, Ray actors allow you to create stateful workers that maintain their internal state between method calls. When you instantiate a Ray actor:
1. Ray starts a **dedicated worker process** somewhere in your cluster
2. The actor’s methods run on that **specific worker** and can access and modify its state
3. The actor executes method calls serially **in the order it receives** them, preserving consistency

```bash
# Define the Counter actor.
@ray.remote
class Counter:
    def __init__(self):
        self.i = 0

    def get(self):
        return self.i

    def incr(self, value):
        self.i += value

c = Counter.remote()

# Submit calls to the actor. These calls run asynchronously but in
# submission order on the remote actor process.
for _ in range(10):
    c.incr.remote(1)

# Retrieve final actor state.
print(ray.get(c.get.remote()))
```

## Object
- Tasks and actors create objects and compute on objects.
- You can refer to these objects as remote objects because Ray stores them anywhere in a Ray cluster, and you use object refs to refer to them. Ray caches remote objects in its distributed shared-memory object store and creates one object store per node in the cluster. In the cluster setting, a remote object can live on one or many nodes, independent of who holds the object ref.

## Passing Objects
Ray’s distributed object store efficiently manages data across your cluster. There are three main ways to work with objects in Ray:

1. **Implicit creation:** When tasks and actors return values, they are automatically stored in Ray’s distributed object store, returning object references that can be later retrieved.
2. **Explicit creation:** Use ray.put() to directly place objects in the store.
3. **Passing references:** You can pass object references to other tasks and actors, avoiding unnecessary data copying and enabling lazy execution.

## Placement Groups
- Placement groups allow users to atomically reserve groups of resources across multiple nodes. You can use them to schedule Ray tasks and actors packed as close as possible for locality (PACK), or spread apart (SPREAD). A common use case is gang-scheduling actors or tasks.
