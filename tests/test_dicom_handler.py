"""Tests for DICOM handling functionality."""
import os
import json
import pytest
from pathlib import Path
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid
from static_dicomweb.dicom_handler import DicomHandler


@pytest.fixture
def temp_dicom_dir(tmp_path):
    """Create a temporary directory for DICOM files."""
    return str(tmp_path / "dicomweb")


@pytest.fixture
def dicom_handler(temp_dicom_dir):
    """Create a DicomHandler instance."""
    return DicomHandler(temp_dicom_dir)


@pytest.fixture
def sample_dicom_dataset():
    """Create a sample DICOM dataset."""
    # Create a basic DICOM dataset
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.2"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.ImplementationClassUID = generate_uid()
    file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"  # Explicit VR Little Endian
    
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    
    # Add required UIDs
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    
    # Add some metadata
    ds.StudyDate = "20230101"
    ds.StudyTime = "120000"
    ds.StudyDescription = "Test Study"
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "Test Series"
    ds.InstanceNumber = "1"
    
    # Add image data
    ds.Rows = 512
    ds.Columns = 512
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.PixelData = bytes([0] * (512 * 512 * 2))
    
    return ds


def test_store_dicom(dicom_handler, sample_dicom_dataset):
    """Test storing DICOM data."""
    # Convert dataset to bytes
    with pydicom.filebase.DicomBytesIO() as buffer:
        sample_dicom_dataset.save_as(buffer)
        dicom_bytes = buffer.getvalue()
    
    # Store the DICOM data
    result = dicom_handler.store_dicom(dicom_bytes)
    
    assert "study_uid" in result
    assert "series_uid" in result
    assert "instance_uid" in result
    
    # Check that files were created
    instance_path = Path(dicom_handler.root_dir) / "studies" / result["study_uid"] / "series" / result["series_uid"] / "instances" / result["instance_uid"]
    assert (instance_path / "metadata.json.gz").exists()
    assert (instance_path / "pixel_data.raw").exists()


def test_get_metadata(dicom_handler, sample_dicom_dataset):
    """Test retrieving metadata."""
    # Store the DICOM data first
    with pydicom.filebase.DicomBytesIO() as buffer:
        sample_dicom_dataset.save_as(buffer)
        dicom_bytes = buffer.getvalue()
    
    uids = dicom_handler.store_dicom(dicom_bytes)
    
    # Get metadata
    metadata = dicom_handler.get_metadata(
        uids["study_uid"],
        uids["series_uid"],
        uids["instance_uid"]
    )
    
    assert metadata["0020000D"]["Value"][0] == uids["study_uid"]
    assert metadata["0020000E"]["Value"][0] == uids["series_uid"]
    assert metadata["00080018"]["Value"][0] == uids["instance_uid"]
    assert metadata["00081030"]["Value"][0] == "Test Study"
    assert metadata["00280010"]["Value"][0] == 512


def test_get_pixel_data(dicom_handler, sample_dicom_dataset):
    """Test retrieving pixel data."""
    # Store the DICOM data first
    with pydicom.filebase.DicomBytesIO() as buffer:
        sample_dicom_dataset.save_as(buffer)
        dicom_bytes = buffer.getvalue()
    
    uids = dicom_handler.store_dicom(dicom_bytes)
    
    # Get pixel data
    pixel_data = dicom_handler.get_pixel_data(
        uids["study_uid"],
        uids["series_uid"],
        uids["instance_uid"]
    )
    
    assert pixel_data == sample_dicom_dataset.PixelData


def test_get_studies_series_instances(dicom_handler, sample_dicom_dataset):
    """Test retrieving study, series, and instance lists."""
    # Store the DICOM data first
    with pydicom.filebase.DicomBytesIO() as buffer:
        sample_dicom_dataset.save_as(buffer)
        dicom_bytes = buffer.getvalue()
    
    uids = dicom_handler.store_dicom(dicom_bytes)
    
    # Test getting studies
    studies = dicom_handler.get_studies()
    assert len(studies) == 1
    assert studies[0] == uids["study_uid"]
    
    # Test getting series
    series = dicom_handler.get_series(uids["study_uid"])
    assert len(series) == 1
    assert series[0] == uids["series_uid"]
    
    # Test getting instances
    instances = dicom_handler.get_instances(uids["study_uid"], uids["series_uid"])
    assert len(instances) == 1
    assert instances[0] == uids["instance_uid"]


def test_invalid_dicom_data(dicom_handler):
    """Test handling invalid DICOM data."""
    with pytest.raises(ValueError):
        dicom_handler.store_dicom(b"invalid dicom data")


def test_missing_metadata(dicom_handler):
    """Test handling missing metadata."""
    with pytest.raises(FileNotFoundError):
        dicom_handler.get_metadata("nonexistent", "nonexistent", "nonexistent")


def test_missing_pixel_data(dicom_handler):
    """Test handling missing pixel data."""
    with pytest.raises(FileNotFoundError):
        dicom_handler.get_pixel_data("nonexistent", "nonexistent", "nonexistent")
