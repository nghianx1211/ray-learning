"""
app_v6.py - Basic Ray Serve deployment without LLM Config, LLM Deployment, or OpenAPI

This script demonstrates a simplified Ray Serve deployment that does not rely on
advanced features like LLM Config, LLM Deployment, or OpenAPI. It uses basic Ray Serve
functionalities to deploy multiple models defined in a YAML configuration file.

Usage:
    python3 app_v6.py multi_model_config.yaml
"""
import yaml
import ray
from ray import serve
from typing import Dict, Any, List
import os
import time

def load_multi_model_config(yaml_path: str) -> List[Dict[str, Any]]:
    """Load multi-model config from YAML file"""
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("applications", [])

class BasicModel:
    def __init__(self, model_id: str):
        self.model_id = model_id

    def __call__(self, request):
        return {"response": f"Hello from model {self.model_id}!"}

def deploy_model_app(app_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deploy one model application from config.
    
    Args:
        app_config: Single application config from YAML
        
    Returns:
        Dict with deployment result: {name, ok, details/error, route}
    """
    app_name = app_config["name"]
    route_prefix = app_config.get("route_prefix", "/")
    model_id = app_config.get("model_id", "default_model")

    print(f"\n🚀 Deploying: {app_name}")
    print(f"   📦 Model ID: {model_id}")
    print(f"   🌐 Route: {route_prefix}")

    try:
        # Define and deploy the model
        @serve.deployment(name=app_name, route_prefix=route_prefix)
        class ModelDeployment:
            def __init__(self):
                self.model = BasicModel(model_id)

            def __call__(self, request):
                return self.model(request)

        ModelDeployment.deploy()

        print(f"   ✅ Deployed successfully: {app_name}")

        # Return success result
        return {
            "name": app_name,
            "ok": True,
            "route": route_prefix,
            "model_id": model_id,
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
    """Main function to deploy all models from YAML config"""
    
    print("🔧 Initializing Ray and Ray Serve...")
    ray.init(ignore_reinit_error=True)
    serve.start()

    print(f"\n📖 Loading config from: {yaml_config_path}")
    apps_config = load_multi_model_config(yaml_config_path)

    if not apps_config:
        print("❌ No applications found in config file!")
        return

    print(f"📦 Found {len(apps_config)} application(s) to deploy")

    deployed_apps = []

    for app_config in apps_config:
        result = deploy_model_app(app_config)
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
            print(f"\n• {app['name']}")
            print(f"   Model ID: {app.get('model_id', 'N/A')}")
            print(f"   Base URL: http://localhost:8000{app['route']}")

    if failed:
        print("\n⚠️  Failed Deployments:")
        print("-" * 80)
        for app in failed:
            print(f"   ❌ {app['name']}: {app.get('error', 'Unknown error')}")

    print("\n" + "=" * 80)
    print("🔥 All deployments completed!")
    print("💡 Ray Dashboard: http://localhost:8265")
    print("=" * 80)

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 app_v6.py <path_to_yaml_config>")
        print("Example: python3 app_v6.py multi_model_config.yaml")
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