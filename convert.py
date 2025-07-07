import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from func.core import calc_overlaps, splice
from func.util import get_dimension, get_video, save_image


@dataclass
class ConvertConfig:
    """Convert configuration parameters"""

    crop_top: float = 0.15  # Top crop ratio
    crop_bottom: float = 0.15  # Bottom crop ratio
    expect_offset: float = 0.3  # Expected offset ratio
    min_overlap: float = 0.15  # Minimum overlap ratio
    approx_diff: float = 1.0  # Approximate difference threshold
    transpose: bool = False  # Horizontal scrolling mode
    seam_width: int = 0  # Debug seam line width
    verbose: bool = False  # Verbose output


def convert_video_to_image(
    src_path: str,
    output_path: Optional[str] = None,
    config: Optional[ConvertConfig] = None,
) -> str:
    """
    Convert screen recording video to long screenshot

    Args:
        src_path: Input video path
        output_path: Output image path, defaults to input filename
        config: Convert configuration, uses default if None

    Returns:
        Output file path
    """
    if config is None:
        config = ConvertConfig()

    # Get video dimensions
    w, h = get_dimension(src_path)
    if config.transpose:
        w, h = h, w

    # Convert relative values to absolute pixel values
    def to_pixels(value: float, dimension: int) -> int:
        return int(value * dimension) if value < 1 else int(value)

    crop_top = to_pixels(config.crop_top, h)
    crop_bottom = to_pixels(config.crop_bottom, h)
    expect_offset = to_pixels(config.expect_offset, h)
    min_overlap = to_pixels(config.min_overlap, h)

    # Read video data
    buffer = get_video(src_path, quiet=not config.verbose)

    # Reshape video array
    shape = [-1, 3, h, w] if not config.transpose else [-1, 3, w, h]
    video = np.frombuffer(buffer, np.uint8).reshape(shape)

    if config.transpose:
        video = video.transpose(0, 1, 3, 2)

    # Calculate inter-frame overlaps
    results = calc_overlaps(
        video,
        crop_top,
        crop_bottom,
        expect_offset,
        sample_cols=None,
        verbose=config.verbose,
        approx_diff=config.approx_diff,
        min_overlap=min_overlap,
    )

    # Splice long image
    panorama = splice(video, results, crop_top, crop_bottom, config.seam_width)

    if config.transpose:
        panorama = panorama.transpose(1, 0, 2)

    # Determine output path
    if output_path is None:
        output_path = Path(src_path).stem + ".jpg"

    # Save image
    save_image(panorama, output_path)

    if config.verbose:
        print(f"Conversion completed: {src_path} -> {output_path}")

    return output_path


def main():
    import click

    @click.command()
    @click.argument("src", type=click.Path(exists=True))
    @click.option("--crop-top", default=0.15, help="Top crop height ratio")
    @click.option("--crop-bottom", default=0.15, help="Bottom crop height ratio")
    @click.option("--expect-offset", default=0.3, help="Expected offset ratio")
    @click.option("-o", "--output", help="Output path")
    @click.option("-t", "--transpose", is_flag=True, help="Horizontal scrolling mode")
    @click.option("--seam-width", default=0, help="Debug seam line width")
    @click.option("-v", "--verbose", is_flag=True, help="Verbose output")
    @click.option("--min-overlap", default=0.15, help="Minimum overlap ratio")
    @click.option("--approx-diff", default=1.0, help="Approximate difference threshold")
    def cli(
        src,
        crop_top,
        crop_bottom,
        expect_offset,
        output,
        transpose,
        seam_width,
        verbose,
        min_overlap,
        approx_diff,
    ):
        config = ConvertConfig(
            crop_top=crop_top,
            crop_bottom=crop_bottom,
            expect_offset=expect_offset,
            min_overlap=min_overlap,
            approx_diff=approx_diff,
            transpose=transpose,
            seam_width=seam_width,
            verbose=verbose,
        )

        result = convert_video_to_image(src, output, config)
        click.echo(f"Output file: {result}")

    cli()


if __name__ == "__main__":
    main()
