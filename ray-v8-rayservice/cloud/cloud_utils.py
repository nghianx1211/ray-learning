"""
Cloud storage utilities for downloading models from GCS/S3.
Simplified version based on Ray LLM's cloud utilities.
"""

import os
import logging
from typing import Optional, Tuple
from common.base_pydantic import BaseModelExtended
from pydantic import field_validator

logger = logging.getLogger(__name__)


def is_remote_path(path: str) -> bool:
    """Check if the path is a remote path (GCS or S3).
    
    Args:
        path: The path to check.
        
    Returns:
        True if the path is a remote path, False otherwise.
    """
    return path.startswith("gs://") or path.startswith("s3://")


def is_local_path(path: str) -> bool:
    """Check if the path is a local filesystem path.
    
    Args:
        path: The path to check.
        
    Returns:
        True if the path is a local path (absolute or relative), False otherwise.
    """
    # Local paths start with / (absolute) or don't contain :// (relative or ./path)
    return path.startswith("/") or (not "://" in path and ("/" in path or path.startswith(".")))


def is_huggingface_id(path: str) -> bool:
    """Check if the path is a HuggingFace model ID.
    
    Args:
        path: The path to check.
        
    Returns:
        True if it looks like a HuggingFace ID (org/model format), False otherwise.
    """
    # HuggingFace IDs are typically: organization/model-name
    # They don't contain :// and don't start with / or .
    return "/" in path and not path.startswith(("/", ".")) and "://" not in path


class CloudMirrorConfig(BaseModelExtended):
    """Unified mirror config for cloud storage (S3 or GCS).
    
    Args:
        bucket_uri: URI of the bucket (s3:// or gs://)
    """
    
    bucket_uri: str
    
    @field_validator("bucket_uri")
    @classmethod
    def check_uri_format(cls, value):
        if value is None:
            return value

        if not is_remote_path(value):
            raise ValueError(
                f'Got invalid value "{value}" for bucket_uri. '
                'Expected a URI that starts with "s3://" or "gs://".'
            )
        return value
    
    @property
    def storage_type(self) -> str:
        """Returns the storage type ('s3' or 'gcs') based on the URI prefix."""
        if self.bucket_uri.startswith("s3://"):
            return "s3"
        elif self.bucket_uri.startswith("gs://"):
            return "gcs"
        return None


class CloudFileSystem:
    """Unified interface for cloud storage operations using PyArrow."""
    
    @staticmethod
    def get_fs_and_path(object_uri: str) -> Tuple:
        """Get the appropriate filesystem and path from a URI.
        
        Args:
            object_uri: URI of the file (gs:// or s3://)
            
        Returns:
            Tuple of (filesystem, path)
        """
        try:
            import pyarrow.fs as pa_fs
        except ImportError:
            raise ImportError(
                "You must `pip install pyarrow` to use cloud storage URIs. "
                "Run: pip install pyarrow"
            )
        
        anonymous = False
        
        # Check for anonymous access pattern
        if "@" in object_uri:
            parts = object_uri.split("@", 1)
            if parts[0].endswith("anonymous"):
                anonymous = True
                scheme = parts[0].split("://")[0]
                object_uri = f"{scheme}://{parts[1]}"
        
        if object_uri.startswith("s3://"):
            endpoint = os.getenv("AWS_ENDPOINT_URL_S3", None)
            fs = pa_fs.S3FileSystem(
                anonymous=anonymous,
                endpoint_override=endpoint,
            )
            path = object_uri[5:]  # Remove "s3://"
        elif object_uri.startswith("gs://"):
            fs = pa_fs.GcsFileSystem(anonymous=anonymous)
            path = object_uri[5:]  # Remove "gs://"
        else:
            raise ValueError(f"Unsupported URI scheme: {object_uri}")
        
        return fs, path
    
    @staticmethod
    def download_files(
        local_path: str,
        bucket_uri: str,
    ) -> None:
        """Download files from cloud storage to a local directory.
        
        Args:
            local_path: Local directory where files will be downloaded
            bucket_uri: URI of cloud directory (gs:// or s3://)
        """
        try:
            import pyarrow.fs as pa_fs
        except ImportError:
            raise ImportError("You must `pip install pyarrow` to download from cloud storage.")
        
        try:
            fs, source_path = CloudFileSystem.get_fs_and_path(bucket_uri)
            
            # Ensure the destination directory exists
            os.makedirs(local_path, exist_ok=True)
            
            # List all files in the bucket
            file_selector = pa_fs.FileSelector(source_path, recursive=True)
            file_infos = fs.get_file_info(file_selector)
            
            logger.info(f"Downloading model from {bucket_uri} to {local_path}")
            
            # Download each file
            downloaded_count = 0
            for file_info in file_infos:
                if file_info.type != pa_fs.FileType.File:
                    continue
                
                # Get relative path from source prefix
                rel_path = file_info.path[len(source_path):].lstrip("/")
                
                # Create destination directory if needed
                dest_path = os.path.join(local_path, rel_path)
                dest_dir = os.path.dirname(dest_path)
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                
                # Download the file
                with fs.open_input_file(file_info.path) as source_file:
                    with open(dest_path, "wb") as dest_file:
                        dest_file.write(source_file.read())
                
                downloaded_count += 1
                if downloaded_count % 10 == 0:
                    logger.info(f"Downloaded {downloaded_count} files...")
            
            logger.info(f"Successfully downloaded {downloaded_count} files from {bucket_uri}")
            
        except Exception as e:
            logger.exception(f"Error downloading files from {bucket_uri}: {e}")
            raise


class CloudModelAccessor:
    """Accessor for models stored in cloud storage (GCS or S3).
    
    Args:
        model_source: Either a HuggingFace model ID or a cloud URI (gs:// or s3://)
        cache_dir: Optional local cache directory. If None, uses default cache.
    """
    
    def __init__(self, model_source: str, cache_dir: Optional[str] = None):
        self.model_source = model_source
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/ray-models")
        self.is_remote = is_remote_path(model_source)
        
    def get_local_path(self) -> str:
        """Get the local path for the model, downloading if necessary.
        
        Returns:
            Local path to the model directory
        """
        # If it's not a remote path, return as-is
        if not self.is_remote:
            return self.model_source
        
        # Generate local cache path based on the remote URI
        # e.g., gs://bucket/path/model -> ~/.cache/ray-models/bucket/path/model
        if self.model_source.startswith("gs://"):
            path_part = self.model_source[5:]  # Remove gs://
        elif self.model_source.startswith("s3://"):
            path_part = self.model_source[5:]  # Remove s3://
        else:
            raise ValueError(f"Unsupported URI: {self.model_source}")
        
        local_path = os.path.join(self.cache_dir, path_part)
        
        # Check if already downloaded
        if os.path.exists(local_path) and os.listdir(local_path):
            logger.info(f"Model already cached at {local_path}")
            return local_path
        
        # Download the model
        logger.info(f"Downloading model from {self.model_source} to {local_path}")
        CloudFileSystem.download_files(local_path, self.model_source)
        
        return local_path


def resolve_model_source(model_source: str, cache_dir: Optional[str] = None) -> str:
    """Resolve a model source to a local path or HuggingFace ID.
    
    This is the main entry point for model loading. It handles:
    - **Cloud URIs** (gs://, s3://): Downloads to local cache and returns path
    - **Local paths** (/path/to/model or ./model): Returns as-is after validation
    - **HuggingFace IDs** (org/model): Returns as-is (transformers will download)
    
    Args:
        model_source: Model ID, cloud URI, or local path
        cache_dir: Optional cache directory for cloud models
        
    Returns:
        Local path or model ID to use for loading
        
    Examples:
        >>> resolve_model_source("tiiuae/Falcon3-1B-Instruct")
        "tiiuae/Falcon3-1B-Instruct"  # HuggingFace ID, no download
        
        >>> resolve_model_source("gs://my-bucket/models/falcon-e")
        "/home/user/.cache/ray-models/my-bucket/models/falcon-e"  # Downloaded from GCS
        
        >>> resolve_model_source("/mnt/models/falcon3-1b")
        "/mnt/models/falcon3-1b"  # Local path, used directly
        
        >>> resolve_model_source("./models/my-model")
        "./models/my-model"  # Relative path, used directly
    """
    # Handle cloud storage URIs (GCS, S3) - highest priority
    if is_remote_path(model_source):
        logger.info(f"Detected cloud storage URI: {model_source}")
        accessor = CloudModelAccessor(model_source, cache_dir)
        resolved_path = accessor.get_local_path()
        logger.info(f"Cloud model will be loaded from cache: {resolved_path}")
        return resolved_path
    
    # Handle HuggingFace model IDs - check before local paths
    # HuggingFace IDs: org/model (no leading slash, no ./)
    elif is_huggingface_id(model_source) and not os.path.exists(os.path.expanduser(model_source)):
        logger.info(f"Using HuggingFace model ID: {model_source}")
        logger.info(f"Model will be downloaded from HuggingFace Hub if not cached")
        return model_source
    
    # Handle local filesystem paths (including ones that look like HF IDs but exist locally)
    elif is_local_path(model_source) or os.path.exists(os.path.expanduser(model_source)):
        # Expand user paths like ~/models
        expanded_path = os.path.expanduser(model_source)
        
        # Check if path exists
        if os.path.exists(expanded_path):
            logger.info(f"Using local model path: {expanded_path}")
            # Verify it's a directory with model files
            if os.path.isdir(expanded_path):
                files = os.listdir(expanded_path)
                logger.info(f"Local model directory contains {len(files)} files/folders")
            return expanded_path
        else:
            # Path doesn't exist - log warning but return anyway
            # (might be created later or handled by the model loader)
            logger.warning(f"Local path does not exist: {expanded_path}")
            logger.warning(f"Returning path anyway - ensure it exists before loading!")
            return expanded_path
    
    # Unknown format - return as-is and let the model loader handle it
    else:
        logger.warning(f"Unknown model source format: {model_source}")
        logger.warning(f"Treating as HuggingFace ID or local path")
        return model_source
