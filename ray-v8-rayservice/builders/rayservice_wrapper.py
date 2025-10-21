#!/usr/bin/env python3
"""
RayService wrapper for builders.app_builder.
This makes build_app() compatible with RayService's import_path requirement.

RayService expects a module-level variable that is a Serve application.
This wrapper creates that variable by calling build_app().

Usage in RayService serveConfigV2:
    # Method 2: Inline config (like Ray official!)
    applications:
      - name: "my-model"
        import_path: builders.rayservice_wrapper:build_app_from_args
        args:
          config_path: "/config/model_config.yaml"
          # Or inline config like Ray official:
          # llm_configs:
          #   - model_loading_config: {...}

Note: This wrapper handles both single and multiple model configs:
- Single model: Returns the router directly
- Multiple models: Returns first model (or specify MODEL_ID env var)
"""
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
    
    This enables inline config in serveConfigV2:
        applications:
          - name: "my-model"
            import_path: builders.rayservice_wrapper:build_app_from_args
            args:
              # Method 1: File path
              config_path: "/config/model.yaml"
              
              # Method 2: Inline config (like Ray official!)
              llm_configs:
                - model_loading_config:
                    model_id: "falcone-3b-instruct"
                    model_source: "/path/to/model"
                  deployment_config: {...}
                  engine_kwargs: {...}
    
    Supports:
    1. File path: args = {"config_path": "/path/to/config.yaml"}
    2. Inline dict: args = {"llm_configs": [{...}]}  ← Like Ray official!
    """
    print(f"🚀 Building app from args: {list(args.keys())}")
    
    # Check if inline config provided (like Ray official)
    if "llm_configs" in args:
        print("   Using inline llm_configs")
        
        # Create temporary YAML structure matching your model_config.yaml format
        import tempfile
        import yaml
        
        llm_configs = args["llm_configs"]
        
        # Wrap in applications structure (your format)
        temp_config = {
            "applications": [{
                "name": "inline-app",
                "route_prefix": "/inline",
                "args": {
                    "llm_configs": llm_configs
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
            import os as os_module
            os_module.unlink(temp_path)
            
            # Handle dict vs single app
            if isinstance(built_app, dict):
                first = list(built_app.values())[0]
                print(f"✓ Built from inline config")
                return first
            return built_app
            
        except Exception as e:
            # Cleanup on error
            import os as os_module
            if os_module.path.exists(temp_path):
                os_module.unlink(temp_path)
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
