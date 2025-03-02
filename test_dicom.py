"""Test script for DICOMWeb server with real DICOM files."""
import os
import uvicorn
from fastapi.testclient import TestClient
from static_dicomweb.web_server import app, init_server_with_config
from static_dicomweb.config import Config

def test_dicom_workflow():
    """Test complete workflow with real DICOM file."""
    # Setup test environment
    test_dir = "/tmp/dicomweb_test"
    os.makedirs(test_dir, exist_ok=True)
    
    # Initialize server with test config
    config = Config(
        staticWadoConfig={"rootDir": test_dir},
        dicomWebServerConfig={"rootDir": test_dir},
        dicomWebScpConfig={"rootDir": test_dir},
        aeConfig={}
    )
    init_server_with_config(config=config)  # Initialize with test config
    
    # Create test client
    client = TestClient(app)
    
    # Use real DICOM file from the test data submodule
    import glob
    from pathlib import Path
    
    # Find a DICOM file in the test data submodule
    test_data_dir = Path(__file__).parent / "test_data"
    dicom_files = glob.glob(str(test_data_dir / "dcm" / "**" / "*.dcm"), recursive=True)
    
    assert len(dicom_files) > 0, "No DICOM files found in test data"
    test_file = dicom_files[0]
    
    # Read the test DICOM file
    with open(test_file, "rb") as f:
        dicom_data = f.read()
    
    # Test store instance
    print("\nTesting store instance...")
    response = client.post("/instances", files={"file": ("test.dcm", dicom_data)})
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.content}")
    assert response.status_code == 200
    uids = response.json()
    print(f"Stored instance: {uids}")
    
    # Test get studies
    print("\nTesting get studies...")
    response = client.get("/studies")
    assert response.status_code == 200
    studies = response.json()
    print(f"Found studies: {studies}")
    
    # Test get series
    print("\nTesting get series...")
    response = client.get(f"/studies/{uids['study_uid']}/series")
    assert response.status_code == 200
    series = response.json()
    print(f"Found series: {series}")
    
    # Test get instances
    print("\nTesting get instances...")
    response = client.get(f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances")
    assert response.status_code == 200
    instances = response.json()
    print(f"Found instances: {instances}")
    
    # Test get metadata
    print("\nTesting get metadata...")
    response = client.get(
        f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/metadata"
    )
    assert response.status_code == 200
    metadata = response.json()
    print(f"Metadata: {metadata}")
    
    # Check if the instance has pixel data (not a document)
    if metadata.get('00080060', {}).get('Value', [''])[0] != 'DOC':
        # Test get frame
        print("\nTesting get frame...")
        response = client.get(
            f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/frames/1"
        )
        assert response.status_code == 200
        frame_data = response.content
        print(f"Frame data size: {len(frame_data)} bytes")
    else:
        print("\nSkipping frame test for document-type DICOM file")
    
    # Test get thumbnails only for non-document DICOM files
    if metadata.get('00080060', {}).get('Value', [''])[0] != 'DOC':
        print("\nTesting get thumbnails...")
        
        # Study thumbnail
        response = client.get(f"/studies/{uids['study_uid']}/thumbnail")
        assert response.status_code == 200
        study_thumbnail = response.content
        print(f"Study thumbnail size: {len(study_thumbnail)} bytes")
        
        # Series thumbnail
        response = client.get(f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/thumbnail")
        assert response.status_code == 200
        series_thumbnail = response.content
        print(f"Series thumbnail size: {len(series_thumbnail)} bytes")
        
        # Instance thumbnail
        response = client.get(
            f"/studies/{uids['study_uid']}/series/{uids['series_uid']}/instances/{uids['instance_uid']}/thumbnail"
        )
    else:
        print("\nSkipping thumbnail tests for document-type DICOM file")
        assert response.status_code == 200
        instance_thumbnail = response.content
        print(f"Instance thumbnail size: {len(instance_thumbnail)} bytes")
    
    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    test_dicom_workflow()
