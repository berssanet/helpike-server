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
    """Convert image to AVIF format using optimized avifenc-style preset.
    
    Based on: avifenc --min 0 --max 15 -y 420 -a end-usage=q -a sharpness=0 -a aq-mode=2 -s 2 -j 8 -d 10
    
    This preset provides excellent compression (~60-80% reduction) while maintaining
    high visual quality through careful quantizer settings and adaptive quantization.
    """
    try:
        avif_output = output_path.replace('.jpg', '.avif').replace('.jpeg', '.avif')
        
        # Limit max resolution to reduce file size further
        MAX_DIMENSION = "2000"
        
        # ============================================
        # PRIMARY: libaom-av1 with avifenc-style preset
        # ============================================
        # Translating avifenc parameters to FFmpeg/libaom:
        # --min 0 --max 15 -> -qmin 0 -qmax 15 (quantizer range)
        # -a end-usage=q   -> -b:v 0 (CQ mode)
        # -a sharpness=0   -> -sharpness 0
        # -a aq-mode=2     -> -aq-mode 2 (adaptive quantization)
        # -s 2             -> -cpu-used 2 (slower = better)
        # -d 10            -> -pix_fmt yuv420p10le (10-bit)
        # -j 8             -> -row-mt 1 -tiles 2x2
        
        cmd = [
            '/usr/local/bin/ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
            '-c:v', 'libaom-av1',
            '-b:v', '0',              # CQ mode (end-usage=q)
            '-qmin', '0',             # min quantizer
            '-qmax', '15',            # max quantizer (lower = higher quality)
            '-pix_fmt', 'yuv420p10le', # 10-bit depth
            '-cpu-used', '2',         # Speed 2 (slower = better compression)
            '-row-mt', '1',           # Row-based multithreading
            '-tiles', '2x2',          # Parallel tile encoding
            '-aq-mode', '2',          # Adaptive quantization mode 2
            '-sharpness', '0',        # No extra sharpening
            '-aom-params', 'enable-chroma-deltaq=1:deltaq-mode=3',  # Better color handling
            '-frames:v', '1',
            avif_output
        ]
        logger.info(f"libaom-av1 AVIF (avifenc preset, qmax 15): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.warning(f"libaom-av1 failed, trying NVENC: {result.stderr}")
            
            # Fallback to NVENC hardware encoder (faster but less control)
            cmd = [
                '/usr/local/bin/ffmpeg', '-y',
                '-i', input_path,
                '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
                '-c:v', 'av1_nvenc',
                '-preset', 'p6',      # p6 = high quality
                '-cq', '25',          # Conservative quality for fallback
                '-pix_fmt', 'yuv420p',
                '-frames:v', '1',
                avif_output
            ]
            logger.info(f"NVENC fallback (CQ 25): {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                logger.warning(f"NVENC failed, falling back to JPEG: {result.stderr}")
                # Final fallback: compressed JPEG
                cmd = [
                    '/usr/local/bin/ffmpeg', '-y',
                    '-i', input_path,
                    '-vf', f'scale=min({MAX_DIMENSION}\\,iw):min({MAX_DIMENSION}\\,ih):force_original_aspect_ratio=decrease',
                    '-q:v', '10',
                    output_path
                ]
                logger.info(f"JPEG fallback (q:v 10): {' '.join(cmd)}")
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

