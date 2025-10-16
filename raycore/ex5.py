# By default, a Ray task only returns a single Object Ref.
import ray


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
print(ray.get(object_ref0), ray.get(object_ref1), ray.get(object_ref2))