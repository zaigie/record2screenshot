import sqlite3
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


# Task status enumeration
class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Database manager for tasks
class TaskDatabase:
    def __init__(self, db_path: str = "data/tasks.db"):
        self.db_path = db_path
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self.init_database()

    def init_database(self):
        """Initialize database and create tasks table"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    file_name TEXT,
                    file_size_mb REAL
                )
            """
            )
            conn.commit()

    def create_task(self, task_info: dict) -> None:
        """Create a new task"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_id, status, created_at, completed_at, 
                                 result_path, error_message, file_name, file_size_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_info["task_id"],
                    task_info["status"],
                    task_info["created_at"],
                    task_info.get("completed_at"),
                    task_info.get("result_path"),
                    task_info.get("error_message"),
                    task_info.get("file_name"),
                    task_info.get("file_size_mb"),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get task by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_task(self, task_id: str, **kwargs) -> None:
        """Update task fields"""
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)

        if fields:
            values.append(task_id)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?", values
                )
                conn.commit()

    def delete_task(self, task_id: str) -> bool:
        """Delete task by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_tasks(self, page: int = 1, page_size: int = 20) -> tuple[List[dict], int]:
        """List tasks with pagination"""
        offset = (page - 1) * page_size

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get total count
            cursor = conn.execute("SELECT COUNT(*) as count FROM tasks")
            total_count = cursor.fetchone()["count"]

            # Get paginated results
            cursor = conn.execute(
                """
                SELECT task_id, status, created_at, completed_at, file_name, file_size_mb
                FROM tasks 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """,
                (page_size, offset),
            )

            tasks = [dict(row) for row in cursor.fetchall()]

        return tasks, total_count


# Task information model
class TaskInfo(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    file_name: Optional[str] = None
    file_size_mb: Optional[float] = None


# Convert parameters model
class ConvertParams(BaseModel):
    crop_top: float = 0.15
    crop_bottom: float = 0.15
    expect_offset: float = 0.3
    min_overlap: float = 0.15
    approx_diff: float = 1.0
    transpose: bool = False
    seam_width: int = 0
    verbose: bool = False


# Paginated response model
class PaginatedTasksResponse(BaseModel):
    tasks: List[dict]
    total_count: int
    page: int
    page_size: int
    total_pages: int
