"""Check that reverse-video can run on this computer, and say how to fix what's missing.

Usage: python -I doctor.py [--fetch-models]

Run it with the skill's venv python. --fetch-models downloads every model now (about 3 GB: Whisper
medium, AST, CLAP, Demucs htdemucs, YuNet) so the first teardown doesn't stop to wait for them."""
import importlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

os_env = __import__("os").environ
os_env.setdefault("HF_HUB_VERBOSITY", "error")
os_env.setdefault("TRANSFORMERS_VERBOSITY", "error")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WIN = platform.system() == "Windows"
MAC = platform.system() == "Darwin"
SKILL = Path(__file__).resolve().parent.parent
YUNET = Path.home() / ".cache" / "reverse-video" / "models" / "yunet.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
problems = []


def ok(msg):
    print("  ok    " + msg)


def bad(msg, fix):
    print("  MISSING " + msg)
    problems.append((msg, fix))


def tool_version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return "?"


def main():
    fetch = "--fetch-models" in sys.argv
    print(f"reverse-video check ({platform.system()}, Python {platform.python_version()})")
    print(f"  python: {sys.executable}")

    v = sys.version_info
    if v < (3, 10):
        bad(f"Python {v.major}.{v.minor} is too old (3.10+ needed)",
            "from the skill folder: uv venv --python 3.12 .venv (then the installs in the README)")
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        print("  note  this isn't a venv python; use the skill's .venv python so the packages are found")

    print("Programs")
    for exe in ("ffmpeg", "ffprobe"):
        if shutil.which(exe):
            ok(f"{exe}: {tool_version([exe, '-version'])[:60]}")
        else:
            bad(exe, "Windows: winget install Gyan.FFmpeg  |  Mac: brew install ffmpeg  |  Linux: apt install ffmpeg"
                     "  (then open a new terminal)")
    js = shutil.which("node") or shutil.which("deno")
    if js:
        ok(f"JavaScript runtime for YouTube downloads: {Path(js).stem}")
    else:
        bad("Node or Deno (yt-dlp needs one for YouTube)",
            "Windows: winget install OpenJS.NodeJS.LTS  |  Mac: brew install node  (local files and other sites work without it)")

    print("Python packages")
    mods = [("numpy", "numpy"), ("scipy", "scipy"), ("PIL", "pillow"), ("cv2", "opencv-python-headless"),
            ("onnxruntime", "onnxruntime"), ("faster_whisper", "faster-whisper"), ("yt_dlp", "yt-dlp"),
            ("shapely", "shapely"), ("pyclipper", "pyclipper"), ("yaml", "pyyaml"), ("demucs", "demucs"),
            ("torch", "torch"), ("transformers", "transformers"), ("rapidocr_onnxruntime", "rapidocr_onnxruntime")]
    from importlib import metadata
    for mod, pkg in mods:
        try:
            importlib.import_module(mod)
            try:
                ver = metadata.version(pkg)
            except Exception:
                ver = ""
            ok(f"{pkg} {ver}")
        except Exception as e:
            fix = ("uv pip install --no-deps rapidocr_onnxruntime" if pkg == "rapidocr_onnxruntime"
                   else "uv pip install -r scripts/requirements.txt --torch-backend cpu")
            bad(f"{pkg} ({type(e).__name__}: {str(e)[:80]})", "from the skill folder: " + fix)
    try:
        dists ={d.metadata["Name"].lower() for d in metadata.distributions() if d.metadata["Name"]}
        if "opencv-python" in dists and "opencv-python-headless" in dists:
            bad("two OpenCV builds installed (opencv-python and the headless one clash)",
                "uv pip uninstall opencv-python opencv-python-headless && uv pip install opencv-python-headless")
    except Exception:
        pass

    print("Models (download on first use, then cached)")
    if YUNET.exists():
        ok("YuNet face model")
    else:
        print("  later YuNet face model (0.3 MB)")
    try:
        from huggingface_hub import scan_cache_dir
        have = {r.repo_id for r in scan_cache_dir().repos}
    except Exception:
        have = set()
    for rid, what in (("Systran/faster-whisper-medium", "Whisper medium, ~1.5 GB"),
                      ("MIT/ast-finetuned-audioset-10-10-0.4593", "AST audio tagger, ~0.35 GB"),
                      ("laion/larger_clap_general", "CLAP, ~0.8 GB")):
        print(("  ok    " if rid in have else "  later ") + f"{rid} ({what})")

    if fetch and not problems:
        print("Fetching models (this takes a while the first time)")
        import urllib.request
        if not YUNET.exists():
            YUNET.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(YUNET_URL, YUNET)
            ok("YuNet")
        from faster_whisper import WhisperModel
        WhisperModel("medium", device="cpu", compute_type="int8")
        ok("Whisper medium")
        from transformers import (ASTForAudioClassification, AutoFeatureExtractor, ClapModel,
                                  ClapProcessor)
        AutoFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")
        ASTForAudioClassification.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")
        ok("AST")
        ClapProcessor.from_pretrained("laion/larger_clap_general")
        ClapModel.from_pretrained("laion/larger_clap_general")
        ok("CLAP")
        from demucs.pretrained import get_model
        get_model("htdemucs")
        ok("Demucs htdemucs")

    print()
    if problems:
        print(f"{len(problems)} thing(s) to fix:")
        for msg, fix in problems:
            print(f"- {msg}\n    {fix}")
        sys.exit(1)
    print("Ready. " + ("" if fetch else "Run with --fetch-models to download the models now (optional)."))


if __name__ == "__main__":
    main()
