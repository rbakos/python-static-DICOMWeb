"""Test DICOMWeb server with real DICOM data from OHIF viewer-testdata."""
import os
import glob
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from static_dicomweb.web_server import app, init_server_with_config
from static_dicomweb.config import Config
from static_dicomweb.dicom_handler import DicomHandler

TEST_DIR = "/tmp/dicomweb_real_test"
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


@pytest.fixture(scope="module")
def test_env():
    """Set up test environment."""
    # Clean up test directory if it exists
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)
    
    # Initialize server with test config
    config = Config(
        staticWadoConfig={"rootDir": TEST_DIR},
        dicomWebServerConfig={"rootDir": TEST_DIR},
        dicomWebScpConfig={"rootDir": TEST_DIR},
        aeConfig={}
    )
    init_server_with_config(config=config)
    
    # Create test client
    client = TestClient(app)
    
    yield {
        "client": client,
        "test_dir": TEST_DIR,
        "test_data_dir": TEST_DATA_DIR
    }
    
    # Cleanup
    shutil.rmtree(TEST_DIR)


def test_store_real_dicom_files(test_env):
    """Test storing real DICOM files from the test data repository."""
    client = test_env["client"]
    
    # Find DICOM files in the test data directory
    # Look in the dcm folder which contains DICOM files
    dicom_files = glob.glob(str(TEST_DATA_DIR / "dcm" / "**" / "*.dcm"), recursive=True)
    
    # Limit to 10 files for faster testing
    dicom_files = dicom_files[:10]
    
    assert len(dicom_files) > 0, "No DICOM files found in test data"
    
    # Store each DICOM file
    stored_uids = []
    for dicom_file in dicom_files:
        with open(dicom_file, "rb") as f:
            dicom_data = f.read()
        
        response = client.post("/instances", files={"file": (os.path.basename(dicom_file), dicom_data)})
        if response.status_code != 200:
            print(f"Error storing file {dicom_file}: {response.status_code} - {response.text}")
            # Try to parse the DICOM file to see if it's valid
            try:
                import pydicom
                ds = pydicom.dcmread(dicom_file)
                print(f"DICOM file info: {ds.SOPClassUID} - {ds.Modality if hasattr(ds, 'Modality') else 'No modality'}")
            except Exception as e:
                print(f"Error parsing DICOM file: {e}")
        assert response.status_code == 200
        uids = response.json()
        stored_uids.append(uids)
        
        # Verify study, series, and instance directories were created
        study_dir = os.path.join(TEST_DIR, "studies", uids["study_uid"])
        series_dir = os.path.join(study_dir, "series", uids["series_uid"])
        instance_dir = os.path.join(series_dir, "instances", uids["instance_uid"])
        
        assert os.path.exists(study_dir)
        assert os.path.exists(series_dir)
        assert os.path.exists(instance_dir)
        assert os.path.exists(os.path.join(instance_dir, "metadata.json.gz"))
    
    # Test retrieving studies
    response = client.get("/studies")
    assert response.status_code == 200
    studies = response.json()
    assert len(studies) > 0
    
    # Test retrieving series for the first study
    study_uid = stored_uids[0]["study_uid"]
    response = client.get(f"/studies/{study_uid}/series")
    assert response.status_code == 200
    series = response.json()
    assert len(series) > 0
    
    # Test retrieving instances for the first series
    series_uid = stored_uids[0]["series_uid"]
    response = client.get(f"/studies/{study_uid}/series/{series_uid}/instances")
    assert response.status_code == 200
    instances = response.json()
    assert len(instances) > 0
    
    # Test retrieving metadata for the first instance
    instance_uid = stored_uids[0]["instance_uid"]
    response = client.get(f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata")
    assert response.status_code == 200
    metadata = response.json()
    assert "00080016" in metadata  # SOP Class UID
    assert "00080018" in metadata  # SOP Instance UID
    
    # Get metadata to check if this is a document-type DICOM
    response = client.get(f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata")
    assert response.status_code == 200
    metadata = response.json()
    
    # Only test rendered frame for non-document DICOM files
    if metadata.get('00080060', {}).get('Value', [''])[0] != 'DOC':
        # Test retrieving rendered frame
        response = client.get(f"/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/rendered")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    else:
        print(f"Skipping rendered frame test for document-type DICOM file")


def test_bulk_data_with_real_files(test_env):
    """Test bulk data handling with real DICOM files."""
    client = test_env["client"]
    
    # Find DICOM files that might contain bulk data
    dicom_files = glob.glob(str(TEST_DATA_DIR / "**" / "*.dcm"), recursive=True)
    
    # Limit to 20 files for faster testing
    dicom_files = dicom_files[:20]
    
    assert len(dicom_files) > 0, "No DICOM files found in test data"
    
    # Store each DICOM file and check for bulk data
    for dicom_file in dicom_files:
        with open(dicom_file, "rb") as f:
            dicom_data = f.read()
        
        response = client.post("/instances", files={"file": (os.path.basename(dicom_file), dicom_data)})
        if response.status_code != 200:
            print(f"Error storing file {dicom_file}: {response.status_code} - {response.text}")
            # Try to parse the DICOM file to see if it's valid
            try:
                import pydicom
                ds = pydicom.dcmread(dicom_file)
                print(f"DICOM file info: {ds.SOPClassUID} - {ds.Modality if hasattr(ds, 'Modality') else 'No modality'}")
            except Exception as e:
                print(f"Error parsing DICOM file: {e}")
        assert response.status_code == 200
        uids = response.json()
        
        # Check if bulk data directory exists and has content
        bulk_dir = os.path.join(TEST_DIR, "studies", uids["study_uid"], "bulkdata")
        if os.path.exists(bulk_dir) and len(os.listdir(bulk_dir)) > 0:
            # If we found bulk data, test the bulk data endpoint
            response = client.get(f"/studies/{uids['study_uid']}/bulkdata")
            assert response.status_code == 200
            bulk_data_list = response.json()
            assert isinstance(bulk_data_list, list)
            
            # Test successful case
            print(f"Found bulk data in file: {dicom_file}")
            return
    
    # If no bulk data was found, skip the test
    pytest.skip("No bulk data found in test files")
