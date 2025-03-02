"""Command-line interface for Static DICOMWeb tools."""
import os
import sys
import click
import uvicorn
from pathlib import Path
from .config import load_config
from .dicom_handler import DicomHandler
from . import web_server


@click.group()
def cli():
    """Static DICOMWeb tools."""
    pass


@cli.command()
@click.argument('dicom_file', type=click.Path(exists=True))
@click.option('-c', '--config', type=click.Path(exists=True),
              help='Path to configuration file')
def store(dicom_file, config):
    """Store a DICOM file in DICOMWeb format."""
    try:
        cfg = load_config(config)
        handler = DicomHandler(cfg.static_wado_config.root_dir)
        
        with open(dicom_file, 'rb') as f:
            dicom_data = f.read()
        
        try:
            # Try to read the DICOM file with pydicom first to validate it
            import pydicom
            pydicom.dcmread(dicom_file)
            
            result = handler.store_dicom(dicom_data)
            if result:
                click.echo(f"Successfully stored DICOM file:")
                click.echo(f"Study UID: {result['study_uid']}")
                click.echo(f"Series UID: {result['series_uid']}")
                click.echo(f"Instance UID: {result['instance_uid']}")
                return 0
            return 1
        except Exception as e:
            click.echo(f"Error processing DICOM file: {str(e)}")
            sys.exit(1)  # Explicitly exit with code 1
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)  # Explicitly exit with code 1


@cli.command()
@click.option('-h', '--host', default='127.0.0.1',
              help='Host to bind server to')
@click.option('-p', '--port', default=8000,
              help='Port to bind server to')
@click.option('-c', '--config', type=click.Path(exists=True),
              help='Path to configuration file')
def serve(host, port, config):
    """Start the DICOMWeb server."""
    try:
        if config:
            web_server.init_server_with_config(config)
        else:
            web_server.init_server_with_config()
        
        click.echo(f"Starting DICOMWeb server at http://{host}:{port}")
        uvicorn.run(web_server.app, host=host, port=port)
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        return 1


@cli.command()
@click.option('-c', '--config', type=click.Path(exists=True),
              help='Path to configuration file')
def list_studies(config):
    """List available studies."""
    try:
        cfg = load_config(config)
        handler = DicomHandler(cfg.static_wado_config.root_dir)
        
        studies = handler.get_studies()
        if not studies:
            click.echo("No studies found")
            return
        
        click.echo("Available studies:")
        for study_uid in studies:
            try:
                series_list = handler.get_series(study_uid)
                if series_list:
                    instance_list = handler.get_instances(study_uid, series_list[0])
                    if instance_list:
                        metadata = handler.get_metadata(
                            study_uid,
                            series_list[0],
                            instance_list[0]
                        )
                        click.echo(f"\nStudy UID: {study_uid}")
                        # Extract date from metadata - look for StudyDate tag (0008,0020)
                        study_date = metadata.get('00080020', {}).get('Value', [''])[0]
                        # Extract description from metadata - look for StudyDescription tag (0008,1030)
                        study_desc = metadata.get('00081030', {}).get('Value', [''])[0]
                        click.echo(f"Date: {study_date}")
                        click.echo(f"Description: {study_desc}")
                        click.echo(f"Number of series: {len(series_list)}")
            except (IndexError, FileNotFoundError):
                continue
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        return 1


if __name__ == '__main__':
    cli()
