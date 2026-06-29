# otc-video-eval

CLI tool for analyzing H.264 video files and comparing their actual frame counts against an expected count derived from a known FPS and clip length.

## Requirements

- Python >= 3.13
- `ffprobe` (part of [FFmpeg](https://ffmpeg.org/))

## Installation

```bash
uv sync
```

## Usage

```
video-eval --fps <FPS> --length <SECONDS> <file> [<file> ...]
```

| Argument | Description |
|---|---|
| `--fps` | Expected frames per second of the recordings |
| `--length` | Expected duration of each clip in seconds |
| `file` | One or more H.264 files to analyze |

Files are processed in parallel using all available CPU cores.

## Example

Analyze three one-minute clips recorded at 25 fps:

```bash
video-eval --fps 25 --length 60 clip1.h264 clip2.h264 clip3.h264
```
