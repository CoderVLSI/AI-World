"""Build the flash image (and, optionally, a preview video) from the Sanskrit text.

    python -m gita_tft.build --chapters 1 --out build/gita_ch1.bin --video build/gita_ch1.mp4
    python -m gita_tft.build --chapters all --out build/gita_all.bin                      (the whole Gita: 701 verses)
    python -m gita_tft.build --chapters all --no-translit --out build/gita_sanskrit_only.bin   (smaller, for 4 MB flash)

The image is what you write to the flash partition (see firmware/README.md). The preview video is rendered by the Python reference of the
same drawing code the TFT runs, so it shows what the display will show (10 frames per second by default).
"""
import argparse
import json
import subprocess
from pathlib import Path

from . import flashimage as fi
from . import render, scene, text

FPS = 10


def chapter_numbers(spec):
    if spec == "all":
        return list(range(1, 19))
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    if not out or any(c < 1 or c > 18 for c in out):
        raise SystemExit("chapters are 1 to 18")
    return out


def build(chapters, translit=True, fps=FPS):
    """Returns (image bytes, report dict). Deterministic: the same inputs give the same bytes."""
    data = text.chapters()
    meta, art, verses, screens = [], [], [], []
    per_chapter = []
    first_verse = 0
    for c in chapters:
        verse_list = data[c - 1]
        meta.append((c, len(verse_list), first_verse))
        art.append(scene.art_params(c))
        frames_total = 0
        for v in verse_list:
            sc = text.verse_screens(v)
            first_screen = len(screens)
            kinds = [("sanskrit", 0)] + ([("iast", 1)] if translit else [])
            for kind, code in kinds:
                top, lines = sc[kind]
                mask, split = render.render_screen(kind, top, lines)
                frames = text.reading_frames(lines, fps) if kind == "sanskrit" else max(int(text.reading_frames(lines, fps) * 0.65), 3 * fps)
                screens.append({"mask_rows": mask, "split": split, "frames": frames, "kind": code})
                frames_total += frames
            verses.append((c, v["verse"], first_screen, len(kinds)))
        per_chapter.append({"chapter": c, "verses": len(verse_list), "seconds": round(frames_total / fps, 1)})
        first_verse += len(verse_list)
    blob = fi.build_image(meta, art, verses, screens)
    report = {"bytes": len(blob), "chapters": per_chapter, "verses": len(verses), "screens": len(screens), "fps": fps,
              "minutes": round(sum(p["seconds"] for p in per_chapter) / 60, 1), "translit": translit}
    return blob, report


def frames_of(blob, fps=FPS):
    """Yield every frame of the whole image in order as (H, W) RGB565 arrays: what the player shows."""
    img = fi.parse_image(blob)
    for ci, ch in enumerate(img["chapters"]):
        t = 0
        for v in [v for v in img["verses"] if v["chapter"] == ch["id"]]:
            for s in img["screens"][v["first_screen"]:v["first_screen"] + v["screens"]]:
                mask = fi.screen_mask(blob, s)
                for k in range(s["frames"]):
                    yield scene.compose(ch, mask, s["y0"], s["split"], t, k, s["frames"])
                    t += 1


def write_video(blob, path, fps=FPS, max_frames=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scene.W}x{scene.H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for frame in frames_of(blob, fps):
        if max_frames is not None and n >= max_frames:
            break
        proc.stdin.write(scene.to_rgb888(frame).tobytes())
        n += 1
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chapters", default="1")
    p.add_argument("--out", required=True)
    p.add_argument("--video")
    p.add_argument("--no-translit", action="store_true")
    p.add_argument("--fps", type=int, default=FPS)
    p.add_argument("--max-seconds", type=float, help="only render this many seconds of the video (a quick look)")
    args = p.parse_args(argv)
    blob, report = build(chapter_numbers(args.chapters), translit=not args.no_translit, fps=args.fps)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(blob)
    if args.video:
        report["video_frames"] = write_video(blob, args.video, args.fps, int(args.max_seconds * args.fps) if args.max_seconds else None)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
