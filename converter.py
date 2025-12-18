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
    """Convert image to AVIF format using NVIDIA NVENC hardware acceleration.
    
    Uses av1_nvenc (GPU) as primary encoder for maximum speed.
    Falls back to libaom-av1 (software) only if GPU encoding fails.
    
    NVENC CQ scale: 0=lossless, 51=max compression
    - CQ 18-22: High quality, good compression (~60-70% reduction)
    - CQ 25-30: Balanced quality/size (~70-80% reduction)
    """
    try:
        avif_output = output_path.replace('.jpg', '.avif').replace('.jpeg', '.avif')
        
        # Limit max resolution to reduce file size
        MAX_DIMENSION = "2000"
        
        # ============================================
        # PRIMARY: av1_nvenc (GPU hardware acceleration)
        # ============================================
        # Using CQ 20 for high quality with excellent compression
        # p6 preset = slower encoding but better compression/quality
        
        cmd = [
            '/usr/local/bin/ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
            '-c:v', 'av1_nvenc',
            '-preset', 'p6',          # p6 = high quality (slower)
            '-cq', '20',              # CQ 20 = high quality, ~60-70% compression
            '-pix_fmt', 'yuv420p',
            '-frames:v', '1',
            avif_output
        ]
        logger.info(f"NVENC av1 AVIF (CQ 20, preset p6): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            logger.warning(f"NVENC failed, trying libaom-av1: {result.stderr}")
            
            # Fallback to software encoder (libaom-av1) with avifenc-style preset
            cmd = [
                '/usr/local/bin/ffmpeg', '-y',
                '-i', input_path,
                '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
                '-c:v', 'libaom-av1',
                '-b:v', '0',
                '-qmin', '0',
                '-qmax', '20',
                '-pix_fmt', 'yuv420p10le',
                '-cpu-used', '4',     # Faster for fallback
                '-row-mt', '1',
                '-tiles', '2x2',
                '-aq-mode', '2',
                '-frames:v', '1',
                avif_output
            ]
            logger.info(f"libaom-av1 fallback (qmax 20): {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.warning(f"libaom-av1 failed, falling back to JPEG: {result.stderr}")
                # Final fallback: compressed JPEG
                cmd = [
                    '/usr/local/bin/ffmpeg', '-y',
                    '-i', input_path,
                    '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
                    '-q:v', '8',
                    output_path
                ]
                logger.info(f"JPEG fallback (q:v 8): {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    return False, result.stderr
                return True, ""
        
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

