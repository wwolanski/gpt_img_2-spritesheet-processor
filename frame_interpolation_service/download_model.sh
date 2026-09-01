#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
repo="$PWD/models/Practical-RIFE"
target="$repo/train_log"
repository_ref="${RIFE_REPOSITORY_REF:-bbfd2ea90910789a860ea3e2b32a240cd577b75e}" # Practical-RIFE main at 2026-09-01
model_sha256="e63d481b7ae5d4a4e6ad7ac5b410ff78f3bf7be3b51b2e38ca8152747abde5b4"
marker="$target/.repository-ref"
if [ -f "$target/RIFE_HDv3.py" ] && [ -f "$target/IFNet_HDv3.py" ] && [ -f "$target/flownet.pkl" ] \
  && [ -f "$marker" ] && [ "$(<"$marker")" = "$repository_ref" ]; then
  printf 'Practical-RIFE 4.25 already installed: %s\n' "$target"
  exit 0
fi

if [ ! -d "$repo/.git" ]; then
  git init "$repo" >/dev/null
  git -C "$repo" remote add origin https://github.com/hzwer/Practical-RIFE.git
fi
git -C "$repo" fetch --depth 1 origin "$repository_ref"
git -C "$repo" checkout --detach FETCH_HEAD >/dev/null
mkdir -p "$target"
archive="$(mktemp --suffix=.zip)"
trap 'rm -f "$archive"' EXIT

# Official Practical-RIFE 4.25 Google Drive artifact linked by upstream README.
python -m gdown 'https://drive.google.com/uc?id=1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg' -O "$archive"
python - "$archive" "$target" "$model_sha256" <<'PY'
from pathlib import Path
import hashlib
import shutil
import sys
import tempfile
import zipfile

archive = Path(sys.argv[1])
target = Path(sys.argv[2])
expected_sha256 = sys.argv[3]
digest = hashlib.sha256()
with archive.open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
if digest.hexdigest() != expected_sha256:
    raise SystemExit("RIFE model archive SHA-256 mismatch; refusing to extract it")
print("Verified RIFE model archive SHA-256.")

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            path = Path(member.filename)
            if member.is_dir() or path.is_absolute() or ".." in path.parts:
                continue
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(member) as source_file, destination.open("wb") as target_file:
                shutil.copyfileobj(source_file, target_file)
    candidates = list(root.rglob("RIFE_HDv3.py"))
    if len(candidates) != 1:
        raise SystemExit(f"Expected one RIFE_HDv3.py in model archive, found {len(candidates)}")
    model_dir = candidates[0].parent
    for item in model_dir.iterdir():
        if item.is_file() and (item.suffix == ".py" or item.name == "flownet.pkl"):
            shutil.copy2(item, target / item.name)

required = ("RIFE_HDv3.py", "IFNet_HDv3.py", "flownet.pkl")
missing = [name for name in required if not (target / name).is_file()]
if missing:
    raise SystemExit(f"Model archive missing required files: {missing}")
PY
printf '%s\n' "$repository_ref" > "$marker"
printf 'Practical-RIFE 4.25 installed: %s\n' "$target"
