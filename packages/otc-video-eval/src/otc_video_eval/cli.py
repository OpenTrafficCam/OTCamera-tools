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
    sum_expected: int
    sum_frames: int

    @property
    def diff(self):
        return self.sum_frames - self.sum_expected


def evaluate(
    video_len_s: int, fps: 20, h264_file_paths: Collection[Path]
) -> EvalResult:

    sum_expected = 0
    sum_frames = 0

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
                print("%r generated an exception: %s" % (path, exc))
            else:
                print("%s has %d frames" % (str(path), frames))
                sum_expected += expected_per_file
                sum_frames += frames
        print()

    return EvalResult(sum_expected=sum_expected, sum_frames=sum_frames)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--fps", type=int)
    parser.add_argument("--length", type=int)

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

    print(f"Number of files: {len(args.file)}")
    print(f"Expected frames: {result.sum_expected}")
    print(f"Actual frames:   {result.sum_frames}")
    print(f"Diff:            {result.diff}")


if __name__ == "__main__":
    main()
