"""Encode branded browser-capture frames into per-component looping GIFs."""

import argparse
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
import subprocess

from build_downloads import digest, temporary_file
from build_preview import ENTRIES

try:
    from PIL import Image
except ImportError:
    Image = None


FFMPEG = Path(shutil.which('ffmpeg') or (
    "C:/Users/Lenovo/.codex/visualizations/2026/11/08/"
    "01a1bc31-98e4-7af0-b84b-739e66db1267/output/"
    "toy-brand-20261109/video/tools/ffmpeg.exe"
))
FPS = 8
MAX_WIDTH = 480
TAIL_HOLD = 0.8
PALETTE_COLORS = 192


def read_capture(manifest, slug):
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("slug") != slug:
        raise ValueError(f"采集清单的slug与组件不一致 {manifest}")
    width, height = data.get("width"), data.get("height")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in (width, height)):
        raise ValueError(f"采集清单需要有效width和height {manifest}")
    frames = data.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError(f"采集清单至少需要两帧 {manifest}")
    prepared = []
    previous = -1.0
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise ValueError(f"frames[{index}]需要file和time")
        filename, timestamp = frame.get("file"), frame.get("time")
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError(f"frames[{index}].file需要本地图片路径")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0 or timestamp <= previous:
            raise ValueError(f"frames[{index}].time需要递增的秒数")
        source = (manifest.parent / filename).resolve()
        if not source.is_file():
            raise ValueError(f"采集图片不存在 {source}")
        with Image.open(source) as picture:
            if picture.size != (width, height):
                raise ValueError(f"采集帧尺寸不一致 {source}")
            picture.verify()
        prepared.append({"file": source, "time": float(timestamp), "sha256": digest(source)})
        previous = timestamp
    return {"width": width, "height": height, "frames": prepared,
            "source_sha256": data.get("source_sha256", {}),
            "duration": prepared[-1]["time"] - prepared[0]["time"],
            "manifest_sha256": digest(manifest)}


def concat_text(frames):
    lines = ["ffconcat version 1.0"]
    for index, frame in enumerate(frames):
        filename = frame["file"].as_posix().replace("'", "'\\''")
        duration = frames[index + 1]["time"] - frame["time"] if index + 1 < len(frames) else TAIL_HOLD
        lines.extend([f"file '{filename}'", f"duration {duration:.9f}"])
    # Repeating the final filename makes the concat demuxer honor its duration.
    filename = frames[-1]["file"].as_posix().replace("'", "'\\''")
    lines.append(f"file '{filename}'")
    return "\n".join(lines) + "\n"


def inspect_gif(source, allow_static=False):
    distinct, duration = set(), 0
    with Image.open(source) as picture:
        frames, dimensions, loop = picture.n_frames, picture.size, picture.info.get("loop")
        minimum = 1 if allow_static else 2
        if picture.format != "GIF" or frames < minimum or loop != 0:
            raise ValueError(f"GIF需要至少两帧并无限循环 {source}")
        for index in range(frames):
            picture.seek(index)
            duration += picture.info.get("duration", 0)
            distinct.add(hashlib.sha256(picture.convert("RGB").tobytes()).digest())
    if len(distinct) < minimum or duration <= 0:
        raise ValueError(f"GIF缺少实际画面变化或播放时长 {source}")
    return {"frame_count": frames, "width": dimensions[0], "height": dimensions[1],
            "duration_seconds": duration / 1000, "loop": loop,
            "distinct_frames": len(distinct), "visible_changes": len(distinct) > 1}


def commit_pair(staged, previous):
    """Commit GIF and metadata together, restoring owned outputs on a failure."""
    backups, committed, preserved = {}, [], set()
    generated = {target: digest(source) for target, source in staged.items()}
    try:
        for target in staged:
            if target.is_symlink() or digest(target) != previous[target]:
                raise ValueError(f"编码期间输出已变化，请保留新内容 {target}")
            if previous[target] is not None:
                backup = temporary_file(target.parent, ".demo-gif.backup")
                backup.write_bytes(target.read_bytes())
                backups[target] = backup
        for target, source in staged.items():
            if target.is_symlink() or digest(target) != previous[target]:
                raise ValueError(f"提交期间输出已变化，请保留新内容 {target}")
            os.replace(source, target)
            committed.append(target)
    except BaseException as error:
        recovery = []
        for target in reversed(committed):
            try:
                if target.exists() and digest(target) != generated[target]:
                    if target in backups:
                        preserved.add(backups[target])
                        recovery.append(str(backups[target]))
                    else:
                        recovery.append(str(target))
                    continue
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                if target in backups:
                    preserved.add(backups[target])
                    recovery.append(str(backups[target]))
                else:
                    recovery.append(str(target))
        if recovery:
            raise OSError(str(error) + "\n请保留这些恢复材料 " + ", ".join(recovery)) from error
        raise
    finally:
        for source in list(staged.values()) + list(backups.values()):
            if source not in preserved:
                source.unlink(missing_ok=True)


def encode(root, frames_root, entry, ffmpeg, overwrite):
    manifest = frames_root / entry.name / "frames.json"
    capture = read_capture(manifest, entry.name)
    output = root / "skills" / entry.name / "examples"
    if not output.is_dir():
        raise ValueError(f"组件示例目录不存在 {output}")
    source_hashes = capture['source_sha256']
    if not isinstance(source_hashes, dict):
        raise ValueError('source_sha256需要素材指纹对象')
    for filename, expected in source_hashes.items():
        source = (output / filename).resolve()
        if not source.is_relative_to(output.resolve()) or digest(source) != expected:
            raise ValueError(f'演示素材已变化，请重新录制 {entry.name}: {filename}')
    targets = [output / "demo.gif", output / "demo-gif.json"]
    inputs = {manifest.resolve()} | {frame["file"] for frame in capture["frames"]}
    if inputs.intersection(path.resolve() for path in targets):
        raise ValueError("GIF或记录输出不能覆盖采集来源")
    for target in targets:
        if target.is_symlink() or target.is_dir():
            raise ValueError(f"输出目标需要普通文件 {target}")
        if target.exists() and not overwrite:
            raise ValueError(f"输出已存在，请使用--overwrite {target}")
    lock_path = output / ".demo-gif.lock"
    try:
        lock_handle = lock_path.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError(f"该组件已有GIF编码任务 {lock_path}") from error
    staged, concat = {}, None
    try:
        lock_handle.write(str(os.getpid()))
        lock_handle.flush()
        previous = {target: digest(target) for target in targets}
        if not overwrite and any(value is not None for value in previous.values()):
            raise ValueError("编码开始前输出已存在，请使用--overwrite")
        concat = temporary_file(output, ".frames.ffconcat")
        concat.write_text(concat_text(capture["frames"]), encoding="utf-8", newline="\n")
        staged[targets[0]] = temporary_file(output, ".gif.part")
        graph = (
            f"[0:v]fps={FPS},scale=w='min({MAX_WIDTH},iw)':h=-1:flags=lanczos,split[a][b];"
            f"[a]palettegen=max_colors={PALETTE_COLORS}:stats_mode=diff[palette];"
            "[b][palette]paletteuse=dither=sierra2_4a:diff_mode=rectangle[out]"
        )
        command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-f", "concat", "-safe", "0", "-i", str(concat),
                   "-filter_complex_threads", "1", "-filter_complex", graph, "-map", "[out]",
                   "-t", f"{capture['duration'] + TAIL_HOLD:.9f}", "-an", "-loop", "0",
                   "-threads", "2", "-f", "gif", str(staged[targets[0]])]
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if process.returncode:
            raise ValueError("GIF编码失败 " + entry.name + "\n" + process.stderr[-2500:])
        info = inspect_gif(staged[targets[0]], allow_static=entry.kind == "html")
        if info["width"] > min(MAX_WIDTH, capture["width"]):
            raise ValueError("编码结果被意外放大 " + entry.name)
        expected_duration = capture["duration"] + TAIL_HOLD
        if abs(info["duration_seconds"] - expected_duration) > 0.3:
            raise ValueError("GIF时长与真实采集时间不一致 " + entry.name)
        if digest(manifest) != capture["manifest_sha256"]:
            raise ValueError("编码期间采集清单发生变化 " + entry.name)
        if any(digest(frame["file"]) != frame["sha256"] for frame in capture["frames"]):
            raise ValueError("编码期间采集图片发生变化 " + entry.name)
        record = {"slug": entry.name, "source": "browser-capture",
                  "source_sha256": source_hashes,
                  "play": "operation-illustration" if entry.kind == "workflow" else "component-demo",
                  **info, "sampling_fps": FPS, "palette_colors": PALETTE_COLORS,
                  "source_frame_count": len(capture["frames"]),
                  "capture_duration_seconds": capture["duration"], "tail_hold_seconds": TAIL_HOLD,
                  "source_manifest_sha256": capture["manifest_sha256"],
                  "bytes": staged[targets[0]].stat().st_size, "sha256": digest(staged[targets[0]])}
        staged[targets[1]] = temporary_file(output, ".json.part")
        staged[targets[1]].write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        commit_pair(staged, previous)
        return record
    finally:
        if concat is not None:
            concat.unlink(missing_ok=True)
        for source in staged.values():
            source.unlink(missing_ok=True)
        lock_handle.close()
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-root", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--only", nargs="+", choices=[entry.name for entry in ENTRIES], help="只编码列出的组件")
    parser.add_argument("--ffmpeg", type=Path, default=FFMPEG)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    frames_root, ffmpeg = args.frames_root.resolve(), args.ffmpeg.resolve()
    try:
        if Image is None:
            raise ValueError("需要Pillow读取采集帧并检查GIF")
        if not ffmpeg.is_file():
            raise ValueError("ffmpeg不存在，请通过--ffmpeg提供可执行文件")
        if not ENTRIES or len({entry.name for entry in ENTRIES}) != len(ENTRIES):
            raise ValueError("组件入口需要非空且身份唯一")
        selected = [entry for entry in ENTRIES if not args.only or entry.name in args.only]
        missing = [frames_root / entry.name / "frames.json" for entry in selected if not (frames_root / entry.name / "frames.json").is_file()]
        if missing:
            raise ValueError("采集清单未齐全 " + ", ".join(str(path) for path in missing))
        total = 0
        for entry in selected:
            record = encode(root, frames_root, entry, ffmpeg, args.overwrite)
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")), flush=True)
            total += 1
        print(json.dumps({"encoded": total, "selected": len(selected)}, ensure_ascii=False), flush=True)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
