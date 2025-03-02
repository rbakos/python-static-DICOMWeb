"""Create a test DICOM file."""
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import generate_uid
import datetime

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
ds.StudyDescription = "Test Study"
ds.SeriesDescription = "Test Series"
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

# Save the file
ds.save_as("/tmp/dicom_test_data/test.dcm")
