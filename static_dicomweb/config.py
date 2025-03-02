"""Configuration management for Static DICOMWeb."""
import os
import json5
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AeConfig(BaseModel):
    """Application Entity configuration."""
    description: str
    host: str
    port: int


class StaticWadoConfig(BaseModel):
    """Base configuration for Static WADO."""
    root_dir: str = Field(alias="rootDir")


class DicomWebServerConfig(StaticWadoConfig):
    """Configuration for DICOMWeb server."""
    proxy_ae: Optional[str] = Field(None, alias="proxyAe")


class DicomWebScpConfig(StaticWadoConfig):
    """Configuration for DICOM SCP service."""
    pass


class Config(BaseModel):
    """Main configuration container."""
    static_wado_config: StaticWadoConfig = Field(alias="staticWadoConfig")
    dicom_web_server_config: DicomWebServerConfig = Field(alias="dicomWebServerConfig")
    dicom_web_scp_config: DicomWebScpConfig = Field(alias="dicomWebScpConfig")
    ae_config: Dict[str, AeConfig] = Field(alias="aeConfig")


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from a JSON5 file.
    
    Args:
        config_path: Optional path to config file. If not provided,
            looks for ./static-wado.json5 or ~/static-wado.json5
    
    Returns:
        Config object
    
    Raises:
        FileNotFoundError: If no config file is found
        ValueError: If config file is invalid
    """
    if not config_path:
        local_config = Path("./static-wado.json5")
        home_config = Path.home() / "static-wado.json5"
        
        if local_config.exists():
            config_path = str(local_config)
        elif home_config.exists():
            config_path = str(home_config)
        else:
            raise FileNotFoundError("No configuration file found")
    
    with open(config_path) as f:
        config_data = json5.load(f)
    
    return Config(**config_data)
