#!/usr/bin/env python3
from builders.app_builder import build_app
import os

def _build_rayservice_app():
    """
    Build the app for RayService from environment variables.
    Called lazily when RayService imports this module.
    """
    # Get config path from environment
    config_path = os.environ.get("MODEL_CONFIG_PATH", "/config/model_config.yaml")
    
    print(f"🚀 Building RayService app from: {config_path}")
    
    # Build application using existing builder
    # build_app returns:
    # - Single model: router (Serve deployment)
    # - Multiple models: dict of routers
    built_app = build_app({"config_path": config_path})
    
    if isinstance(built_app, dict):
        # Multiple models - RayService needs single entry point
        target_model = os.environ.get("MODEL_ID")
        
        if target_model:
            if target_model in built_app:
                print(f"✓ Using model: {target_model}")
                return built_app[target_model]
            else:
                available = list(built_app.keys())
                raise ValueError(
                    f"MODEL_ID={target_model} not found. "
                    f"Available models: {available}"
                )
        else:
            # No MODEL_ID specified - use first model
            first_model = list(built_app.keys())[0]
            print(f"⚠️  Multiple models detected, using first: {first_model}")
            print(f"💡 Available models: {list(built_app.keys())}")
            print(f"💡 Set MODEL_ID env var to choose specific model")
            return built_app[first_model]
    else:
        # Single model - perfect for RayService
        print(f"✓ Single model application ready")
        return built_app


def build_app_from_args(args: dict):
    """
    Build app from serveConfigV2 args - exactly like Ray official build_openai_app()!
    
    This enables multiple config methods in serveConfigV2:
        applications:
          - name: "my-model"
            import_path: builders.rayservice_wrapper:build_app_from_args
            args:
              # Method 1: Full config file path
              config_path: "/config/model_config.yaml"
              
              # Method 2: Single model config file path (NEW!)
              llm_configs:
                - models/h1/falcon-h1-0.5b-instruct.yaml
              
              # Method 3: Inline dict config (like Ray official!)
              llm_configs:
                - model_loading_config:
                    model_id: "falcone-3b-instruct"
                    model_source: "/path/to/model"
                  deployment_config: {...}
                  engine_kwargs: {...}
    
    Supports:
    1. Full config path: args = {"config_path": "/path/to/config.yaml"}
    2. Model file paths: args = {"llm_configs": ["models/h1/model1.yaml", "models/e/model2.yaml"]}
    3. Inline dict: args = {"llm_configs": [{...}]}  ← Like Ray official!
    """
    print(f"🚀 Building app from args: {list(args.keys())}")
    import yaml
    import tempfile
    
    # Check if llm_configs is provided
    if "llm_configs" in args:
        llm_configs_arg = args["llm_configs"]
        
        # Check if it's a list of file paths (strings) or inline dicts
        if isinstance(llm_configs_arg, list) and len(llm_configs_arg) > 0:
            first_item = llm_configs_arg[0]
            
            # Case 1: List of YAML file paths
            if isinstance(first_item, str):
                print(f"   Loading {len(llm_configs_arg)} model config file(s)")
                
                loaded_configs = []
                for config_file in llm_configs_arg:
                    print(f"   - Loading: {config_file}")
                    with open(config_file, 'r') as f:
                        model_cfg = yaml.safe_load(f)
                        loaded_configs.append(model_cfg)
                
                # Wrap in applications structure
                temp_config = {
                    "applications": [{
                        "name": "multi-model-app",
                        "route_prefix": "/",
                        "args": {
                            "llm_configs": loaded_configs
                        }
                    }]
                }
                
                # Write to temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    yaml.dump(temp_config, f)
                    temp_path = f.name
                
                print(f"   Created temp config: {temp_path}")
                
                try:
                    # Build using existing builder
                    built_app = build_app({"config_path": temp_path})
                    
                    # Cleanup
                    os.unlink(temp_path)
                    
                    # Handle dict vs single app
                    if isinstance(built_app, dict):
                        first = list(built_app.values())[0]
                        print(f"✓ Built from {len(llm_configs_arg)} model file(s)")
                        return first
                    return built_app
                    
                except Exception as e:
                    # Cleanup on error
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise e
            
            # Case 2: Inline dict configs
            elif isinstance(first_item, dict):
                print(f"   Using inline llm_configs (dict format)")
                
                # Wrap in applications structure
                temp_config = {
                    "applications": [{
                        "name": "inline-app",
                        "route_prefix": "/inline",
                        "args": {
                            "llm_configs": llm_configs_arg
                        }
                    }]
                }
                
                # Write to temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    yaml.dump(temp_config, f)
                    temp_path = f.name
                
                print(f"   Created temp config: {temp_path}")
                
                try:
                    # Build using existing builder
                    built_app = build_app({"config_path": temp_path})
                    
                    # Cleanup
                    os.unlink(temp_path)
                    
                    # Handle dict vs single app
                    if isinstance(built_app, dict):
                        first = list(built_app.values())[0]
                        print(f"✓ Built from inline config")
                        return first
                    return built_app
                    
                except Exception as e:
                    # Cleanup on error
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise e
    
    # File path mode
    elif "config_path" in args:
        config_path = args["config_path"]
        print(f"   Using config file: {config_path}")
    else:
        # Fallback to env var
        config_path = os.environ.get("MODEL_CONFIG_PATH", "/config/model_config.yaml")
        print(f"   Using config from env: {config_path}")
    
    # Build using existing builder
    built_app = build_app({"config_path": config_path})
    
    # Handle dict vs single app
    if isinstance(built_app, dict):
        # Multiple models - take first or use model_id from args
        model_id = args.get("model_id") or os.environ.get("MODEL_ID")
        if model_id and model_id in built_app:
            print(f"✓ Selected model: {model_id}")
            return built_app[model_id]
        else:
            first = list(built_app.keys())[0]
            print(f"✓ Using first model: {first}")
            return built_app[first]
    
    print(f"✓ Single model application ready")
    return built_app


# Create the app variable that RayService will import
# This is evaluated when the module is imported
app = _build_rayservice_app()
