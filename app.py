"""
app.py - FastAPI backend for Helpike AV1 media conversion service.

Endpoints:
- POST /upload - Upload media file, returns job_id
- GET /status/{job_id} - Get conversion status and file sizes
- GET /download/{job_id} - Download converted file
"""

import os
import logging
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from job_manager import job_manager, JobStatus
from converter import convert_media

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directory configuration
UPLOAD_DIR = Path("uploads")
CONVERTED_DIR = Path("converted")
UPLOAD_DIR.mkdir(exist_ok=True)
CONVERTED_DIR.mkdir(exist_ok=True)

# FastAPI app
app = FastAPI(
    title="Helpike AV1 Converter",
    description="High-efficiency media compression service using AV1 codec",
    version="1.0.0"
)

# CORS configuration for iOS app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for mobile app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_conversion(job_id: str, input_path: str, use_av1: bool = False) -> None:
    """Background task to convert media file.
    
    Args:
        job_id: Unique job identifier
        input_path: Path to the uploaded file
        use_av1: If True, use AV1 codec (iOS 16+). If False, use HEVC (iOS < 16).
    """
    try:
        logger.info(f"Starting conversion for job {job_id} (encoder: {'AV1' if use_av1 else 'HEVC'})")
        job_manager.update_status(job_id, JobStatus.PROCESSING)
        
        success, output_path, error = convert_media(input_path, str(CONVERTED_DIR), use_av1)
        
        if success:
            converted_size = os.path.getsize(output_path)
            job_manager.set_completed(job_id, output_path, converted_size)
            logger.info(f"Conversion completed for job {job_id}: {output_path} ({converted_size} bytes)")
        else:
            job_manager.set_error(job_id, error)
            logger.error(f"Conversion failed for job {job_id}: {error}")
            
    except Exception as e:
        job_manager.set_error(job_id, str(e))
        logger.exception(f"Exception during conversion for job {job_id}")


@app.post("/upload")
async def upload_media(
    background_tasks: BackgroundTasks,
    media: UploadFile = File(...),
    ios_version: str = None
):
    """
    Upload a media file for HEVC/AV1 conversion.
    
    Accepts any video or image file via multipart form data.
    Returns a job_id to track conversion progress.
    
    Args:
        media: The media file to convert
        ios_version: Optional iOS version string (e.g., "17.0", "15.5")
                     iOS 16+ uses AV1 for better compression
                     iOS < 16 uses HEVC for compatibility
    """
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / media.filename
        content = await media.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        original_size = len(content)
        
        # Parse iOS version to determine encoder
        use_av1 = False
        if ios_version:
            try:
                major_version = int(ios_version.split('.')[0])
                use_av1 = major_version >= 16
                logger.info(f"iOS version: {ios_version} (major: {major_version}) -> {'AV1' if use_av1 else 'HEVC'}")
            except (ValueError, IndexError):
                logger.warning(f"Could not parse iOS version: {ios_version}, defaulting to HEVC")
        
        logger.info(f"Received upload: {media.filename} ({original_size} bytes), encoder: {'AV1' if use_av1 else 'HEVC'}")
        
        # Create job and start background conversion
        job_id = job_manager.create_job(str(file_path), original_size)
        background_tasks.add_task(process_conversion, job_id, str(file_path), use_av1)
        
        return {"job_id": job_id}
        
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Get the status of a conversion job.
    
    Returns:
    - status: "pendente", "processando", "concluido", or "erro"
    - original_size_bytes: Size of original file
    - converted_size_bytes: Size of converted file (when complete)
    """
    job = job_manager.get_job(job_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "status": job.status.value,
        "original_size_bytes": job.original_size_bytes,
        "converted_size_bytes": job.converted_size_bytes
    }


@app.get("/download/{job_id}")
async def download_media(job_id: str):
    """
    Download the converted media file.
    
    Only available after conversion is complete (status = "concluido").
    """
    job = job_manager.get_job(job_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Job not ready. Current status: {job.status.value}"
        )
    
    if not os.path.exists(job.converted_path):
        raise HTTPException(status_code=404, detail="Converted file not found")
    
    # Determine media type for response
    file_ext = Path(job.converted_path).suffix.lower()
    if file_ext == ".avif":
        media_type = "image/avif"
    else:
        media_type = "video/mp4"
    
    return FileResponse(
        path=job.converted_path,
        media_type=media_type,
        filename=Path(job.converted_path).name
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
