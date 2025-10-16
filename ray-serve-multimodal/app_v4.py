"""
app_v4.py - Multi-model Ray Serve application
Hỗ trợ deploy nhiều model động từ YAML config
Mỗi model có route riêng và config riêng
"""
import yaml
import ray
from ray import serve
from typing import Dict, Any, List

def load_multi_model_config(yaml_path: str) -> List[Dict[str, Any]]:
    """Load multi-model config từ YAML file"""
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    return config.get('applications', [])

def deploy_model_app(app_config: Dict[str, Any]):
    """
    Deploy một model application từ config
    Sử dụng build_openai_app từ ray.serve.llm
    """
    from ray.serve.llm import build_openai_app
    
    app_name = app_config['name']
    route_prefix = app_config['route_prefix']
    llm_configs = app_config['args']['llm_configs']

    # Validate and filter llm_configs fields
    def filter_keys(source_dict, allowed_keys):
        return {key: source_dict[key] for key in allowed_keys if key in source_dict}

    # Define allowed keys for each field
    allowed_model_loading_keys = {'model_id', 'model_source'}
    allowed_deployment_keys = {'name', 'num_replicas', 'max_concurrent_queries', 'autoscaling_config', 'min_replicas', 'max_replicas', 'cpus', 'gpus'}
    allowed_engine_keys = {'tensor_parallel_size', 'custom_all_reduce'}

    # Construct llm_serving_args with validated fields
    llm_serving_args = {
        'llm_configs': [
            {
                'model_loading_config': filter_keys(llm_configs[0]['model_loading_config'], allowed_model_loading_keys),
                'deployment_config': filter_keys(llm_configs[0]['deployment_config'], allowed_deployment_keys),
                'engine_kwargs': filter_keys(llm_configs[0]['engine_kwargs'], allowed_engine_keys),
            }
        ]
    }

    print(f"\n🚀 Deploying: {app_name}")
    print(f"   📦 Model ID: {llm_serving_args['llm_configs'][0]['model_loading_config']['model_id']}")
    print(f"   🌐 Route: {route_prefix}")

    # Build application sử dụng build_openai_app
    app = build_openai_app(llm_serving_args=llm_serving_args)

    # Deploy application
    serve.run(
        app,
        name=app_name,
        route_prefix=route_prefix
    )

    print(f"   ✅ Deployed successfully!")

    deployment_config = llm_serving_args['llm_configs'][0]['deployment_config']

    return {
        'name': app_name,
        'route': route_prefix,
        'model': llm_serving_args['llm_configs'][0]['model_loading_config']['model_id'],
        'model_source': llm_serving_args['llm_configs'][0]['model_loading_config'].get('model_source', 'N/A'),
        'min_replicas': deployment_config.get('min_replicas', 'N/A'),
        'max_replicas': deployment_config.get('max_replicas', 'N/A'),
        'cpus': deployment_config.get('cpus', 'N/A'),
        'gpus': deployment_config.get('gpus', 'N/A')
    }

def main(yaml_config_path: str):
    """Main function để deploy tất cả models từ YAML config"""
    
    # Khởi tạo Ray và Serve
    print("🔧 Initializing Ray and Ray Serve...")
    ray.init(ignore_reinit_error=True)
    serve.start(detached=True)
    
    # Load config
    print(f"\n📖 Loading config from: {yaml_config_path}")
    apps_config = load_multi_model_config(yaml_config_path)
    
    if not apps_config:
        print("No applications found in config file!")
        return
    
    print(f"📦 Found {len(apps_config)} application(s) to deploy")
    
    # Deploy từng model application
    deployed_apps = []
    for app_config in apps_config:
        try:
            app_info = deploy_model_app(app_config)
            deployed_apps.append(app_info)
        except Exception as e:
            print(f"❌ Error deploying {app_config['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("✅ Deployment Summary")
    print("="*80)
    print(f"Total applications deployed: {len(deployed_apps)}/{len(apps_config)}")
    
    if deployed_apps:
        print("\n📋 Deployed Applications:")
        print("-" * 80)
        for app in deployed_apps:
            print(f"\n� {app['name']}")
            print(f"   Model: {app['model_source']}")
            print(f"   Replicas: {app['min_replicas']} → {app['max_replicas']} (autoscaling)")
            print(f"   Resources: {app['cpus']} CPUs, {app['gpus']} GPUs per replica")
            print(f"   Base URL: http://localhost:8000{app['route']}")
            print(f"   Endpoints:")
            print(f"     • POST {app['route']}/v1/chat/completions")
            print(f"     • POST {app['route']}/v1/completions")
            print(f"     • GET  {app['route']}/v1/models")
    
    print("\n" + "="*80)
    print("🔥 All applications are running!")
    print("💡 Tip: Check status at http://localhost:8265 (Ray Dashboard)")
    print("="*80)

if __name__ == "__main__":
    import sys
    import time
    
    if len(sys.argv) < 2:
        print("Usage: python app_v4.py <path_to_yaml_config>")
        print("Example: python app_v4.py multi_model_config.yaml")
        sys.exit(1)
    
    yaml_config_path = sys.argv[1]
    
    try:
        main(yaml_config_path)
        
        print("\n⏸️  Keep this running to serve requests...")
        print("   Press Ctrl+C to shutdown")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        serve.shutdown()
        print("✓ Shutdown complete!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
