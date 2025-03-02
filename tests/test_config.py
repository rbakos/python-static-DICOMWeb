"""Tests for configuration management."""
import os
import pytest
from pathlib import Path
from static_dicomweb.config import load_config, Config


@pytest.fixture
def sample_config_file(tmp_path):
    """Create a sample config file for testing."""
    config_content = """{
        staticWadoConfig: {
            rootDir: "/dicomweb",
        },
        dicomWebServerConfig: {
            rootDir: "/dicomweb",
            proxyAe: "myProxyAe",
        },
        dicomWebScpConfig: {
            rootDir: "/dicomweb",
        },
        aeConfig: {
            myProxyAe: {
                description: "A proxy AE to use",
                host: "proxyAe.hospital.com",
                port: 104,
            },
        }
    }"""
    
    config_file = tmp_path / "static-wado.json5"
    config_file.write_text(config_content)
    return str(config_file)


def test_load_config(sample_config_file):
    """Test loading configuration from file."""
    config = load_config(sample_config_file)
    assert isinstance(config, Config)
    assert config.static_wado_config.root_dir == "/dicomweb"
    assert config.dicom_web_server_config.proxy_ae == "myProxyAe"
    assert config.ae_config["myProxyAe"].port == 104


def test_load_config_missing_file():
    """Test error when config file is missing."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.json5")


def test_load_config_invalid_content(tmp_path):
    """Test error with invalid config content."""
    invalid_config = tmp_path / "invalid.json5"
    invalid_config.write_text("{invalid json5")
    
    with pytest.raises(Exception):
        load_config(str(invalid_config))
