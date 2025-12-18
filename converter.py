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
    try:
        cmd = ['/usr/local/bin/ffmpeg', '-y', '-i', input_path, '-q:v', '2', output_path]
        logger.info(f"Image conversion: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return False, result.stderr
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
        output_path = os.path.join(output_dir, f"{input_name}_compressed.jpg")
        success, error = convert_image(input_path, output_path)
    return (True, output_path, "") if success else (False, "", error)
