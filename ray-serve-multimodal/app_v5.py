"""
app_v5.py - Concurrent multi-model Ray Serve deployment

Improvements over app_v4.py:
1. Deploy multiple applications concurrently (parallel) instead of sequentially
2. Ensure per-replica resources: map num_cpus/num_gpus/cpus/gpus into ray_actor_options
   so each replica uses exactly the specified resources, not grabbing the full node

Usage:
    python3 app_v5.py multi_model_config.yaml
"""
import yaml
import ray
from ray import serve
from typing import Dict, Any, List
import concurrent.futures
import os
import time


def load_multi_model_config(yaml_path: str) -> List[Dict[str, Any]]:
    """Load multi-model config from YAML file"""
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("applications", [])


def _ensure_ray_actor_options(deployment_config: Dict[str, Any]) -> None:
    """
    Ensure deployment_config contains ray_actor_options with per-replica resources.
    
    This function maps common resource keys (num_cpus, cpus, num_gpus, gpus) into
    ray_actor_options so that Ray allocates resources per replica (actor) instead of
    trying to grab full node resources.
    
    Args:
        deployment_config: The deployment_config dict from YAML config
    """
    if deployment_config is None:
        return

    # If user already provided ray_actor_options, respect it
    if "ray_actor_options" in deployment_config and isinstance(
        deployment_config["ray_actor_options"], dict
    ):
        return

    ray_actor_options = {}

    # Map CPU keys (prefer num_cpus, fallback to cpus)
    for cpu_key in ("num_cpus", "cpus"):
        if cpu_key in deployment_config:
            try:
                ray_actor_options["num_cpus"] = float(deployment_config[cpu_key])
            except (ValueError, TypeError):
                # Keep original value if conversion fails
                ray_actor_options["num_cpus"] = deployment_config[cpu_key]
            break

    # Map GPU keys (prefer num_gpus, fallback to gpus)
    for gpu_key in ("num_gpus", "gpus"):
        if gpu_key in deployment_config:
            try:
                ray_actor_options["num_gpus"] = float(deployment_config[gpu_key])
            except (ValueError, TypeError):
                # Keep original value if conversion fails
                ray_actor_options["num_gpus"] = deployment_config[gpu_key]
            break

    # Only set ray_actor_options if we found some resources to map
    if ray_actor_options:
        deployment_config["ray_actor_options"] = ray_actor_options
        print(f"   📊 Mapped resources to ray_actor_options: {ray_actor_options}")


def deploy_model_app(app_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deploy one model application from config.
    
    This function is designed to be called concurrently from multiple threads.
    It returns a result dict indicating success/failure.
    
    Args:
        app_config: Single application config from YAML
        
    Returns:
        Dict with deployment result: {name, ok, details/error, route}
    """
    from ray.serve.llm import build_openai_app
    
    app_name = app_config["name"]
    route_prefix = app_config.get("route_prefix", "/")
    llm_configs = app_config["args"]["llm_configs"]

    # Filter allowed keys for validation
    def filter_keys(source_dict, allowed_keys):
        return {key: source_dict[key] for key in allowed_keys if key in source_dict}

    allowed_model_loading_keys = {"model_id", "model_source"}
    allowed_deployment_keys = {
        "name",
        "num_replicas",
        "max_concurrent_queries",
        "autoscaling_config",
        "min_replicas",
        "max_replicas",
        "target_ongoing_requests",
        "max_ongoing_requests",
        "cpus",
        "gpus",
        "num_cpus",
        "num_gpus",
        "ray_actor_options",
        # NOTE: Do NOT include placement_group_strategy or placement_group_bundles
        # Ray LLM will handle these automatically based on engine config
    }
    # Allow all engine_kwargs - don't filter too strictly
    # Just pass through what user provides
    allowed_engine_keys = None  # Will copy all engine_kwargs

    # Extract and filter configs
    raw_model_cfg = llm_configs[0]
    model_loading = filter_keys(
        raw_model_cfg.get("model_loading_config", {}), allowed_model_loading_keys
    )
    deployment_cfg = filter_keys(
        raw_model_cfg.get("deployment_config", {}), allowed_deployment_keys
    )
    # Don't filter engine_kwargs - pass all through
    engine_kwargs = raw_model_cfg.get("engine_kwargs", {})

    print(f"\n🚀 Deploying: {app_name}")
    print(f"   📦 Model ID: {model_loading.get('model_id', 'N/A')}")
    print(f"   🌐 Route: {route_prefix}")

    # Ensure per-replica resources are properly set
    _ensure_ray_actor_options(deployment_cfg)

    # Build llm_serving_args
    llm_serving_args = {
        "llm_configs": [
            {
                "model_loading_config": model_loading,
                "deployment_config": deployment_cfg,
                "engine_kwargs": engine_kwargs,
            }
        ]
    }

    try:
        # Build the application
        app = build_openai_app(llm_serving_args=llm_serving_args)

        # Deploy the application (Ray Serve handles concurrent registration)
        serve.run(app, name=app_name, route_prefix=route_prefix)

        print(f"   ✅ Deployed successfully: {app_name}")

        # Return success result
        return {
            "name": app_name,
            "ok": True,
            "route": route_prefix,
            "model_id": model_loading.get("model_id", "N/A"),
            "model_source": model_loading.get("model_source", "N/A"),
            "deployment_config": deployment_cfg,
        }

    except Exception as e:
        print(f"   ❌ Error deploying {app_name}: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "name": app_name,
            "ok": False,
            "error": str(e),
        }


def main(yaml_config_path: str):
    """Main function to deploy all models from YAML config concurrently"""
    
    print("🔧 Initializing Ray and Ray Serve...")
    ray.init(ignore_reinit_error=True)
    serve.start(detached=True)

    print(f"\n📖 Loading config from: {yaml_config_path}")
    apps_config = load_multi_model_config(yaml_config_path)

    if not apps_config:
        print("❌ No applications found in config file!")
        return

    print(f"📦 Found {len(apps_config)} application(s) to deploy")
    print("🔄 Starting concurrent deployment...\n")

    # Deploy all applications concurrently using ThreadPoolExecutor
    # Use bounded worker count to avoid excessive threads
    max_workers = min(len(apps_config), max(2, os.cpu_count() or 2))
    deployed_apps = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all deployment tasks
        future_to_config = {
            executor.submit(deploy_model_app, cfg): cfg for cfg in apps_config
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_config):
            result = future.result()
            deployed_apps.append(result)

    # Print deployment summary
    print("\n" + "=" * 80)
    print("✅ Deployment Summary")
    print("=" * 80)

    succeeded = [app for app in deployed_apps if app.get("ok")]
    failed = [app for app in deployed_apps if not app.get("ok")]

    print(f"Total applications deployed: {len(succeeded)}/{len(apps_config)}")

    if succeeded:
        print("\n📋 Successfully Deployed Applications:")
        print("-" * 80)
        for app in succeeded:
            dep_cfg = app.get("deployment_config", {})
            ray_actor_opts = dep_cfg.get("ray_actor_options", {})
            
            # Get resources (prefer from ray_actor_options)
            cpus = ray_actor_opts.get("num_cpus") or dep_cfg.get("num_cpus") or dep_cfg.get("cpus", "N/A")
            gpus = ray_actor_opts.get("num_gpus") or dep_cfg.get("num_gpus") or dep_cfg.get("gpus", "N/A")
            
            autoscaling = dep_cfg.get("autoscaling_config", {})
            min_replicas = autoscaling.get("min_replicas", dep_cfg.get("min_replicas", 1))
            max_replicas = autoscaling.get("max_replicas", dep_cfg.get("max_replicas", 1))
            
            print(f"\n• {app['name']}")
            print(f"   Model: {app.get('model_source', 'N/A')}")
            print(f"   Model ID: {app.get('model_id', 'N/A')}")
            print(f"   Resources per replica: {cpus} CPUs, {gpus} GPUs")
            print(f"   Replicas: {min_replicas} → {max_replicas} (autoscaling)")
            print(f"   Base URL: http://localhost:8000{app['route']}")
            print(f"   Endpoints:")
            print(f"     • POST {app['route']}/v1/chat/completions")
            print(f"     • POST {app['route']}/v1/completions")
            print(f"     • GET  {app['route']}/v1/models")

    if failed:
        print("\n⚠️  Failed Deployments:")
        print("-" * 80)
        for app in failed:
            print(f"   ❌ {app['name']}: {app.get('error', 'Unknown error')}")

    print("\n" + "=" * 80)
    print("🔥 All deployments completed!")
    print("💡 Ray Dashboard: http://localhost:8265")
    print("💡 Check deployment status and resource usage in the dashboard")
    print("=" * 80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 app_v5.py <path_to_yaml_config>")
        print("Example: python3 app_v5.py multi_model_config.yaml")
        sys.exit(1)

    yaml_config_path = sys.argv[1]

    try:
        main(yaml_config_path)

        print("\n⏸️  Keeping service running... Press Ctrl+C to shutdown")
        
        # Keep the process running to serve requests
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down Ray Serve...")
        serve.shutdown()
        print("✓ Shutdown complete!")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
