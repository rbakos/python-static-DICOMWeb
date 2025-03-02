"""Tests for DICOMWeb server."""
import json
import pytest
from fastapi.testclient import TestClient
from static_dicomweb.web_server import app
from static_dicomweb.config import Config
from static_dicomweb.dicom_handler import DicomHandler
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid


@pytest.fixture
def test_config(tmp_path):
    """Create test configuration."""
    dicom_dir = tmp_path / "dicomweb"
    dicom_dir.mkdir(parents=True, exist_ok=True)
    dicom_dir_str = str(dicom_dir)
    return Config(
        staticWadoConfig={"rootDir": dicom_dir_str},
        dicomWebServerConfig={"rootDir": dicom_dir_str},
        dicomWebScpConfig={"rootDir": dicom_dir_str},
        aeConfig={}
    )


@pytest.fixture
def test_client(test_config, monkeypatch):
    """Create test client with mocked configuration."""
    from static_dicomweb.web_server import server
    server.config = test_config
    server.handler = DicomHandler(test_config.static_wado_config.root_dir)
    return TestClient(app)


@pytest.fixture
def sample_dicom_file():
    """Create a sample DICOM file."""
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.2"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.ImplementationClassUID = generate_uid()
    file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"  # Explicit VR Little Endian
    
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.StudyDate = "20230101"
    ds.SeriesNumber = "1"
    ds.InstanceNumber = "1"
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = bytes([0] * (512 * 512 * 2))
    
    # Convert to bytes
    with pydicom.filebase.DicomBytesIO() as buffer:
        ds.save_as(buffer)
        return buffer.getvalue()


def test_store_instance(test_client, sample_dicom_file):
    """Test storing a DICOM instance."""
    response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    assert response.status_code == 200
    data = response.json()
    assert "study_uid" in data
    assert "series_uid" in data
    assert "instance_uid" in data


def test_get_studies(test_client, sample_dicom_file):
    """Test retrieving studies."""
    # First store a DICOM instance
    test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    
    # Get studies
    response = test_client.get("/studies")
    assert response.status_code == 200
    studies = response.json()
    assert len(studies) == 1
    assert "uid" in studies[0]
    assert "date" in studies[0]


def test_get_series(test_client, sample_dicom_file):
    """Test retrieving series."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    
    # Get series
    response = test_client.get(f"/studies/{study_uid}/series")
    assert response.status_code == 200
    series = response.json()
    assert len(series) == 1
    assert "uid" in series[0]
    assert "number" in series[0]


def test_get_instances(test_client, sample_dicom_file):
    """Test retrieving instances."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    series_uid = store_response.json()["series_uid"]
    
    # Get instances
    response = test_client.get(f"/studies/{study_uid}/series/{series_uid}/instances")
    assert response.status_code == 200
    instances = response.json()
    assert len(instances) == 1
    assert "uid" in instances[0]
    assert "number" in instances[0]


def test_get_metadata(test_client, sample_dicom_file):
    """Test retrieving metadata."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    series_uid = store_response.json()["series_uid"]
    instance_uid = store_response.json()["instance_uid"]
    
    # Get metadata
    response = test_client.get(
        f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata"
    )
    assert response.status_code == 200
    metadata = response.json()
    assert "0020000D" in metadata  # StudyInstanceUID
    assert "0020000E" in metadata  # SeriesInstanceUID
    assert "00080018" in metadata  # SOPInstanceUID
    assert "00280010" in metadata  # Rows


def test_get_pixel_data(test_client, sample_dicom_file):
    """Test retrieving pixel data."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    series_uid = store_response.json()["series_uid"]
    instance_uid = store_response.json()["instance_uid"]
    
    # Get pixel data
    response = test_client.get(
        f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/pixel-data"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert len(response.content) == 512 * 512 * 2  # Size of our test pixel data (16-bit)


def test_get_nonexistent_metadata(test_client):
    """Test retrieving metadata for nonexistent instance."""
    response = test_client.get(
        "/studies/nonexistent/series/nonexistent/instances/nonexistent/metadata"
    )
    assert response.status_code == 404


def test_get_nonexistent_pixel_data(test_client):
    """Test retrieving pixel data for nonexistent instance."""
    response = test_client.get(
        "/studies/nonexistent/series/nonexistent/instances/nonexistent/frames/1"
    )
    assert response.status_code == 404


def test_get_frame(test_client, sample_dicom_file):
    """Test retrieving frame data."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    series_uid = store_response.json()["series_uid"]
    instance_uid = store_response.json()["instance_uid"]
    
    # Get frame data
    response = test_client.get(
        f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/1"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert len(response.content) > 0


def test_get_study_thumbnail(test_client, sample_dicom_file):
    """Test retrieving study thumbnail."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    
    # Get study thumbnail
    response = test_client.get(f"/studies/{study_uid}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0


def test_get_series_thumbnail(test_client, sample_dicom_file):
    """Test retrieving series thumbnail."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    series_uid = store_response.json()["series_uid"]
    
    # Get series thumbnail
    response = test_client.get(f"/studies/{study_uid}/series/{series_uid}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0


def test_get_instance_thumbnail(test_client, sample_dicom_file):
    """Test retrieving instance thumbnail."""
    # First store a DICOM instance
    store_response = test_client.post(
        "/instances",
        files={"file": ("test.dcm", sample_dicom_file)}
    )
    study_uid = store_response.json()["study_uid"]
    series_uid = store_response.json()["series_uid"]
    instance_uid = store_response.json()["instance_uid"]
    
    # Get instance thumbnail
    response = test_client.get(
        f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/thumbnail"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0


def test_get_nonexistent_thumbnail(test_client):
    """Test retrieving thumbnail for nonexistent study."""
    response = test_client.get("/studies/nonexistent/thumbnail")
    assert response.status_code == 404
