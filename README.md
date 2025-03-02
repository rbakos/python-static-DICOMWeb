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
