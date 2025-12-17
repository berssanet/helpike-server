"""
converter.py - FFmpeg wrapper for AV1 media conversion with NVIDIA GPU acceleration.

Uses:
- NVDEC for hardware-accelerated decoding
- libsvtav1 for high-quality AV1 encoding (software, but highly optimized)
- libaom-av1 for AVIF image encoding
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FFmpeg quality presets
# Lower CRF = better quality, larger file
# SVT-AV1 CRF range: 0-63 (default 35)
VIDEO_CRF = 30  # Good balance of quality and compression
VIDEO_PRESET = 6  # 0=slowest/best, 13=fastest/worst

# AVIF/AV1 image settings
IMAGE_CRF = 20  # Higher quality for still images


def get_media_type(file_path: str) -> str:
    """Determine if file is video or image based on extension."""
    ext = Path(file_path).suffix.lower()
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'}
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.bmp', '.tiff'}
    
    if ext in video_extensions:
        return "video"
    elif ext in image_extensions:
        return "image"
    else:
        # Default to video for unknown types
        return "video"


def convert_video(input_path: str, output_path: str) -> Tuple[bool, str]:
    """
    Convert video to AV1 using SVT-AV1 encoder with CUDA-accelerated decoding.
    
    Args:
        input_path: Path to input video file
        output_path: Path for output AV1 video (should be .mp4)
    
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        # FFmpeg command with:
        # - CUDA hardware decoding (if available, falls back to software)
        # - SVT-AV1 encoding (best open-source AV1 encoder)
        # - Opus audio for better compression
        # - faststart for streaming compatibility
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-hwaccel', 'cuda',  # Use NVIDIA GPU for decoding
            '-hwaccel_output_format', 'cuda',
            '-i', input_path,
            '-c:v', 'libsvtav1',
            '-preset', str(VIDEO_PRESET),
            '-crf', str(VIDEO_CRF),
            '-pix_fmt', 'yuv420p',  # Maximum compatibility
            '-c:a', 'libopus',
            '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]
        
        logger.info(f"Running video conversion: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode != 0:
            # Try fallback without CUDA if GPU decode fails
            logger.warning("CUDA decode failed, trying software decode...")
            cmd_fallback = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-c:v', 'libsvtav1',
                '-preset', str(VIDEO_PRESET),
                '-crf', str(VIDEO_CRF),
                '-pix_fmt', 'yuv420p',
                '-c:a', 'libopus',
                '-b:a', '128k',
                '-movflags', '+faststart',
                output_path
            ]
            
            result = subprocess.run(
                cmd_fallback,
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            if result.returncode != 0:
                return False, result.stderr
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "Conversion timeout exceeded (1 hour)"
    except Exception as e:
        return False, str(e)


def convert_image(input_path: str, output_path: str) -> Tuple[bool, str]:
    """
    Convert image to AVIF format using libaom-av1.
    
    Args:
        input_path: Path to input image file
        output_path: Path for output AVIF image
    
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        # FFmpeg command for AVIF encoding
        cmd = [
            'ffmpeg',
            '-y',
            '-i', input_path,
            '-c:v', 'libaom-av1',
            '-crf', str(IMAGE_CRF),
            '-still-picture', '1',  # Optimize for still images
            '-pix_fmt', 'yuv420p',
            output_path
        ]
        
        logger.info(f"Running image conversion: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for images
        )
        
        if result.returncode != 0:
            return False, result.stderr
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "Image conversion timeout exceeded (5 minutes)"
    except Exception as e:
        return False, str(e)


def convert_media(input_path: str, output_dir: str) -> Tuple[bool, str, str]:
    """
    Convert media file (video or image) to AV1/AVIF format.
    
    Args:
        input_path: Path to input media file
        output_dir: Directory for output file
    
    Returns:
        Tuple of (success: bool, output_path: str, error_message: str)
    """
    media_type = get_media_type(input_path)
    input_name = Path(input_path).stem
    
    if media_type == "video":
        output_path = os.path.join(output_dir, f"{input_name}_av1.mp4")
        success, error = convert_video(input_path, output_path)
    else:
        output_path = os.path.join(output_dir, f"{input_name}.avif")
        success, error = convert_image(input_path, output_path)
    
    if success:
        return True, output_path, ""
    else:
        return False, "", error
