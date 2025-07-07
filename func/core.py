import math
import numpy as np


def col_sampling(img_array: np.ndarray, sample_cols=None):
    """Sample columns from image array"""
    w = img_array.shape[1]
    if sample_cols is None:
        sample_cols = [
            np.linspace(20, w // 4, 3, dtype="int"),
            np.linspace(w // 2, 5 * w // 8, 3, dtype="int"),
            np.linspace(6 * w // 8, 7 * w // 8, 3, dtype="int"),
        ]
    return np.stack(
        [np.average(img_array[:, cols], axis=1) for cols in sample_cols], axis=1
    )


def predict_offset(max_val: int, p: int):
    """Generate optimal offset sequence"""
    p = np.clip(p, -max_val, max_val)
    positive = np.arange(1, max_val + 1, dtype=np.int16)
    negative = np.arange(-max_val, 0, dtype=np.int16)
    full = np.hstack((negative, positive))

    if p > 0:
        r_1 = full[2 * p : p + max_val][::-1]
        r_2 = full[max_val + p : 2 * max_val]
        r_3 = full[0 : 2 * p][::-1]
    else:
        r_1 = full[0 : max_val + p][::-1]
        r_2 = full[max_val + p : 2 * (max_val + p)]
        r_3 = full[2 * (max_val + p) :]

    r_1_2 = np.stack([r_1, r_2], axis=1).reshape([-1])
    return np.hstack([[0], r_1_2, r_3])


def diff_overlap(
    cols: np.ndarray, cols2: np.ndarray, predict=0, approx_diff=0.2, min_overlap=100
):
    """Calculate overlap position between two images"""
    approach_count = 0
    min_diff = (0, 255)
    max_offset = cols.shape[0] - min_overlap

    for offset in predict_offset(max_offset, predict):
        if offset == 0:
            diff = np.abs(cols - cols2)
        elif offset > 0:
            diff = np.abs(cols[offset:] - cols2[:-offset])
        else:
            diff = np.abs(cols[:offset] - cols2[-offset:])

        avg = np.average(diff)
        if avg < min_diff[1]:
            min_diff = (offset, avg)

        if avg < approx_diff:
            approach_count += 1
            if approach_count > 10 or avg < approx_diff / 4:
                return min_diff

    return min_diff


def predict(history: list, expect_offset: int, max_step=3):
    """Predict next frame offset based on historical data"""
    if len(history) < 1:
        return 1, 0
    if len(history) == 1:
        return 1, history[0][1]

    pre_data, data = history[-2], history[-1]
    offset_per_frame = data[1] / (data[0] - pre_data[0])

    if offset_per_frame == 0:
        return (max_step, 0) if pre_data[1] == 0 else (1, pre_data[1])

    frame_distance = math.floor(expect_offset / abs(offset_per_frame))
    step = max(min(frame_distance, max_step), 1)
    predict_y = int(step * offset_per_frame)
    return step, predict_y


def calc_overlaps(
    frames: np.ndarray,
    crop_top: int,
    crop_bottom: int,
    expect_offset: int,
    sample_cols=None,
    verbose=False,
    approx_diff=0.2,
    min_overlap=100,
):
    """Calculate overlap positions between video frames"""
    n = frames.shape[0]
    cols = col_sampling(frames[0][0][crop_top:-crop_bottom], sample_cols)
    results = []
    i = 1

    while i < n:
        cols2 = col_sampling(frames[i][0][crop_top:-crop_bottom], sample_cols)
        step, p = predict(results[-3:], expect_offset)
        offset, diff = diff_overlap(cols, cols2, p, approx_diff, min_overlap)
        results.append((i, offset, diff))

        if verbose:
            print(f"Frame {i}\tOffset {offset}\tPredict {p}\tDiff {diff:.3f}")

        i += step
        cols = cols2

    return results


def splice(
    frames: np.ndarray, results: list, crop_top: int, crop_bottom: int, seam_width=0
):
    """Splice frames into long image"""
    full_h, w = frames[0][0].shape
    h = full_h - crop_top - crop_bottom

    # Calculate canvas range
    y_min = y_max = 0
    y_current = 0
    top_frame = bottom_frame = 0

    for i, (frame_idx, offset, _) in enumerate(results):
        y_current += offset
        if y_current > y_max:
            y_max = y_current
            bottom_frame = frame_idx
        if y_current < y_min:
            y_min = y_current
            top_frame = frame_idx

    # Create and initialize canvas
    canvas_height = y_max - y_min + full_h
    canvas = np.zeros((canvas_height, w, 3), dtype=np.uint8)

    def get_frame_rgb(i):
        return np.dstack((frames[i][0], frames[i][1], frames[i][2]))

    # Place first frame
    y = crop_top - y_min
    canvas[y : y + h] = get_frame_rgb(0)[crop_top:-crop_bottom]
    canvas[:crop_top] = get_frame_rgb(top_frame)[:crop_top]
    canvas[-crop_bottom:] = get_frame_rgb(bottom_frame)[-crop_bottom:]

    # Splice subsequent frames
    for frame_idx, offset, _ in results:
        y += offset
        frame = get_frame_rgb(frame_idx)[crop_top:-crop_bottom]
        if seam_width > 0:
            frame[:seam_width] = [76, 84, 255]  # Debug seam line
        canvas[y : y + h] = frame

    return canvas
