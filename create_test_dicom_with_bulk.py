"""Create a test DICOM file with bulk data."""
import os
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import generate_uid
import datetime

# Create output directory
output_dir = "/tmp/dicom_test_data_with_bulk"
os.makedirs(output_dir, exist_ok=True)

# Create a new file meta dataset
file_meta = FileMetaDataset()
file_meta.FileMetaInformationGroupLength = 200
file_meta.FileMetaInformationVersion = b'\x00\x01'
file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'  # CT Image Storage
file_meta.MediaStorageSOPInstanceUID = generate_uid()
file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'  # Explicit VR Little Endian
file_meta.ImplementationClassUID = '1.2.3.4.5.6.7'
file_meta.ImplementationVersionName = 'PYDICOM'

# Create the dataset
ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)

# Add required elements
ds.StudyInstanceUID = generate_uid()
ds.SeriesInstanceUID = generate_uid()
ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
ds.PatientName = "Test^Patient"
ds.PatientID = "123456"
ds.PatientBirthDate = "19700101"
ds.PatientSex = "O"
ds.StudyDate = datetime.date.today().strftime('%Y%m%d')
ds.StudyTime = datetime.datetime.now().strftime('%H%M%S')
ds.AccessionNumber = ""
ds.Modality = "CT"
ds.SeriesNumber = "1"
ds.StudyDescription = "Test Study with Bulk Data"
ds.SeriesDescription = "Test Series with Bulk Data"
ds.InstanceNumber = "1"

# Image specific attributes
ds.SamplesPerPixel = 1
ds.PhotometricInterpretation = "MONOCHROME2"
ds.Rows = 64
ds.Columns = 64
ds.BitsAllocated = 16
ds.BitsStored = 16
ds.HighBit = 15
ds.PixelRepresentation = 0

# Create a simple image
pixel_array = np.zeros((64, 64), dtype=np.uint16)
pixel_array[32, 32] = 65535  # Set center pixel to max value
ds.PixelData = pixel_array.tobytes()

# Add bulk data elements
# 1. Encapsulated Document
document_data = b'This is a test document for bulk data testing.'
ds.add_new([0x0042, 0x0011], 'OB', document_data)  # Encapsulated Document

# 2. Private Data Element
private_data = np.random.bytes(1000)
ds.add_new([0x0009, 0x0010], 'LO', 'Test Creator')  # Private Creator
ds.add_new([0x0009, 0x1001], 'OB', private_data)  # Private Data

# 3. Waveform Data
waveform_data = np.sin(np.linspace(0, 2*np.pi, 1000)).astype(np.float32).tobytes()
ds.add_new([0x5400, 0x1010], 'OW', waveform_data)  # Waveform Data

# Save the file
output_file = os.path.join(output_dir, "test_with_bulk.dcm")
ds.save_as(output_file)

print(f"Created test DICOM file with bulk data at: {output_file}")
print(f"Study UID: {ds.StudyInstanceUID}")
print(f"Series UID: {ds.SeriesInstanceUID}")
print(f"Instance UID: {ds.SOPInstanceUID}")

# Copy to test_data directory
test_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data", "bulk_test")
os.makedirs(test_data_dir, exist_ok=True)
test_data_file = os.path.join(test_data_dir, "test_with_bulk.dcm")

import shutil
shutil.copy(output_file, test_data_file)
print(f"Copied test file to: {test_data_file}")
