#!/usr/bin/env python3
"""
Deploy Ray Serve applications with custom app names based on model_id.
Usage: python deploy_app.py [config_path]
"""
import sys
import os
from ray import serve


from builders.app_builder import build_app, load_multi_model_config
from serve.health import deploy_health_check
from rich.console import Console

console = Console()

def main():
    # Get config path from args or environment
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # Try K8s ConfigMap path first, then fall back to local
        config_path = os.environ.get("MODEL_CONFIG_PATH", "/config/model_config.yaml")
        if not os.path.exists(config_path):
            config_path = "model_config.yaml"  # Local development fallback
    
    console.print(f"[bold cyan]📋 Loading config from: {config_path}[/bold cyan]")
    
    # Deploy health check endpoint first (for K8s probes)
    console.print("[bold yellow]Deploying health check endpoint...[/bold yellow]")
    try:
        deploy_health_check()
        console.print("[bold green]✓ Health check endpoint ready at /-/healthz[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Warning: Health check deployment failed: {e}[/bold red]")
    
    # Load configs to get model IDs
    configs = load_multi_model_config(config_path)
    
    # Build and deploy application(s)
    if len(configs) == 1:
        # Single model - use model_id as app name
        model_id = configs[0].model_loading_config.get("model_id", "default")
        console.print(f"[bold green]Deploying single model application: {model_id}[/bold green]")
        
        app = build_app({"config_path": config_path})
        serve.run(app, name=model_id, route_prefix=f"/{model_id}")
        
        console.print(f"[bold green]Application '{model_id}' deployed successfully![/bold green]")
        console.print(f"[bold cyan]📍 Endpoint: http://127.0.0.1:8000/{model_id}[/bold cyan]")
    else:
        # Multiple models - deploy each as separate application
        console.print(f"[bold green]Deploying {len(configs)} separate applications in parallel[/bold green]")
        
        # Initialize Serve once before parallel deployment
        from ray.serve._private.api import serve_start
        serve_start(detached=True)
        
        apps_dict = build_app({"config_path": config_path})
        
        def deploy_app(model_id, app):
            console.print(f"\n[bold yellow]Deploying: {model_id}[/bold yellow]")
            serve.run(app, name=model_id, route_prefix=f"/{model_id}")
            console.print(f"[bold green]Application '{model_id}' deployed[/bold green]")
            console.print(f"[bold cyan]📍 Endpoint: http://127.0.0.1:8000/{model_id}[/bold cyan]")
        
        # Deploy all apps in parallel using threads
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(apps_dict)) as executor:
            futures = [executor.submit(deploy_app, model_id, app) 
                      for model_id, app in apps_dict.items()]
            # Wait for all deployments to complete
            for future in futures:
                future.result()
    
    console.print("\n[bold green]🎉 All applications deployed successfully![/bold green]")
    console.print("[bold cyan]💡 Press Ctrl+C to stop[/bold cyan]")
    
    # Keep the script running
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️  Shutting down...[/bold yellow]")
        serve.shutdown()
        console.print("[bold green]Shutdown complete[/bold green]")

if __name__ == "__main__":
    main()
