import os
import asyncio
import uuid
import math
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import tempfile
import shutil

from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException,
    BackgroundTasks,
    Form,
    Depends,
    Query,
)
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from convert import convert_video_to_image, ConvertConfig
from model import (
    TaskStatus,
    TaskDatabase,
    ConvertParams,
    PaginatedTasksResponse,
)

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", 2))

# Initialize database
db = TaskDatabase()

# Create FastAPI application
app = FastAPI(
    title="Record2Screenshot API",
    description="Asynchronously convert screen recording videos to long screenshots",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create output directory
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Process pool executor
executor = ProcessPoolExecutor(max_workers=MAX_CONCURRENCY)

# File size limit (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Supported video formats
SUPPORTED_VIDEO_TYPES = {
    "video/mp4",
    "video/avi",
    "video/mov",
    "video/mkv",
    "video/webm",
    "video/flv",
}


def validate_video_file(file: UploadFile) -> UploadFile:
    """Validate uploaded video file"""
    # Check if file exists
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please select a file to upload")

    # Check file type
    if not file.content_type or file.content_type not in SUPPORTED_VIDEO_TYPES:
        supported_formats = ", ".join(SUPPORTED_VIDEO_TYPES)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported formats: {supported_formats}",
        )

    return file


def process_video_sync(video_path: str, output_path: str, config_dict: dict) -> str:
    """Synchronous video processing function (runs in subprocess)"""
    config = ConvertConfig(**config_dict)
    return convert_video_to_image(video_path, output_path, config)


async def process_video_task(task_id: str, video_path: str, params: ConvertParams):
    """Asynchronous video processing task"""
    try:
        # Update task status
        db.update_task(task_id, status=TaskStatus.PROCESSING)

        # Prepare output path
        output_filename = f"{task_id}.jpg"
        output_path = OUTPUT_DIR / output_filename

        # Convert config to dict (for serialization to subprocess)
        config_dict = params.dict()

        # Execute video processing in process pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor, process_video_sync, video_path, str(output_path), config_dict
        )

        # Update task completion status
        db.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            completed_at=datetime.now().isoformat(),
            result_path=str(output_path),
        )

    except Exception as e:
        # Handle errors
        db.update_task(
            task_id,
            status=TaskStatus.FAILED,
            completed_at=datetime.now().isoformat(),
            error_message=str(e),
        )

    finally:
        # Clean up temporary video file
        try:
            Path(video_path).unlink()
        except:
            pass


@app.get("/")
async def root():
    """Root path"""
    return {"message": "Record2Screenshot API", "version": "1.0.0"}


@app.post(
    "/upload",
    summary="Upload video file",
    description="Upload screen recording video file, system will process asynchronously and generate long screenshot",
    response_description="Returns task ID for status query",
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(
        ...,
        description="Video file (Supported: MP4, AVI, MOV, MKV, WebM, FLV)",
        media_type="video/*",
    ),
    crop_top: float = Form(
        0.15,
        description="Top crop ratio (0.0-1.0), used to remove fixed header",
        ge=0.0,
        le=1.0,
    ),
    crop_bottom: float = Form(
        0.15,
        description="Bottom crop ratio (0.0-1.0), used to remove fixed footer",
        ge=0.0,
        le=1.0,
    ),
    expect_offset: float = Form(
        0.3,
        description="Expected scroll offset ratio (0.1-1.0), affects algorithm prediction accuracy",
        ge=0.1,
        le=1.0,
    ),
    min_overlap: float = Form(
        0.15,
        description="Minimum overlap ratio (0.1-0.5), ensures sufficient inter-frame overlap",
        ge=0.1,
        le=0.5,
    ),
    approx_diff: float = Form(
        1.0,
        description="Approximate difference threshold (0.1-5.0), controls matching precision",
        ge=0.1,
        le=5.0,
    ),
    transpose: bool = Form(
        False, description="Horizontal scrolling mode (default is vertical scrolling)"
    ),
    seam_width: int = Form(
        0, description="Debug seam line width (pixels), 0 means no display", ge=0, le=10
    ),
    verbose: bool = Form(
        False, description="Verbose output mode, displays processing information"
    ),
    validated_file: UploadFile = Depends(validate_video_file),
):
    """
    Upload video file and start asynchronous conversion task

    **Supported video formats:**
    - MP4 (Recommended)
    - AVI
    - MOV
    - MKV
    - WebM
    - FLV

    **Parameter descriptions:**
    - **crop_top/crop_bottom**: Crop ratio, used to remove fixed header/footer bars
    - **expect_offset**: Expected offset ratio, adjust according to scroll speed
    - **min_overlap**: Minimum overlap ratio, ensures inter-frame matching precision
    - **approx_diff**: Difference threshold, smaller values are more precise but take longer
    - **transpose**: Whether for horizontal scrolling (like left-right swiping web pages)
    """
    # Check file size
    file.file.seek(0, 2)  # Move to end of file
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large, maximum supported {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename).suffix
    ) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        temp_video_path = tmp_file.name

    # Create task information
    task_info = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "created_at": datetime.now().isoformat(),
        "file_name": file.filename,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
    }
    db.create_task(task_info)

    # Prepare conversion parameters
    params = ConvertParams(
        crop_top=crop_top,
        crop_bottom=crop_bottom,
        expect_offset=expect_offset,
        min_overlap=min_overlap,
        approx_diff=approx_diff,
        transpose=transpose,
        seam_width=seam_width,
        verbose=verbose,
    )

    # Add background task
    background_tasks.add_task(process_video_task, task_id, temp_video_path, params)

    return {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "message": "Task created, processing in progress",
        "file_name": file.filename,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
    }


@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Query task status

    Args:
        task_id: Task ID

    Returns:
        Task status information
    """
    task_info = db.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task_info["status"],
        "created_at": task_info["created_at"],
        "completed_at": task_info.get("completed_at"),
        "error_message": task_info.get("error_message"),
    }


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """
    Get processed result image

    Args:
        task_id: Task ID

    Returns:
        Processed image file
    """
    task_info = db.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_info["status"] != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed yet, current status: {task_info['status']}",
        )

    if not task_info.get("result_path") or not Path(task_info["result_path"]).exists():
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(
        task_info["result_path"],
        media_type="image/jpeg",
        filename=f"screenshot_{task_id}.jpg",
    )


@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """
    Delete task and related files

    Args:
        task_id: Task ID

    Returns:
        Deletion result
    """
    task_info = db.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete result file
    if task_info.get("result_path"):
        try:
            Path(task_info["result_path"]).unlink()
        except:
            pass

    # Delete task record
    db.delete_task(task_id)

    return {"message": f"Task {task_id} deleted"}


@app.get("/tasks", response_model=PaginatedTasksResponse)
async def list_tasks(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
):
    """
    List all tasks with pagination

    Args:
        page: Page number (starts from 1)
        page_size: Page size (1-100)

    Returns:
        Paginated task list
    """
    tasks_list, total_count = db.list_tasks(page=page, page_size=page_size)
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return PaginatedTasksResponse(
        tasks=tasks_list,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


if __name__ == "__main__":
    import uvicorn

    print("Starting Record2Screenshot API server...")
    print("API documentation: http://localhost:8000/docs")

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
