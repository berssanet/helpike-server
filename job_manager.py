"""
job_manager.py - Thread-safe job state management for media conversion tasks.
"""

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class JobStatus(Enum):
    PENDING = "pendente"
    PROCESSING = "processando"
    COMPLETED = "concluido"
    ERROR = "erro"


@dataclass
class JobData:
    """Represents a single conversion job."""
    job_id: str
    status: JobStatus = JobStatus.PENDING
    original_path: str = ""
    converted_path: str = ""
    original_size_bytes: float = 0.0
    converted_size_bytes: float = 0.0
    error_message: str = ""


class JobManager:
    """Thread-safe manager for conversion jobs."""

    def __init__(self):
        self._jobs: Dict[str, JobData] = {}
        self._lock = threading.Lock()

    def create_job(self, original_path: str, original_size: float) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        job = JobData(
            job_id=job_id,
            original_path=original_path,
            original_size_bytes=original_size
        )
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job data by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = status

    def set_completed(self, job_id: str, converted_path: str, converted_size: float) -> None:
        """Mark job as completed with converted file info."""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = JobStatus.COMPLETED
                job.converted_path = converted_path
                job.converted_size_bytes = converted_size

    def set_error(self, job_id: str, error_message: str) -> None:
        """Mark job as failed with error message."""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = JobStatus.ERROR
                job.error_message = error_message


# Global singleton instance
job_manager = JobManager()
