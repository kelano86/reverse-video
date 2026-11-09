"""Get a video and its metadata into a work folder: video.mp4, meta.json, cover.jpg.

Usage: python -I fetch.py <url or file> <workdir> [--cookies-from-browser firefox|chrome|edge|safari|brave]

Links (YouTube long form and Shorts, TikTok, X, Instagram and the rest yt-dlp supports) download
with yt-dlp: free, no account, no key. Instagram sometimes wants a signed-in session: then pass
--cookies-from-browser with a browser you're signed in to Instagram on (yt-dlp reads that browser's
cookies on this computer; nothing is sent anywhere else), or download the video yourself and pass
the file. A local file is linked in as is. meta.json carries title, caption, channel, date, views,
likes, comments and, for YouTube, the chapters and the most-replayed heatmap."""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import log, probe, run, save  # noqa: E402


def platform_of(url):
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "instagram.com" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    if "x.com" in u or "twitter.com" in u:
        return "x"
    return "web"


def ytdlp(url, wd, cookies_from=None):
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings", "-q"]
    if shutil.which("node"):  # YouTube's player needs a JS runtime; yt-dlp also finds deno on its own
        cmd += ["--js-runtimes", "node"]
    if cookies_from:
        cmd += ["--cookies-from-browser", cookies_from]
    cmd += ["-f", "bv*+ba/b", "-S", "res:1080,ext:mp4:m4a", "--merge-output-format", "mp4",
            "--write-info-json", "--write-thumbnail", "--convert-thumbnails", "jpg",
            "-o", str(wd / "video.%(ext)s"), url]
    r = run(cmd, timeout=1800)
    mp4 = wd / "video.mp4"
    if not mp4.exists():
        cands = [p for p in wd.glob("video.*") if p.suffix in (".mp4", ".mkv", ".webm", ".mov")]
        if cands:
            mp4 = cands[0]
    if not mp4.exists() or mp4.suffix not in (".mp4", ".mkv", ".webm", ".mov"):
        return None, (r.stderr or r.stdout or "").strip()[-600:]
    info = {}
    ij = wd / "video.info.json"
    if ij.exists():
        info = json.load(open(ij, encoding="utf-8"))
        ij.unlink()  # 10 MB of format lists; meta.json keeps what matters
    thumb = wd / "video.jpg"
    if thumb.exists():
        shutil.move(str(thumb), str(wd / "cover.jpg"))
    return info, None


def norm_meta(info, src, plat):
    keep = {}
    for k in ("id", "title", "description", "channel", "uploader", "channel_follower_count", "upload_date", "timestamp",
              "duration", "view_count", "like_count", "comment_count", "webpage_url", "tags", "categories",
              "chapters", "heatmap", "width", "height", "fps"):
        if info.get(k) is not None:
            keep[k] = info[k]
    if keep.get("description") and len(keep["description"]) > 4000:
        keep["description"] = keep["description"][:4000] + " ..."
    keep["source"] = src
    keep["platform"] = plat
    return keep


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("src")
    ap.add_argument("workdir")
    ap.add_argument("--cookies-from-browser", dest="cookies", default=None)
    a = ap.parse_args()
    src, wd = a.src, Path(a.workdir)
    wd.mkdir(parents=True, exist_ok=True)
    if (wd / "video.mp4").exists() and (wd / "meta.json").exists():
        log("already fetched:", wd / "video.mp4")
        return
    if os.path.exists(src):
        p = Path(src).resolve()
        dest = wd / ("video" + p.suffix.lower())
        try:
            os.link(p, dest)
        except OSError:
            shutil.copy2(p, dest)
        meta = {"source": str(p), "platform": "file", "title": p.stem}
    else:
        plat = platform_of(src)
        info, err = ytdlp(src, wd, a.cookies)
        if info is None:
            hint = ""
            if plat in ("instagram", "tiktok", "x") and not a.cookies:
                hint = ("\nThis platform sometimes wants a signed-in session. Re-run with --cookies-from-browser "
                        "<browser you're signed in on> (firefox is the most reliable; Chrome on Windows often "
                        "can't be read), or download the video yourself and pass the file instead of the link.")
            raise SystemExit(f"download failed: {err}{hint}")
        meta = norm_meta(info, src, plat)
    vids = [p for p in wd.glob("video.*") if p.suffix in (".mp4", ".mkv", ".webm", ".mov")]
    if not vids:
        raise SystemExit("no video file after fetch")
    if vids[0].suffix != ".mp4":  # remux/convert so every later step reads video.mp4
        r = run(["ffmpeg", "-y", "-v", "error", "-i", vids[0], "-c", "copy", wd / "video.mp4"])
        if r.returncode:
            run(["ffmpeg", "-y", "-v", "error", "-i", vids[0], "-c:v", "libx264", "-crf", "16", "-c:a", "aac",
                 "-b:a", "256k", wd / "video.mp4"])
    meta["probe"] = probe(wd / "video.mp4")
    if not (wd / "cover.jpg").exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", wd / "video.mp4", "-frames:v", "1", "-q:v", "2", wd / "first_frame.jpg"])
    save(wd / "meta.json", meta)
    pr = meta["probe"]
    log(f"fetched {meta.get('platform')}: {pr['width']}x{pr['height']} {pr['fps']}fps {pr['duration']:.1f}s"
        f" | {meta.get('channel') or meta.get('uploader') or ''} | {(meta.get('title') or '')[:70]}"
        f" | views {meta.get('view_count')}")


if __name__ == "__main__":
    main()
