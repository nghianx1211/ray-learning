from typing import Any, Dict, List
from ray import serve
import yaml
import sys
import os
from configs.server_models import MultiModelConfig
from rich.console import Console
from rich.table import Table

from serve.deployments.multi_model_deployment import MultiModelDeployment
from serve.router.router import MultiModelRouter

console = Console()

def build_app(args: dict):
    """Build and return the Ray Serve application."""
    yaml_config_path = args.get("config_path", os.environ.get("MODEL_CONFIG_PATH", "model_config.yaml"))
    
    configs = load_multi_model_config(yaml_config_path)
    console.print(f"[bold green]✅ Successfully loaded {len(configs)} models from {yaml_config_path}[/bold green]")
    print_configs(configs)

    # Get CUDA_VISIBLE_DEVICES from environment
    cuda_visible_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
    console.print(f"[bold cyan]🎮 Using CUDA_VISIBLE_DEVICES={cuda_visible_devices}[/bold cyan]")
    
    # CRITICAL: Set runtime_env for Ray actors
    ray_actor_options = {
        "runtime_env": {
            "env_vars": {
                "CUDA_VISIBLE_DEVICES": cuda_visible_devices
            }
        }
    }

    # Apply ray_actor_options to all model deployments
    deployments = [
        MultiModelDeployment.options(ray_actor_options=ray_actor_options).bind([cfg]) 
        for cfg in configs
    ]
    
    # Router deployment with runtime_env
    router_deployment = MultiModelRouter.as_deployment(configs)
    router = router_deployment.options(ray_actor_options=ray_actor_options).bind(deployments)
    
    return router

def load_config(yaml_path: str) -> MultiModelConfig:
    """Load a single-model config (first model from YAML)."""
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    if 'llm_configs' not in config:
        raise ValueError("Invalid YAML: missing top-level key 'llm_configs'.")

    model_config = config['llm_configs'][0]

    return MultiModelConfig(
        model_loading_config=model_config['model_loading_config'],
        deployment_config=model_config.get('deployment_config', {}),
        engine_kwargs=model_config.get('engine_kwargs', {})
    )


def load_multi_model_config(yaml_path: str) -> List[MultiModelConfig]:
    """Load multi-model configurations from YAML file."""
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    llm_configs = []
    try:
        for app in config.get('applications', []):
            for llm_config in app.get('args', {}).get('llm_configs', []):
                llm_configs.append(MultiModelConfig(
                    model_loading_config=llm_config['model_loading_config'],
                    deployment_config=llm_config.get('deployment_config', {}),
                    engine_kwargs=llm_config.get('engine_kwargs', {})
                ))
    except KeyError as e:
        raise ValueError(f"Invalid YAML structure: Missing expected key {e}.") from e

    return llm_configs


def print_configs(configs: List[MultiModelConfig]):
    """Pretty print all loaded model configs."""
    table = Table(title="Loaded MultiModel Configs", show_lines=True)
    table.add_column("Model ID", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("GPU Util", style="green")
    table.add_column("Deployment Name", style="magenta")
    table.add_column("Autoscaling", style="blue")

    for cfg in configs:
        model_id = cfg.model_loading_config.get("model_id", "N/A")
        model_type = cfg.model_loading_config.get("type", "Unknown")
        gpu_util = str(cfg.engine_kwargs.get("gpu_memory_utilization", ""))
        deploy_name = cfg.deployment_config.get("name", "unnamed-deployment")
        autoscaling = cfg.deployment_config.get("autoscaling_config", {})

        table.add_row(model_id, model_type, gpu_util, deploy_name, str(autoscaling))

    console.print(table)


def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] python load_config.py <path_to_yaml>")
        sys.exit(1)

    yaml_config_path = sys.argv[1]

    try:
        configs = load_multi_model_config(yaml_config_path)
        console.print(f"[bold green]✅ Successfully loaded {len(configs)} models from {yaml_config_path}[/bold green]")
        print_configs(configs)

        # Get CUDA_VISIBLE_DEVICES from environment
        cuda_visible_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
        console.print(f"[bold cyan]🎮 Using CUDA_VISIBLE_DEVICES={cuda_visible_devices}[/bold cyan]")
        
        # CRITICAL: Set runtime_env for Ray actors
        ray_actor_options = {
            "runtime_env": {
                "env_vars": {
                    "CUDA_VISIBLE_DEVICES": cuda_visible_devices
                }
            }
        }

        # Apply ray_actor_options to all model deployments
        deployments = [
            MultiModelDeployment.options(ray_actor_options=ray_actor_options).bind([cfg]) 
            for cfg in configs
        ]
        
        # Router deployment with runtime_env
        router_deployment = MultiModelRouter.as_deployment(configs)
        router = router_deployment.options(ray_actor_options=ray_actor_options).bind(deployments)
        
        serve.run(router)
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()