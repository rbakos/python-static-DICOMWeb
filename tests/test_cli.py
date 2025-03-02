"""Tests for command-line interface."""
import json
import pytest
from click.testing import CliRunner
from static_dicomweb.cli import cli
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_config_file(tmp_path):
    """Create a sample configuration file."""
    config = {
        "staticWadoConfig": {
            "rootDir": str(tmp_path / "dicomweb")
        },
        "dicomWebServerConfig": {
            "rootDir": str(tmp_path / "dicomweb")
        },
        "dicomWebScpConfig": {
            "rootDir": str(tmp_path / "dicomweb")
        },
        "aeConfig": {}
    }
    
    config_file = tmp_path / "config.json5"
    config_file.write_text(json.dumps(config))
    return str(config_file)


@pytest.fixture
def sample_dicom_file(tmp_path):
    """Create a sample DICOM file."""
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.ImplementationClassUID = generate_uid()
    file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"  # Explicit VR Little Endian
    
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.StudyDate = "20230101"
    ds.StudyDescription = "Test Study"
    ds.SeriesNumber = "1"
    ds.InstanceNumber = "1"
    ds.Rows = 512
    ds.Columns = 512
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.PixelData = bytes([0] * (512 * 512 * 2))
    
    dicom_file = tmp_path / "test.dcm"
    ds.save_as(str(dicom_file))
    return str(dicom_file)


def test_store_command(runner, sample_config_file, sample_dicom_file):
    """Test storing a DICOM file."""
    result = runner.invoke(cli, [
        'store',
        '--config', sample_config_file,
        sample_dicom_file
    ])
    
    assert result.exit_code == 0
    assert "Successfully stored DICOM file" in result.output
    assert "Study UID" in result.output
    assert "Series UID" in result.output
    assert "Instance UID" in result.output


def test_list_studies_command(runner, sample_config_file, sample_dicom_file):
    """Test listing studies."""
    # First store a DICOM file
    runner.invoke(cli, [
        'store',
        '--config', sample_config_file,
        sample_dicom_file
    ])
    
    # Then list studies
    result = runner.invoke(cli, [
        'list-studies',
        '--config', sample_config_file
    ])
    
    assert result.exit_code == 0
    assert "Available studies" in result.output
    assert "Study UID" in result.output
    assert "Date: 20230101" in result.output
    assert "Description: Test Study" in result.output


def test_store_invalid_dicom(runner, sample_config_file, tmp_path):
    """Test storing invalid DICOM file."""
    invalid_file = tmp_path / "invalid.dcm"
    invalid_file.write_text("not a dicom file")
    
    result = runner.invoke(cli, [
        'store',
        '--config', sample_config_file,
        str(invalid_file)
    ])
    
    assert result.exit_code == 1
    assert "Error" in result.output


def test_list_studies_empty(runner, sample_config_file):
    """Test listing studies when none exist."""
    result = runner.invoke(cli, [
        'list-studies',
        '--config', sample_config_file
    ])
    
    assert result.exit_code == 0
    assert "No studies found" in result.output
