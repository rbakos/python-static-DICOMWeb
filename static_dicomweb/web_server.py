"""FastAPI-based DICOMWeb server."""
import gzip
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response, FileResponse
from .dicom_handler import DicomHandler
from .config import Config, load_config

app = FastAPI(title="Static DICOMWeb Server")


class DicomWebServer:
    """DICOMWeb server implementation."""
    
    def __init__(self, config: Config):
        """Initialize server with configuration."""
        self.config = config
        # Use the same directory for all components
        self.root_dir = config.dicom_web_server_config.root_dir
        self.handler = DicomHandler(self.root_dir)
    
    async def store_instance(self, dicom_data: bytes) -> Dict[str, str]:
        """Store a DICOM instance."""
        try:
            return self.handler.store_dicom(dicom_data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    async def get_studies(self) -> List[Dict[str, Any]]:
        """Get list of available studies."""
        studies = []
        for study_uid in self.handler.get_studies():
            try:
                # Get series for this study
                series_list = self.handler.get_series(study_uid)
                if series_list:
                    # Get metadata from the first instance of the first series
                    instance_list = self.handler.get_instances(study_uid, series_list[0])
                    if instance_list:
                        metadata = self.handler.get_metadata(study_uid, series_list[0], instance_list[0])
                        studies.append({
                            "uid": study_uid,
                            "date": metadata.get("00080020", {}).get("Value", [""])[0],
                            "description": metadata.get("00081030", {}).get("Value", [""])[0]
                        })
            except Exception:
                continue
        return studies
    
    async def get_series(self, study_uid: str) -> List[Dict[str, Any]]:
        """Get list of series in a study."""
        series_list = []
        for series_uid in self.handler.get_series(study_uid):
            try:
                # Get instances for this series
                instance_list = self.handler.get_instances(study_uid, series_uid)
                if instance_list:
                    # Get metadata from the first instance
                    metadata = self.handler.get_metadata(study_uid, series_uid, instance_list[0])
                    series_list.append({
                        "uid": series_uid,
                        "number": metadata.get("00200011", {}).get("Value", ["1"])[0],
                        "description": metadata.get("0008103E", {}).get("Value", [""])[0]
                    })
            except Exception:
                continue
        return series_list
    
    async def get_instances(self, study_uid: str, series_uid: str) -> List[Dict[str, Any]]:
        """Get list of instances in a series."""
        instance_list = []
        for instance_uid in self.handler.get_instances(study_uid, series_uid):
            try:
                metadata = self.handler.get_metadata(study_uid, series_uid, instance_uid)
                instance_list.append({
                    "uid": metadata["00080018"]["Value"][0],
                    "number": metadata["00200013"]["Value"][0]
                })
            except FileNotFoundError:
                continue
        return instance_list
    
    async def get_study_metadata(self, study_uid: str) -> Dict[str, Any]:
        """Get metadata for a study."""
        # Check if study exists
        series_list = self.handler.get_series(study_uid)
        if not series_list:
            raise HTTPException(status_code=404, detail="Study not found")
            
        # Get metadata from the first instance of the first series
        try:
            instance_list = self.handler.get_instances(study_uid, series_list[0])
            if not instance_list:
                raise HTTPException(status_code=404, detail="No instances found in study")
                
            # Return the metadata for the first instance
            return self.handler.get_metadata(study_uid, series_list[0], instance_list[0])
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Error retrieving study metadata: {str(e)}")

    async def get_metadata(self, study_uid: str, series_uid: str, instance_uid: str) -> Dict[str, Any]:
        """Get metadata for an instance."""
        try:
            metadata_path = self.handler._get_instance_path(study_uid, series_uid, instance_uid) / "metadata.json.gz"
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata not found for instance {instance_uid}")
            with gzip.open(metadata_path, 'rt') as f:
                return json.load(f)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Instance not found")
    
    async def get_frame_data(self, study_uid: str, series_uid: str, instance_uid: str, frame_number: int = 1) -> bytes:
        """Get frame data for an instance."""
        try:
            return self.handler.get_frame_data(study_uid, series_uid, instance_uid, frame_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Frame data not found")

    async def get_pixel_data(self, study_uid: str, series_uid: str, instance_uid: str) -> bytes:
        """Get pixel data for an instance."""
        try:
            return self.handler.get_pixel_data(study_uid, series_uid, instance_uid)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Pixel data not found")
    
    async def get_thumbnail(self, study_uid: str, series_uid: str = None, instance_uid: str = None) -> bytes:
        """Get thumbnail for study, series, or instance."""
        try:
            return self.handler.get_thumbnail(study_uid, series_uid, instance_uid)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Thumbnail not found")


# Initialize server with default config for testing
default_root = Path("/tmp/dicomweb")
default_root.mkdir(parents=True, exist_ok=True)
server = DicomWebServer(Config(
    staticWadoConfig={"rootDir": str(default_root)},
    dicomWebServerConfig={"rootDir": str(default_root)},
    dicomWebScpConfig={"rootDir": str(default_root)},
    aeConfig={}
))

def init_server_with_config(config_path=None, config=None):
    """Initialize server with configuration.
    
    Args:
        config_path: Optional path to config file
        config: Optional Config object
    """
    global server
    if config:
        server = DicomWebServer(config)
    else:
        server = DicomWebServer(load_config(config_path))

# Define routes
@app.post("/instances", response_model=Dict[str, str])
async def store_instance(file: UploadFile):
    """Store a DICOM instance."""
    dicom_data = await file.read()
    return await server.store_instance(dicom_data)

@app.get("/studies", response_model=List[Dict[str, Any]])
async def get_studies():
    """Get list of available studies."""
    return await server.get_studies()

@app.get("/studies/{study_uid}/series", response_model=List[Dict[str, Any]])
async def get_series(study_uid: str):
    """Get list of series in a study."""
    return await server.get_series(study_uid)

@app.get("/studies/{study_uid}/series/{series_uid}/instances", response_model=List[Dict[str, Any]])
async def get_instances(study_uid: str, series_uid: str):
    """Get list of instances in a series."""
    return await server.get_instances(study_uid, series_uid)

@app.get("/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata")
async def get_metadata(study_uid: str, series_uid: str, instance_uid: str):
    """Get metadata for an instance."""
    return await server.get_metadata(study_uid, series_uid, instance_uid)

@app.get("/studies/{study_uid}/metadata")
async def get_study_metadata(study_uid: str):
    """Get metadata for a study."""
    return await server.get_study_metadata(study_uid)

@app.get("/studies/{study_uid}/series/{series_uid}/metadata")
async def get_series_metadata(study_uid: str, series_uid: str):
    """Get metadata for a series."""
    try:
        # First check if series exists
        if series_uid not in server.handler.get_series(study_uid):
            raise HTTPException(status_code=404, detail="Series not found")
            
        # Get metadata from the first instance of the series
        instance_list = server.handler.get_instances(study_uid, series_uid)
        if not instance_list:
            raise HTTPException(status_code=404, detail="No instances found in series")
            
        # Return the metadata for the first instance
        return server.handler.get_metadata(study_uid, series_uid, instance_list[0])
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Series metadata not found: {str(e)}")

@app.get("/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_number}")
async def get_frame(study_uid: str, series_uid: str, instance_uid: str, frame_number: int):
    """Get frame data for an instance."""
    frame_data = await server.get_frame_data(study_uid, series_uid, instance_uid, frame_number)
    return Response(content=frame_data, media_type="application/octet-stream")

@app.get("/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/pixel-data")
async def get_pixel_data(study_uid: str, series_uid: str, instance_uid: str):
    """Get pixel data for an instance."""
    pixel_data = await server.get_pixel_data(study_uid, series_uid, instance_uid)
    return Response(content=pixel_data, media_type="application/octet-stream")

@app.get("/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/rendered")
async def get_rendered_instance(study_uid: str, series_uid: str, instance_uid: str):
    """Get rendered instance."""
    rendered_path = server.handler._get_instance_path(study_uid, series_uid, instance_uid) / "rendered" / "0.png"
    if not rendered_path.exists():
        raise HTTPException(status_code=404, detail="Rendered instance not found")
    return FileResponse(str(rendered_path), media_type="image/png")

@app.get("/studies/{study_uid}/thumbnail")
async def get_study_thumbnail(study_uid: str):
    """Get thumbnail for a study."""
    thumbnail = await server.get_thumbnail(study_uid)
    return Response(content=thumbnail, media_type="image/jpeg")

@app.get("/studies/{study_uid}/series/{series_uid}/thumbnail")
async def get_series_thumbnail(study_uid: str, series_uid: str):
    """Get thumbnail for a series."""
    thumbnail = await server.get_thumbnail(study_uid, series_uid)
    return Response(content=thumbnail, media_type="image/jpeg")

@app.get("/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/thumbnail")
async def get_instance_thumbnail(study_uid: str, series_uid: str, instance_uid: str):
    """Get thumbnail for an instance."""
    thumbnail = await server.get_thumbnail(study_uid, series_uid, instance_uid)
    return Response(content=thumbnail, media_type="image/jpeg")
