"""
converter.py - FFmpeg wrapper for HEVC media conversion with NVIDIA NVENC hardware acceleration.

Uses:
- hevc_nvenc for hardware-accelerated HEVC encoding (NVIDIA L4 Ada Lovelace)
- HEVC is native to iOS since iPhone 7, ensuring Photo Library compatibility
- Fixed bitrate mode to ensure smaller output files
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
    """Convert video to HEVC (H.265) using NVIDIA NVENC for iOS Photo Library compatibility.
    
    HEVC is native to iOS since iPhone 7, ensuring the video can be saved directly
    to the Photo Library without format issues.
    """
    try:
        # hevc_nvenc with fixed bitrate for guaranteed compression + iOS compatibility
        cmd = [
            '/usr/local/bin/ffmpeg', '-y',
            '-i', input_path,
            '-pix_fmt', 'yuv420p',
            '-c:v', 'hevc_nvenc', '-preset', VIDEO_PRESET,
            '-b:v', VIDEO_BITRATE,     # Fixed bitrate
            '-maxrate', VIDEO_BITRATE, # Cap max rate
            '-bufsize', '4M',          # Buffer size
            '-tag:v', 'hvc1',          # Required for iOS compatibility
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart', output_path
        ]
        logger.info(f"Running HEVC NVENC (iOS compatible): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, result.stderr
        return True, ""
    except Exception as e:
        return False, str(e)


def convert_image(input_path: str, output_path: str) -> Tuple[bool, str]:
    """Convert image to HEIC format using NVIDIA NVENC hardware acceleration.
    
    Uses hevc_nvenc (GPU) as primary encoder - HEIC is native to iOS since iPhone 7.
    Falls back to libx265 (software) if GPU encoding fails.
    
    HEIC provides excellent compression (~50-70% smaller than JPEG) with 
    full iOS compatibility for Photo Library saving.
    
    CRF scale for HEVC: 0=lossless, 51=worst
    - CRF 18-22: High quality, good compression
    - CRF 23-28: Balanced quality/size (default: 23)
    """
    try:
        # Output as HEIC (iOS native format)
        heic_output = output_path.replace('.jpg', '.heic').replace('.jpeg', '.heic').replace('.avif', '.heic')
        
        # Limit max resolution to reduce file size
        MAX_DIMENSION = "2000"
        
        # ============================================
        # PRIMARY: hevc_nvenc (GPU hardware acceleration)
        # ============================================
        # HEIC = HEVC codec in HEIF container
        # Using CQ 23 for balanced quality/compression
        
        cmd = [
            '/usr/local/bin/ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
            '-c:v', 'hevc_nvenc',
            '-preset', 'p6',          # p6 = high quality
            '-cq', '23',              # CQ 23 = balanced quality/compression
            '-pix_fmt', 'yuv420p',
            '-tag:v', 'hvc1',         # Required for iOS compatibility
            '-frames:v', '1',
            heic_output
        ]
        logger.info(f"HEVC NVENC (CQ 23, iOS compatible): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            logger.warning(f"hevc_nvenc failed, trying libx265: {result.stderr}")
            
            # Fallback to software encoder (libx265)
            cmd = [
                '/usr/local/bin/ffmpeg', '-y',
                '-i', input_path,
                '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
                '-c:v', 'libx265',
                '-crf', '23',
                '-preset', 'medium',
                '-pix_fmt', 'yuv420p',
                '-tag:v', 'hvc1',         # Required for iOS compatibility
                '-frames:v', '1',
                heic_output
            ]
            logger.info(f"libx265 fallback (CRF 23): {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.warning(f"libx265 failed, falling back to JPEG: {result.stderr}")
                # Final fallback: compressed JPEG (always works)
                cmd = [
                    '/usr/local/bin/ffmpeg', '-y',
                    '-i', input_path,
                    '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
                    '-q:v', '5',  # High quality JPEG
                    output_path
                ]
                logger.info(f"JPEG fallback (q:v 5): {' '.join(cmd)}")
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
        output_path = os.path.join(output_dir, f"{input_name}_hevc.mp4")
        success, error = convert_video(input_path, output_path)
    else:
        # Use HEIC for images (iOS native format, excellent compression)
        output_path = os.path.join(output_dir, f"{input_name}_compressed.heic")
        success, error = convert_image(input_path, output_path)
        # If HEIC failed, check for JPEG fallback
        if not success:
            jpg_path = os.path.join(output_dir, f"{input_name}_compressed.jpg")
            if os.path.exists(jpg_path):
                output_path = jpg_path
                success = True
                error = ""
    return (True, output_path, "") if success else (False, "", error)

