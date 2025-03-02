"""DICOM file handling and conversion to DICOMWeb format."""
import os
import io
import json
import gzip
from pathlib import Path
from typing import Dict, Any, List, Union
import pydicom
from pydicom.dataset import Dataset
from pydicom.filebase import DicomBytesIO
from PIL import Image
import numpy as np


class DicomHandler:
    """Handles DICOM file operations and conversions following Static DICOMWeb file structure."""
    
    def __init__(self, root_dir: Union[str, Path]):
        """Initialize handler with root directory.
        
        Args:
            root_dir: Base directory for storing DICOMWeb files
        """
        self.root_dir = Path(str(root_dir))  # Ensure string conversion
        self.studies_dir = self.root_dir / "studies"
        self.deduplicated_dir = self.root_dir / "deduplicated"
        self.instances_dir = self.root_dir / "instances"
        self.notifications_dir = self.root_dir / "notifications"
        
        # Create all required directories
        for directory in [self.studies_dir, self.deduplicated_dir, 
                        self.instances_dir, self.notifications_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create studies index if it doesn't exist
        studies_index = self.studies_dir / "index.json.gz"
        if not studies_index.exists():
            with gzip.open(studies_index, 'wt', compresslevel=9) as f:
                json.dump([], f)
    
    def _get_study_path(self, study_uid: str) -> Path:
        """Get path for study directory."""
        return self.studies_dir / study_uid
    
    def _get_series_path(self, study_uid: str, series_uid: str) -> Path:
        """Get path for series directory."""
        return self._get_study_path(study_uid) / "series" / series_uid
    
    def _get_instance_path(self, study_uid: str, series_uid: str, instance_uid: str) -> Path:
        """Get path for instance directory."""
        return self._get_series_path(study_uid, series_uid) / "instances" / instance_uid
    
    def _get_frame_path(self, study_uid: str, series_uid: str, instance_uid: str, frame_number: int) -> Path:
        """Get path for frame file."""
        return self._get_instance_path(study_uid, series_uid, instance_uid) / "frames" / f"{frame_number}.gz"
    
    def _get_thumbnail_path(self, study_uid: str, series_uid: str = None, instance_uid: str = None) -> Path:
        """Get path for thumbnail file."""
        if instance_uid:
            return self._get_instance_path(study_uid, series_uid, instance_uid) / "thumbnail.jpg"
        elif series_uid:
            return self._get_series_path(study_uid, series_uid) / "thumbnail.jpg"
        else:
            return self._get_study_path(study_uid) / "thumbnail.jpg"
    
    def _generate_thumbnail(self, pixel_array: np.ndarray, study_uid: str, 
                          series_uid: str = None, instance_uid: str = None) -> None:
        """Generate and save thumbnail for an image.
        
        Args:
            pixel_array: Image data as numpy array
            study_uid: Study instance UID
            series_uid: Optional series instance UID
            instance_uid: Optional instance UID
        """
        try:
            # Handle complex array shapes
            # If it's a 3D+ array, take a middle slice
            if pixel_array.ndim > 2:
                # For 3D arrays, take the middle slice
                if pixel_array.ndim == 3:
                    if pixel_array.shape[2] == 3:  # RGB image
                        middle_slice = pixel_array
                    else:  # Multiple slices
                        middle_slice = pixel_array[:, :, pixel_array.shape[2]//2]
                # For 4D arrays (like multi-frame color images)
                elif pixel_array.ndim == 4:
                    middle_slice = pixel_array[pixel_array.shape[0]//2, :, :, 0]
                else:
                    # Default to a simple gray image for complex arrays
                    middle_slice = np.ones((64, 64), dtype=np.uint8) * 128
            else:
                middle_slice = pixel_array
            
            # Normalize pixel values to 0-255 range
            if middle_slice.max() != middle_slice.min():  # Avoid division by zero
                normalized = ((middle_slice - middle_slice.min()) * 255 / 
                             (middle_slice.max() - middle_slice.min())).astype(np.uint8)
            else:
                normalized = np.zeros_like(middle_slice, dtype=np.uint8)
            
            # Create thumbnail
            image = Image.fromarray(normalized)
            image.thumbnail((128, 128))  # Resize to thumbnail size
        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            # Create a default gray thumbnail
            default_array = np.ones((64, 64), dtype=np.uint8) * 128
            image = Image.fromarray(default_array)
            image.thumbnail((128, 128))
        
        # Save thumbnail
        thumbnail_path = self._get_thumbnail_path(study_uid, series_uid, instance_uid)
        
        # Ensure parent directory exists
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to RGB and save
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(thumbnail_path, format='JPEG', quality=85)
    
    def _update_studies_index(self, study_uid: str, metadata: Dict[str, Any]) -> None:
        """Update the studies index with new study information.
        
        Args:
            study_uid: Study instance UID
            metadata: Study metadata
        """
        # Create the study directory if it doesn't exist
        study_path = self._get_study_path(study_uid)
        study_path.mkdir(parents=True, exist_ok=True)
        
        # Create or update the study index file
        index_path = study_path / "index.json.gz"
        
        # If the index file exists, read it and update
        if index_path.exists():
            with gzip.open(index_path, "rt") as f:
                study_metadata = json.load(f)
                # Update with new metadata
                study_metadata.update(metadata)
        else:
            # Create new metadata
            study_metadata = metadata.copy()
            # Add the study UID
            study_metadata["0020000D"] = {"vr": "UI", "Value": [study_uid]}
        
        # Write the updated index file
        with gzip.open(index_path, "wt", compresslevel=9) as f:
            json.dump(study_metadata, f)
    
    def store_dicom(self, dicom_data: bytes) -> Dict[str, str]:
        """Store DICOM data in DICOMWeb format.
        
        Args:
            dicom_data: Raw DICOM file data
            
        Returns:
            Dict with study, series, and instance UIDs
            
        Raises:
            ValueError: If DICOM data is invalid
        """
        try:
            dataset = pydicom.dcmread(DicomBytesIO(dicom_data), force=True)
            if not hasattr(dataset, 'StudyInstanceUID') or not hasattr(dataset, 'SeriesInstanceUID') or not hasattr(dataset, 'SOPInstanceUID'):
                raise ValueError("Missing required DICOM attributes: StudyInstanceUID, SeriesInstanceUID, or SOPInstanceUID")
            study_uid = str(dataset.StudyInstanceUID)
            series_uid = str(dataset.SeriesInstanceUID)
            instance_uid = str(dataset.SOPInstanceUID)
        except Exception as e:
            raise ValueError(f"Invalid DICOM data: {str(e)}")
        
        # Create directories
        instance_path = self._get_instance_path(study_uid, series_uid, instance_uid)
        instance_path.mkdir(parents=True, exist_ok=True)
        
        # Store instance metadata
        metadata = self._extract_metadata(dataset)
        instance_metadata_path = instance_path / "metadata.json.gz"
        with gzip.open(instance_metadata_path, "wt", compresslevel=9) as f:
            json.dump(metadata, f)
        
        # Store pixel data
        if hasattr(dataset, "PixelData"):
            pixel_data_path = instance_path / "pixel_data.raw"
            pixel_data_path.write_bytes(dataset.PixelData)
            
            # Create frames directory
            frames_dir = instance_path / "frames"
            frames_dir.mkdir(exist_ok=True)
            
            # Try to get the pixel array from the dataset
            try:
                pixel_array = dataset.pixel_array
                
                # Generate thumbnails
                self._generate_thumbnail(pixel_array, study_uid)
                self._generate_thumbnail(pixel_array, study_uid, series_uid)
                self._generate_thumbnail(pixel_array, study_uid, series_uid, instance_uid)
                
                # Store frame data (for single-frame images, just store the entire pixel data as frame 1)
                frame_path = frames_dir / "1.gz"
                with gzip.open(frame_path, "wb") as f:
                    np.save(f, pixel_array)
                    
                # Create rendered directory
                rendered_dir = instance_path / "rendered"
                rendered_dir.mkdir(exist_ok=True)
                
                # Create rendered frame
                try:
                    # Handle complex array shapes
                    if pixel_array.ndim > 2:
                        # For 3D arrays, take the middle slice
                        if pixel_array.ndim == 3:
                            if pixel_array.shape[2] == 3:  # RGB image
                                middle_slice = pixel_array
                            else:  # Multiple slices
                                middle_slice = pixel_array[:, :, pixel_array.shape[2]//2]
                        # For 4D arrays (like multi-frame color images)
                        elif pixel_array.ndim == 4:
                            middle_slice = pixel_array[pixel_array.shape[0]//2, :, :, 0]
                        else:
                            # Default to a simple gray image for complex arrays
                            middle_slice = np.ones((64, 64), dtype=np.uint8) * 128
                    else:
                        middle_slice = pixel_array
                    
                    # Normalize the slice
                    normalized = ((middle_slice - middle_slice.min()) * (255.0 / (middle_slice.max() - middle_slice.min() + 1e-10))).astype(np.uint8)
                    
                    # Save as PNG
                    from PIL import Image
                    img = Image.fromarray(normalized)
                    img.save(str(rendered_dir / "0.png"))
                except Exception as e:
                    print(f"Error creating rendered frame: {e}")
                    # Create a default gray image
                    default_array = np.ones((64, 64), dtype=np.uint8) * 128
                    from PIL import Image
                    img = Image.fromarray(default_array)
                    img.save(str(rendered_dir / "0.png"))
                    
            except Exception as e:
                # If we can't get the pixel array, create default thumbnails and frames
                print(f"Warning: Could not process pixel data for {instance_uid}: {e}")
                
                # Create default thumbnails
                default_array = np.ones((64, 64), dtype=np.uint8) * 128  # Gray image
                self._generate_thumbnail(default_array, study_uid)
                self._generate_thumbnail(default_array, study_uid, series_uid)
                self._generate_thumbnail(default_array, study_uid, series_uid, instance_uid)
                
                # Create a default frame
                frame_path = frames_dir / "1.gz"
                with gzip.open(frame_path, "wb") as f:
                    np.save(f, default_array)
                    
                # Create a default rendered frame
                rendered_dir = instance_path / "rendered"
                rendered_dir.mkdir(exist_ok=True)
                from PIL import Image
                img = Image.fromarray(default_array)
                img.save(str(rendered_dir / "0.png"))
                

        
        # Extract and store bulk data
        bulk_data_dir = self._get_study_path(study_uid) / "bulkdata"
        bulk_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate study thumbnail if it doesn't exist
        study_thumbnail_path = self._get_study_path(study_uid) / "thumbnail.jpg"
        if not study_thumbnail_path.exists() and hasattr(dataset, "PixelData"):
            self._generate_thumbnail(dataset.pixel_array, study_uid)
        
        # Check for bulk data elements (other than PixelData)
        bulk_data_elements = [attr for attr in dir(dataset) if attr.endswith('Data') and attr != 'PixelData' and hasattr(dataset, attr)]
        
        for attr in bulk_data_elements:
            data = getattr(dataset, attr)
            if isinstance(data, bytes) and len(data) > 0:
                bulk_data_path = bulk_data_dir / f"{instance_uid}_{attr}.bin"
                bulk_data_path.write_bytes(data)
        
        # Create notification for eventual consistency
        notification_path = self.notifications_dir / f"{study_uid}_{series_uid}_{instance_uid}.json"
        with open(notification_path, "w") as f:
            json.dump({"status": "pending"}, f)
        
        # Update studies index
        study_metadata = {
            "00080020": {"Value": [str(getattr(dataset, "StudyDate", ""))]},
            "00081030": {"Value": [str(getattr(dataset, "StudyDescription", ""))]}
        }
        self._update_studies_index(study_uid, study_metadata)
        
        # Create series index file
        series_path = self._get_series_path(study_uid, series_uid)
        series_path.mkdir(parents=True, exist_ok=True)
        
        # Create series index file
        series_index_path = series_path / "index.json.gz"
        series_metadata = {
            "00200011": {"Value": [str(getattr(dataset, "SeriesNumber", "1"))]},
            "0008103E": {"Value": [str(getattr(dataset, "SeriesDescription", ""))]},
            "0020000E": {"Value": [series_uid]},
            "00080060": {"Value": [str(getattr(dataset, "Modality", ""))]}
        }
        with gzip.open(series_index_path, "wt", compresslevel=9) as f:
            json.dump(series_metadata, f)
            
        # Create series metadata file
        series_metadata_path = series_path / "metadata.json.gz"
        with gzip.open(series_metadata_path, "wt", compresslevel=9) as f:
            json.dump(metadata, f)
        
        return {
            "study_uid": study_uid,
            "series_uid": series_uid,
            "instance_uid": instance_uid
        }
    
    def _extract_metadata(self, dataset: Dataset) -> Dict[str, Any]:
        """Extract metadata from DICOM dataset in DICOMWeb JSON format.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Dict containing metadata in DICOMWeb JSON format
        """
        def get_attr(ds, attr, default=""):
            return str(getattr(ds, attr, default))
            
        def get_int_attr(ds, attr, default=0):
            return int(getattr(ds, attr, default))
            
        # Convert DICOM attributes to DICOMWeb format
        metadata = {
            "00080020": {"vr": "DA", "Value": [get_attr(dataset, "StudyDate")]},
            "00080030": {"vr": "TM", "Value": [get_attr(dataset, "StudyTime")]},
            "00081030": {"vr": "LO", "Value": [get_attr(dataset, "StudyDescription")]},
            "0020000D": {"vr": "UI", "Value": [get_attr(dataset, "StudyInstanceUID")]},
            "00100010": {"vr": "PN", "Value": [get_attr(dataset, "PatientName")]},
            "00100020": {"vr": "LO", "Value": [get_attr(dataset, "PatientID")]},
            "00200011": {"vr": "IS", "Value": [get_attr(dataset, "SeriesNumber")]},
            "0008103E": {"vr": "LO", "Value": [get_attr(dataset, "SeriesDescription")]},
            "0020000E": {"vr": "UI", "Value": [get_attr(dataset, "SeriesInstanceUID")]},
            "00200013": {"vr": "IS", "Value": [get_attr(dataset, "InstanceNumber")]},
            "00080016": {"vr": "UI", "Value": [get_attr(dataset, "SOPClassUID")]},
            "00080018": {"vr": "UI", "Value": [get_attr(dataset, "SOPInstanceUID")]},
            "00280010": {"vr": "US", "Value": [get_int_attr(dataset, "Rows")]},
            "00280011": {"vr": "US", "Value": [get_int_attr(dataset, "Columns")]},
            "00280004": {"vr": "CS", "Value": [get_attr(dataset, "PhotometricInterpretation")]},
            "00280100": {"vr": "US", "Value": [get_int_attr(dataset, "BitsAllocated")]},
            "00280101": {"vr": "US", "Value": [get_int_attr(dataset, "BitsStored")]},
            "00280102": {"vr": "US", "Value": [get_int_attr(dataset, "HighBit")]},
            "00280103": {"vr": "US", "Value": [get_int_attr(dataset, "PixelRepresentation")]},
            "00080060": {"vr": "CS", "Value": [get_attr(dataset, "Modality")]},
            "00200010": {"vr": "SH", "Value": [get_attr(dataset, "StudyID")]},
            "00080050": {"vr": "SH", "Value": [get_attr(dataset, "AccessionNumber")]},
            "00100040": {"vr": "CS", "Value": [get_attr(dataset, "PatientSex")]},
            "00100030": {"vr": "DA", "Value": [get_attr(dataset, "PatientBirthDate")]},
            "00100021": {"vr": "LO", "Value": [get_attr(dataset, "IssuerOfPatientID")]}
        }
        
        return metadata
    
    def get_studies(self) -> List[str]:
        """Get list of available study UIDs.
        
        Returns:
            List of study UIDs
        """
        # Check for studies in the studies directory
        return [d.name for d in self.studies_dir.iterdir() if d.is_dir()]
    
    def get_series(self, study_uid: str) -> List[str]:
        """Get list of series UIDs for a study.
        
        Args:
            study_uid: Study instance UID
            
        Returns:
            List of series UIDs
        """
        study_path = self._get_study_path(study_uid)
        if not study_path.exists():
            return []
            
        series_path = study_path / "series"
        if not series_path.exists():
            return []
            
        return [d.name for d in series_path.iterdir() if d.is_dir()]
    
    def get_instances(self, study_uid: str, series_uid: str) -> List[str]:
        """Get list of instance UIDs for a series.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            
        Returns:
            List of instance UIDs
        """
        series_path = self._get_series_path(study_uid, series_uid)
        if not series_path.exists():
            return []
            
        instances_path = series_path / "instances"
        if not instances_path.exists():
            return []
            
        return [d.name for d in instances_path.iterdir() if d.is_dir()]
    
    def get_series_metadata(self, study_uid: str, series_uid: str) -> Dict[str, Any]:
        """Get metadata for a series.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            
        Returns:
            Dict containing series metadata
            
        Raises:
            FileNotFoundError: If metadata not found
        """
        # Get instances for this series
        instance_list = self.get_instances(study_uid, series_uid)
        if not instance_list:
            raise FileNotFoundError(f"No instances found for series {series_uid}")
            
        # Get metadata from the first instance
        return self.get_metadata(study_uid, series_uid, instance_list[0])
    
    def get_metadata(self, study_uid: str, series_uid: str, instance_uid: str) -> Dict[str, Any]:
        """Get metadata for an instance.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            instance_uid: SOP instance UID
            
        Returns:
            Dict containing study, series, instance, and image metadata
            
        Raises:
            FileNotFoundError: If metadata not found
        """
        metadata_path = self._get_instance_path(study_uid, series_uid, instance_uid) / "metadata.json.gz"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found for instance {instance_uid}")
        
        with gzip.open(metadata_path, 'rt') as f:
            dicom_metadata = json.load(f)
            
        # Add study, series, and instance UIDs
        dicom_metadata.update({
            "0020000D": {"vr": "UI", "Value": [study_uid]},
            "0020000E": {"vr": "UI", "Value": [series_uid]},
            "00080018": {"vr": "UI", "Value": [instance_uid]}
        })
        return dicom_metadata
    
    def get_frame_data(self, study_uid: str, series_uid: str, instance_uid: str, frame_number: int = 1) -> bytes:
        """Get frame data for an instance.

        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            instance_uid: SOP instance UID
            frame_number: Frame number (1-based)

        Returns:
            Frame data as bytes

        Raises:
            FileNotFoundError: If frame data not found
        """
        frame_path = self._get_frame_path(study_uid, series_uid, instance_uid, frame_number)
        
        if not frame_path.exists():
            raise FileNotFoundError(f"Frame {frame_number} not found")
        
        with gzip.open(frame_path, 'rb') as f:
            frame_data = np.load(f)
            return frame_data.astype(np.uint16).tobytes()
            
    def get_pixel_data(self, study_uid: str, series_uid: str, instance_uid: str) -> bytes:
        """Get pixel data for an instance.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            instance_uid: SOP instance UID
            
        Returns:
            Pixel data as bytes
            
        Raises:
            FileNotFoundError: If pixel data not found
        """
        instance_path = self._get_instance_path(study_uid, series_uid, instance_uid)
        pixel_data_path = instance_path / "pixel_data.raw"
        
        if not pixel_data_path.exists():
            raise FileNotFoundError(f"Pixel data not found for instance {instance_uid}")
            
        return pixel_data_path.read_bytes()
    
    def get_series_metadata(self, study_uid: str, series_uid: str) -> Dict[str, Any]:
        """Get metadata for a series.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            
        Returns:
            Dict containing metadata
            
        Raises:
            FileNotFoundError: If metadata not found
        """
        metadata_path = self._get_series_path(study_uid, series_uid) / "metadata.json.gz"
        if not metadata_path.exists():
            raise FileNotFoundError("Series metadata not found")
            
        with gzip.open(metadata_path, "rt") as f:
            return json.load(f)
    
    def get_thumbnail(self, study_uid: str, series_uid: str = None, instance_uid: str = None) -> bytes:
        """Get thumbnail for study, series, or instance.

        Args:
            study_uid: Study instance UID
            series_uid: Optional series instance UID
            instance_uid: Optional SOP instance UID

        Returns:
            Thumbnail image data as bytes

        Raises:
            FileNotFoundError: If thumbnail not found
        """
        thumbnail_path = self._get_thumbnail_path(study_uid, series_uid, instance_uid)
        
        if not thumbnail_path.exists():
            raise FileNotFoundError("Thumbnail not found")
        
        # Create a BytesIO object to store the image data
        img_buffer = io.BytesIO()
        
        # Open the image, convert to RGB if needed, and save to buffer
        with Image.open(thumbnail_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(img_buffer, format='JPEG')
        
        # Get the image data as bytes
        img_buffer.seek(0)
        return img_buffer.read()