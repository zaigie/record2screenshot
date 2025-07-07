import ffmpeg
import numpy as np
from PIL import Image
from pathlib import Path


def get_dimension(video_path: str) -> tuple[int, int]:
    """Get video dimensions"""
    probe = ffmpeg.probe(video_path)
    video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    return int(video_stream["width"]), int(video_stream["height"])


def get_video(video_path: str, pix_fmt="yuv444p", quiet=False) -> bytes:
    """Get raw video data"""
    stream = ffmpeg.input(video_path).output(
        "pipe:", format="rawvideo", pix_fmt=pix_fmt
    )
    buffer, _ = stream.run(capture_stdout=True, quiet=quiet)
    return buffer


def save_image(array: np.ndarray, file_path: str, max_height=65000, mode="YCbCr"):
    """Save image with support for ultra-high image chunking"""
    path_obj = Path(file_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    filename = path_obj.stem
    file_dir = path_obj.parent

    chunk_count = array.shape[0] // max_height + 1
    for i in range(chunk_count):
        chunk = array[i * max_height : (i + 1) * max_height]
        if chunk.size == 0:
            continue

        img = Image.fromarray(chunk, mode)
        suffix = "" if i == 0 else f"_{i}"
        img_path = file_dir / f"{filename}{suffix}.jpg"
        img.save(img_path)
