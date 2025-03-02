"""Comprehensive tests for DICOMWeb server functionality."""
import os
import io
import json
import gzip
import shutil
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid
from static_dicomweb.web_server import app, init_server_with_config
from static_dicomweb.config import Config

@pytest.fixture
def test_env():
    """Set up test environment."""
    test_dir = "/tmp/dicomweb_test"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    # Initialize server with test config
    config = Config(
        staticWadoConfig={"rootDir": test_dir},
        dicomWebServerConfig={"rootDir": test_dir},
        dicomWebScpConfig={"rootDir": test_dir},
        aeConfig={}
    )
    init_server_with_config(config=config)
    
    # Create test client
    client = TestClient(app)
    
    # Create test DICOM dataset
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.2'  # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.ImplementationClassUID = generate_uid()
    file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'  # Explicit VR Little Endian
    
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b'\0' * 128)
    
    # Study level attributes
    ds.StudyInstanceUID = generate_uid()
    ds.StudyDate = '20250301'
    ds.StudyTime = '205901'
    ds.StudyDescription = 'Test Study'
    ds.PatientName = 'Test^Patient'
    ds.PatientID = '123456'
    
    # Series level attributes
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = '1'
    ds.SeriesDescription = 'Test Series'
    ds.Modality = 'CT'
    
    # Instance level attributes
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.InstanceNumber = '1'
    
    # Image attributes
    ds.Rows = 64
    ds.Columns = 64
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = np.random.randint(0, 65535, (64, 64), dtype=np.uint16).tobytes()
    
    # Create a temporary file to store the dataset
    temp_file = '/tmp/dicom_test_data/test.dcm'
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)
    ds.save_as(temp_file, write_like_original=False)
    
    yield {
        "client": client,
        "test_dir": test_dir,
        "dicom_file": temp_file,
        "dataset": ds
    }
    
    # Cleanup
    shutil.rmtree(test_dir)
    shutil.rmtree(os.path.dirname(temp_file))

def test_store_instance(test_env):
    """Test storing a DICOM instance."""
    client = test_env["client"]
    
    with open(test_env["dicom_file"], "rb") as f:
        dicom_data = f.read()
    
    response = client.post("/instances", files={"file": ("test.dcm", dicom_data)})
    assert response.status_code == 200
    uids = response.json()
    
    # Verify UIDs match the dataset
    assert uids["study_uid"] == test_env["dataset"].StudyInstanceUID
    assert uids["series_uid"] == test_env["dataset"].SeriesInstanceUID
    assert uids["instance_uid"] == test_env["dataset"].SOPInstanceUID
    
    return uids

def test_study_level_operations(test_env):
    """Test study level operations."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Test study query
    response = client.get("/studies")
    assert response.status_code == 200
    studies = response.json()
    assert len(studies) > 0
    
    # Test study metadata
    response = client.get(f"/studies/{uids['study_uid']}/metadata")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata.get('00100020', {}).get('Value', [''])[0] == '123456'  # PatientID
    
    # Test study thumbnail
    response = client.get(f"/studies/{uids['study_uid']}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    
    # Verify thumbnail dimensions
    img_buffer = io.BytesIO(response.content)
    img = Image.open(img_buffer)
    assert img.size[0] > 0 and img.size[1] > 0

def test_series_level_operations(test_env):
    """Test series level operations."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Test series query
    response = client.get(f"/studies/{uids['study_uid']}/series")
    assert response.status_code == 200
    series = response.json()
    assert len(series) > 0
    
    # Test series metadata
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/metadata"
    )
    assert response.status_code == 200
    metadata = response.json()
    assert metadata.get('00200011', {}).get('Value', [''])[0] == '1'  # SeriesNumber
    
    # Test series thumbnail
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/thumbnail"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

def test_instance_level_operations(test_env):
    """Test instance level operations."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Test instances query
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances"
    )
    assert response.status_code == 200
    instances = response.json()
    assert len(instances) > 0
    
    # Test instance metadata
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/metadata"
    )
    assert response.status_code == 200
    metadata = response.json()
    assert metadata.get('00200013', {}).get('Value', [''])[0] == '1'  # InstanceNumber
    
    # Test instance thumbnail
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/thumbnail"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

def test_frame_operations(test_env):
    """Test frame operations."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Test frame retrieval
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/frames/1"
    )
    assert response.status_code == 200
    frame_data = response.content
    assert len(frame_data) == 64 * 64 * 2  # 16-bit pixels
    
    # Test rendered frame
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/rendered"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    
    # Verify rendered image dimensions
    img_buffer = io.BytesIO(response.content)
    img = Image.open(img_buffer)
    assert img.size == (64, 64)

def test_file_structure(test_env):
    """Test the generated file structure."""
    uids = test_store_instance(test_env)
    test_dir = test_env["test_dir"]
    
    # Check study level files
    study_dir = os.path.join(test_dir, "studies", uids["study_uid"])
    assert os.path.exists(os.path.join(study_dir, "index.json.gz"))
    assert os.path.exists(os.path.join(study_dir, "thumbnail.jpg"))
    assert os.path.exists(os.path.join(study_dir, "bulkdata"))
    
    # Check series level files
    series_dir = os.path.join(study_dir, "series", uids["series_uid"])
    assert os.path.exists(os.path.join(series_dir, "index.json.gz"))
    assert os.path.exists(os.path.join(series_dir, "metadata.json.gz"))
    assert os.path.exists(os.path.join(series_dir, "thumbnail.jpg"))
    
    # Check instance level files
    instance_dir = os.path.join(series_dir, "instances", uids["instance_uid"])
    assert os.path.exists(os.path.join(instance_dir, "metadata.json.gz"))
    assert os.path.exists(os.path.join(instance_dir, "thumbnail.jpg"))
    assert os.path.exists(os.path.join(instance_dir, "frames", "1.gz"))
    assert os.path.exists(os.path.join(instance_dir, "rendered", "0.png"))

def test_error_handling(test_env):
    """Test error handling."""
    client = test_env["client"]
    
    # Test invalid study UID
    response = client.get("/studies/invalid_uid")
    assert response.status_code == 404
    
    # Test invalid series UID
    response = client.get("/studies/1.2.3/series/invalid_uid")
    assert response.status_code == 404
    
    # Test invalid instance UID
    response = client.get("/studies/1.2.3/series/4.5.6/instances/invalid_uid")
    assert response.status_code == 404
    
    # Test invalid frame number
    uids = test_store_instance(test_env)
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/frames/999"
    )
    assert response.status_code == 404

def test_invalid_dicom_data(test_env):
    """Test handling of invalid DICOM data."""
    client = test_env["client"]
    
    # Test empty file
    response = client.post("/instances", files={"file": ("empty.dcm", io.BytesIO(b""))})
    assert response.status_code == 400
    assert "Invalid DICOM data" in response.json()["detail"]
    
    # Test non-DICOM file
    response = client.post("/instances", files={"file": ("test.txt", io.BytesIO(b"Not a DICOM file"))})
    assert response.status_code == 400
    assert "Invalid DICOM data" in response.json()["detail"]
    
    # Test missing required attributes
    ds = FileDataset("missing_attrs.dcm", Dataset(), file_meta=Dataset())
    buffer = io.BytesIO()
    ds.save_as(buffer)
    response = client.post("/instances", files={"file": ("missing_attrs.dcm", buffer.getvalue())})
    assert response.status_code == 400
    assert "Missing required DICOM attributes" in response.json()["detail"]

def test_bulk_data(test_env):
    """Test bulk data handling."""
    client = test_env["client"]
    
    # Create a DICOM dataset with bulk data
    ds = test_env["dataset"]
    ds.WaveformData = b"\x00" * 1000  # Add some bulk data
    ds.save_as(test_env["dicom_file"], write_like_original=False)
    
    with open(test_env["dicom_file"], "rb") as f:
        dicom_data = f.read()
    response = client.post("/instances", files={"file": ("test.dcm", dicom_data)})
    assert response.status_code == 200
    uids = response.json()
    
    # Check bulk data directory exists
    bulk_dir = os.path.join(test_env["test_dir"], "studies", uids["study_uid"], "bulkdata")
    assert os.path.exists(bulk_dir)
    
    # Check bulk data files are created
    bulk_files = os.listdir(bulk_dir)
    assert len(bulk_files) > 0
    
    # Verify bulk data file content
    bulk_file = os.path.join(bulk_dir, bulk_files[0])
    assert os.path.getsize(bulk_file) > 0

def test_rendered_frame(test_env):
    """Test rendered frame quality."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Get rendered frame
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/rendered"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    
    # Verify image quality
    img_buffer = io.BytesIO(response.content)
    img = Image.open(img_buffer)
    assert img.mode in ["L", "RGB", "I;16"]
    assert img.size == (64, 64)  # Should match original dimensions
    
    # Check pixel values are reasonable
    img_array = np.array(img)
    assert img_array.min() >= 0
    assert img_array.max() <= 65535  # 16-bit image

def test_series_index(test_env):
    """Test series-level index operations."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Check series index file exists
    series_dir = os.path.join(
        test_env["test_dir"], "studies", uids["study_uid"], "series", uids["series_uid"]
    )
    index_file = os.path.join(series_dir, "index.json.gz")
    assert os.path.exists(index_file)
    
    # Verify index content
    import gzip
    with gzip.open(index_file, "rt") as f:
        index = json.load(f)
    assert isinstance(index, dict)
    assert "series" in index
    assert "uid" in index["series"]
    assert "number" in index["series"]



def test_rendered_frame(test_env):
    """Test rendered frame quality."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Get rendered frame
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/rendered"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    
    # Verify image quality
    img_buffer = io.BytesIO(response.content)
    img = Image.open(img_buffer)
    assert img.mode in ["L", "RGB", "I;16"]  # Allow 16-bit grayscale
    assert img.size == (64, 64)  # Should match original dimensions
    
    # Check pixel values are reasonable
    img_array = np.array(img)
    assert img_array.min() >= 0
    assert img_array.max() <= 65535  # 16-bit image

def test_series_index(test_env):
    """Test series-level index operations."""
    client = test_env["client"]
    uids = test_store_instance(test_env)
    
    # Check series index file exists
    series_dir = os.path.join(
        test_env["test_dir"], "studies", uids["study_uid"], "series", uids["series_uid"]
    )
    index_file = os.path.join(series_dir, "index.json.gz")
    assert os.path.exists(index_file)
    
    # Verify index content
    with gzip.open(index_file, "rt") as f:
        index = json.load(f)
    assert isinstance(index, dict)
    assert index.get("00200011", {}).get("Value", ["0"])[0] == "1"  # SeriesNumber
    assert index.get("0020000E", {}).get("Value", [""])[0] == uids["series_uid"]  # SeriesInstanceUID
