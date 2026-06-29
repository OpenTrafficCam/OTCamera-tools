import argparse
import json
import os
import subprocess
import time
from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


def count_frames(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return int(data["streams"][0]["nb_read_frames"])


@dataclass
class EvalResult:
    sum_files: int
    sum_expected: int
    sum_frames: int
    sum_exceptions: int
    sum_abs_errors: int

    @property
    def diff(self):
        return self.sum_frames - self.sum_expected

    @property
    def mean_abs_error(self):
        return self.sum_abs_errors / self.sum_files if self.sum_files > 0 else 0


def evaluate(
    video_len_s: int, fps: int, h264_file_paths: Collection[Path]
) -> EvalResult:

    sum_expected = 0
    sum_frames = 0
    sum_exceptions = 0
    sum_abs_errors = 0
    sum_files = 0

    expected_per_file = video_len_s * fps

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        future_to_path = {
            ex.submit(count_frames, path): path for path in h264_file_paths
        }
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                frames = future.result()
            except Exception as exc:
                sum_exceptions += 1
                print("%r generated an exception: %s" % (path, exc))
            else:
                print("%s has %d frames" % (str(path), frames))
                sum_files += 1
                sum_expected += expected_per_file
                sum_frames += frames

                sum_abs_errors += abs(frames - expected_per_file)
        print()

    return EvalResult(
        sum_expected=sum_expected,
        sum_frames=sum_frames,
        sum_files=sum_files,
        sum_exceptions=sum_exceptions,
        sum_abs_errors=sum_abs_errors,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--length", type=int, default=60)

    parser.add_argument("file", nargs="+", type=Path)

    args = parser.parse_args()

    start = time.perf_counter()
    result = evaluate(video_len_s=args.length, fps=args.fps, h264_file_paths=args.file)
    duration = time.perf_counter() - start

    print(f"Finished analyzing {len(args.file)} file(s) after {duration:.3f}s")
    print("Eval results:")
    print("-----------")
    print()
    print(f"FPS:   {args.fps}")
    print(f"Length: {args.length}s")
    print()

    print(f"Number of files:    {result.sum_files}")
    print(f"Skipped files:      {result.sum_exceptions}")
    print("-----------")
    print(f"Expected frames:    {result.sum_expected}")
    print(f"Actual frames:      {result.sum_frames}")
    print(f"Diff:               {result.diff}")
    print(f"Mean abs. error:    {result.mean_abs_error}")


if __name__ == "__main__":
    main()
