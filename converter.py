"""
converter.py - FFmpeg wrapper for AV1 media conversion with NVIDIA NVENC hardware acceleration.

Uses:
- av1_nvenc for hardware-accelerated AV1 encoding (NVIDIA L4 Ada Lovelace)
- Fixed bitrate mode to ensure smaller output files
- JPEG output for images
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Video bitrate (adjust as needed)
# 2M = ~900MB/hour, 3M = ~1.3GB/hour, 4M = ~1.8GB/hour
VIDEO_BITRATE = "2M"
VIDEO_PRESET = "p4"  # p1 (fastest) to p7 (slowest/best)


def get_media_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'}
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.bmp', '.tiff'}
    if ext in video_extensions:
        return "video"
    elif ext in image_extensions:
        return "image"
    return "video"


def convert_video(input_path: str, output_path: str) -> Tuple[bool, str]:
    """Convert video to AV1 using NVIDIA NVENC hardware encoder with fixed bitrate."""
    try:
        # av1_nvenc with fixed bitrate for guaranteed compression
        cmd = [
            '/usr/local/bin/ffmpeg', '-y',
            '-i', input_path,
            '-pix_fmt', 'yuv420p',  # Required for av1_nvenc
            '-c:v', 'av1_nvenc', '-preset', VIDEO_PRESET,
            '-b:v', VIDEO_BITRATE,  # Fixed bitrate
            '-maxrate', VIDEO_BITRATE,  # Cap max rate
            '-bufsize', '4M',  # Buffer size
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart', output_path
        ]
        logger.info(f"Running NVENC AV1: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, result.stderr
        return True, ""
    except Exception as e:
        return False, str(e)


def convert_image(input_path: str, output_path: str) -> Tuple[bool, str]:
    """Convert image to AVIF format for superior compression (40-60% smaller than JPEG).
    
    Uses libaom-av1 encoder with CRF mode for quality/size balance.
    CRF values: 0 = lossless, 23 = good quality, 35 = smaller file, 63 = max compression
    """
    try:
        # First try AVIF conversion (best compression)
        avif_output = output_path.replace('.jpg', '.avif').replace('.jpeg', '.avif')
        
        # CRF 32 = good balance of quality/size (adjust 28-40 as needed)
        # Lower = better quality but larger file
        # Higher = smaller file but lower quality
        IMAGE_CRF = "32"
        
        cmd = [
            '/usr/local/bin/ffmpeg', '-y',
            '-i', input_path,
            '-c:v', 'libaom-av1',
            '-crf', IMAGE_CRF,
            '-b:v', '0',  # Required for CRF mode
            '-pix_fmt', 'yuv420p',
            '-cpu-used', '4',  # Speed: 0=slowest/best, 8=fastest
            '-row-mt', '1',  # Enable row-based multithreading
            '-tiles', '2x2',  # Parallel tile encoding
            avif_output
        ]
        logger.info(f"AVIF conversion (CRF {IMAGE_CRF}): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            logger.warning(f"AVIF failed, falling back to JPEG: {result.stderr}")
            # Fallback to highly compressed JPEG
            # -q:v scale: 1=best quality, 31=worst quality
            # Using 8-12 for good compression with acceptable quality
            cmd = ['/usr/local/bin/ffmpeg', '-y', '-i', input_path, '-q:v', '10', output_path]
            logger.info(f"JPEG fallback: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                return False, result.stderr
            return True, ""
            
        # AVIF succeeded - update output path
        return True, ""
    except Exception as e:
        return False, str(e)


def convert_media(input_path: str, output_dir: str) -> Tuple[bool, str, str]:
    media_type = get_media_type(input_path)
    input_name = Path(input_path).stem
    if media_type == "video":
        output_path = os.path.join(output_dir, f"{input_name}_av1.mp4")
        success, error = convert_video(input_path, output_path)
    else:
        # Use AVIF for images (superior compression)
        output_path = os.path.join(output_dir, f"{input_name}_compressed.avif")
        success, error = convert_image(input_path, output_path)
        # If AVIF failed, check for JPEG fallback
        if not success:
            jpg_path = os.path.join(output_dir, f"{input_name}_compressed.jpg")
            if os.path.exists(jpg_path):
                output_path = jpg_path
                success = True
                error = ""
    return (True, output_path, "") if success else (False, "", error)

