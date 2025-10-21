from common.base_pydantic import BaseModelExtended
from pydantic import Field, field_validator
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

def is_remote_path(path: str) -> bool:
    """Check if the path is a remote path.

    Args:
        path: The path to check.

    Returns:
        True if the path is a remote path, False otherwise.
    """
    return path.startswith("s3://") or path.startswith("gs://")


class ExtraFiles(BaseModelExtended):
    bucket_uri: str
    destination_path: str


class CloudMirrorConfig(BaseModelExtended):
    """Unified mirror config for cloud storage (S3 or GCS).

    Args:
        bucket_uri: URI of the bucket (s3:// or gs://)
        extra_files: Additional files to download
    """

    bucket_uri: Optional[str] = None
    extra_files: List[ExtraFiles] = Field(default_factory=list)

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
        if self.bucket_uri is None:
            return None
        elif self.bucket_uri.startswith("s3://"):
            return "s3"
        elif self.bucket_uri.startswith("gs://"):
            return "gcs"
        return None
