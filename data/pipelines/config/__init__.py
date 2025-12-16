# Make ingestion.config a proper Python package so imports like
# `from config.environment import ...` work when INGESTION_DIR is on PYTHONPATH.

from .environment import (
    EnvironmentConfig,
    get_config,
    is_local_mode,
    is_cloud_mode,
    get_database_url,
    logger,
)

__all__ = [
    "EnvironmentConfig",
    "get_config",
    "is_local_mode",
    "is_cloud_mode",
    "get_database_url",
    "logger",
]
