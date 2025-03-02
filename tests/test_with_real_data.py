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
    
    # Use our specific test file with bulk data
    bulk_test_file = TEST_DATA_DIR / "bulk_test" / "test_with_bulk.dcm"
    
    # Ensure the test file exists
    if not bulk_test_file.exists():
        # If it doesn't exist, try to create it
        try:
            import sys
            import subprocess
            script_path = Path(__file__).parent.parent / "create_test_dicom_with_bulk.py"
            subprocess.run([sys.executable, str(script_path)], check=True)
            assert bulk_test_file.exists(), "Failed to create test DICOM file with bulk data"
        except Exception as e:
            pytest.skip(f"Could not create test DICOM file with bulk data: {e}")
    
    # Read the test file
    with open(bulk_test_file, "rb") as f:
        dicom_data = f.read()
    
    # Store the DICOM file
    response = client.post("/instances", files={"file": ("test_with_bulk.dcm", dicom_data)})
    assert response.status_code == 200, f"Failed to store test DICOM file: {response.text}"
    uids = response.json()
    
    # Check if bulk data directory exists and has content
    bulk_dir = os.path.join(TEST_DIR, "studies", uids["study_uid"], "bulkdata")
    assert os.path.exists(bulk_dir), "Bulk data directory was not created"
    assert len(os.listdir(bulk_dir)) > 0, "No bulk data files were created"
    
    # Test the bulk data endpoint
    response = client.get(f"/studies/{uids['study_uid']}/bulkdata")
    assert response.status_code == 200, f"Bulk data endpoint failed: {response.text}"
    bulk_data_list = response.json()
    assert isinstance(bulk_data_list, list), "Bulk data response is not a list"
    assert len(bulk_data_list) > 0, "Bulk data list is empty"
    
    # Test retrieving a specific bulk data item
    bulk_item = bulk_data_list[0]
    response = client.get(f"/studies/{uids['study_uid']}/bulkdata/{bulk_item['uid']}/{bulk_item['type']}")
    assert response.status_code == 200, f"Failed to retrieve bulk data item: {response.text}"
    assert len(response.content) > 0, "Bulk data item is empty"
    
    print(f"Successfully tested bulk data with file: {bulk_test_file}")
