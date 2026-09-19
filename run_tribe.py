"""
Run TRIBE v2 (facebookresearch/tribev2) inference on a video/audio/text file.

TRIBE v2 predicts fMRI brain responses on the fsaverage5 cortical mesh
(~20k vertices) from naturalistic video, audio, or text stimuli.

Repo:    https://github.com/facebookresearch/tribev2
Install: git clone the repo, then `pip install -e ".[plotting]"` (Python 3.11+).
Note:    the package is NOT on PyPI, so `pip install tribev2` will fail.
         ffmpeg must be installed and on your PATH for video/audio decoding.
"""

import argparse
import shutil
import sys
from pathlib import Path


def check_prerequisites() -> None:
    """Fail early with a helpful message if the package or ffmpeg is missing."""
    try:
        import tribev2  # noqa: F401
    except ImportError:
        sys.exit(
            "ERROR: the 'tribev2' package is not installed.\n"
            "It is not on PyPI. Install it from source:\n"
            "    git clone https://github.com/facebookresearch/tribev2.git\n"
            "    cd tribev2\n"
            '    pip install -e ".[plotting]"   # requires Python 3.11+\n'
        )

    if shutil.which("ffmpeg") is None:
        print(
            "WARNING: 'ffmpeg' was not found on your PATH. Video/audio decoding\n"
            "will likely fail. Install it (e.g. `winget install Gyan.FFmpeg`).",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run TRIBE v2 brain-response prediction on a stimulus file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", type=Path, help="Path to a video file (.mp4).")
    group.add_argument("--audio", type=Path, help="Path to an audio file.")
    group.add_argument("--text", type=Path, help="Path to a text file.")
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("./cache"),
        help="Folder to cache downloaded model weights (default: ./cache).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional .npy path to save the predictions array.",
    )
    args = parser.parse_args()

    check_prerequisites()

    from tribev2 import TribeModel

    print("Loading pretrained model 'facebook/tribev2' (downloads on first run)...")
    model = TribeModel.from_pretrained(
        "facebook/tribev2", cache_folder=str(args.cache)
    )

    # get_events_dataframe accepts video_path, audio_path, or text_path.
    if args.video is not None:
        stimulus = args.video
        kwargs = {"video_path": str(args.video)}
    elif args.audio is not None:
        stimulus = args.audio
        kwargs = {"audio_path": str(args.audio)}
    else:
        stimulus = args.text
        kwargs = {"text_path": str(args.text)}

    if not stimulus.exists():
        sys.exit(f"ERROR: input file not found: {stimulus}")

    print(f"Extracting events from: {stimulus}")
    df = model.get_events_dataframe(**kwargs)
    print(f"Got {len(df)} events.")

    print("Running prediction...")
    preds, segments = model.predict(events=df)

    # preds shape: (n_timesteps, n_vertices) on the fsaverage5 mesh (~20k vertices).
    # Predictions are offset 5s into the past to compensate for hemodynamic lag.
    print(f"preds.shape    = {tuple(preds.shape)}  # (n_timesteps, n_vertices)")
    print(f"num segments   = {len(segments)}")

    if args.out is not None:
        import numpy as np

        arr = preds.detach().cpu().numpy() if hasattr(preds, "detach") else np.asarray(preds)
        np.save(args.out, arr)
        print(f"Saved predictions to {args.out}")


if __name__ == "__main__":
    main()
