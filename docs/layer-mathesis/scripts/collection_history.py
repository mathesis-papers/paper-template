"""Read-only preservation of publisher-owned collection version snapshots."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import shutil

HISTORY = ".mathesis/collection-history.json"


def history_files(root, work):
    marker = root / HISTORY
    directory = root / "versions"
    if not marker.exists() and not marker.is_symlink():
        if directory.exists() or directory.is_symlink():
            raise ValueError("versions require a publisher collection-history record")
        return {}
    if marker.is_symlink():
        raise ValueError("collection-history record must not be linked")
    record = json.loads(marker.read_text())
    if (record.get("schema") != "mathesis.collection-history.v1" or record.get("work") != work
            or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", record.get("source_commit", ""))):
        raise ValueError("collection-history source identity differs")
    hashes = record.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("collection-history requires frozen snapshots")
    for name, expected in hashes.items():
        p = PurePosixPath(name)
        if (str(p) != name or len(p.parts) < 3 or p.parts[0] != "versions"
                or not re.fullmatch(r"v[1-9][0-9]*", p.parts[1])
                or any(part in ("..", ".git") for part in p.parts) or "\\" in name
                or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)):
            raise ValueError("invalid collection-history path or digest")
        path = root / name
        if (path.is_symlink() or any((root / parent).is_symlink() for parent in p.parents)
                or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError("collection-history bytes differ: " + name)
    actual = {p.relative_to(root).as_posix() for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(hashes):
        raise ValueError("unlisted or missing collection-history snapshot")
    if any(not any(name.startswith(p.relative_to(root).as_posix() + "/") for name in hashes)
           for p in directory.rglob("*") if p.is_dir()):
        raise ValueError("unlisted collection-history directory")
    return hashes


def emit_history(root, out, work):
    hashes = history_files(root, work)
    for name in hashes:
        target = out / name
        if not target.resolve().is_relative_to(out.resolve()) or any((out / parent).is_symlink() for parent in PurePosixPath(name).parents):
            raise ValueError("linked historical output path")
        if target.is_symlink() or (target.exists() and (not target.is_file()
                                or hashlib.sha256(target.read_bytes()).hexdigest() != hashes[name])):
            raise ValueError("built content conflicts with a historical version")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    return hashes
