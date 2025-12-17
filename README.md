# Helpike Backend - AV1 Media Converter

Backend service for high-efficiency AV1 video and image compression using NVIDIA GPU acceleration.

## Quick Start

### Local Development (without GPU)

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app:app --host 0.0.0.0 --port 5001 --reload
```

### Docker (with NVIDIA GPU)

```bash
# Build and run
docker compose up --build

# Or run in background
docker compose up -d --build
```

## API Endpoints

### Upload Media
```bash
curl -X POST -F "media=@video.mp4" http://localhost:5001/upload
# Response: {"job_id": "uuid-string"}
```

### Check Status
```bash
curl http://localhost:5001/status/{job_id}
# Response: {"status": "processando", "original_size_bytes": 1234567, "converted_size_bytes": 0}
```

### Download Converted File
```bash
curl -O http://localhost:5001/download/{job_id}
```

## Requirements

- Python 3.10+
- FFmpeg with libsvtav1 and libaom-av1 support
- NVIDIA GPU with CUDA (optional, for hardware-accelerated decoding)

## AWS Deployment

For AWS EC2 with NVIDIA L4 GPU:

1. Use an AMI with NVIDIA drivers pre-installed (e.g., Deep Learning AMI)
2. Install Docker and NVIDIA Container Toolkit
3. Clone this repository
4. Run `docker compose up -d --build`

```bash
# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```
