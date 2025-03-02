# Static DICOMWeb (Python Implementation)

A Python implementation of the Static DICOMWeb project, designed to create a web-centric PACS system optimized for DICOMweb.

## Features

- Optimized serving of DICOMweb files for OHIF viewing
- Static file serving directly from disk
- Data compression to minimize storage
- Distributed, eventually consistent data model
- Cloud provider support (AWS)
- Enhanced metadata structures
  - Easier to parse/understand than DICOMweb metadata
  - Smaller footprint (up to 1/100th of original size)
  - Faster first image display
- Bulk data handling
  - Extraction and storage of non-pixel bulk data elements
  - RESTful endpoints for bulk data retrieval
  - Support for various DICOM VR types (OB, OW, OF, OD, UN)

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

The package provides several command-line tools:

1. `mkdicomweb` - Create DICOMweb static files
2. `dicomwebserver` - Serve DICOMweb files
3. `dicomwebscp` - DICOM SCP service

Configuration is handled through JSON5 files and command-line arguments.

### DICOMweb API Endpoints

The server provides the following DICOMweb endpoints:

#### WADO-RS
- `GET /studies/{study_uid}` - Retrieve study metadata
- `GET /studies/{study_uid}/series/{series_uid}` - Retrieve series metadata
- `GET /studies/{study_uid}/series/{series_uid}/instances/{instance_uid}` - Retrieve instance metadata
- `GET /studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_number}` - Retrieve frame data
- `GET /studies/{study_uid}/thumbnail` - Retrieve study thumbnail
- `GET /studies/{study_uid}/series/{series_uid}/thumbnail` - Retrieve series thumbnail
- `GET /studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/thumbnail` - Retrieve instance thumbnail

#### QIDO-RS
- `GET /studies` - Query for studies
- `GET /studies/{study_uid}/series` - Query for series in a study
- `GET /studies/{study_uid}/series/{series_uid}/instances` - Query for instances in a series

#### STOW-RS
- `POST /instances` - Store DICOM instances

#### Bulk Data
- `GET /studies/{study_uid}/bulkdata` - List all bulk data items for a study
- `GET /studies/{study_uid}/bulkdata/{instance_uid}/{data_type}` - Retrieve specific bulk data item

## Testing

### Test Data

This repository includes a git submodule that contains sample DICOM data from the [OHIF viewer-testdata](https://github.com/OHIF/viewer-testdata) repository. To initialize the submodule after cloning, run:

```bash
git submodule update --init --recursive
```

### Running Tests

Run the test suite:
```bash
pytest
```

To run tests with real DICOM data from the submodule:
```bash
pytest tests/test_with_real_data.py
```

## Configuration

Configuration uses JSON5 files with the following structure:
```json5
{
  "staticWadoConfig": {
    "rootDir": "/dicomweb"
  },
  "dicomWebServerConfig": {
    "proxyAe": "myProxyAe"
  },
  "aeConfig": {
    "myProxyAe": {
      "description": "A proxy AE to use",
      "host": "proxyAe.hospital.com",
      "port": 104
    }
  }
}
```

## License

Same as original project
