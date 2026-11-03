"""Verify the explicitly required Colab Drive directory before starting a run."""
import argparse
import os
from pathlib import Path
import tempfile


def verify_storage(root, drive_root='/content/drive/MyDrive'):
    root=Path(root).resolve();drive=Path(drive_root).resolve()
    if not drive.is_dir() or not root.is_relative_to(drive):
        raise ValueError('Persistent Drive storage is required; no ephemeral fallback. Mount Drive and select a directory inside MyDrive.')
    root.mkdir(parents=True,exist_ok=True)
    # Test write, fsync and readback without touching existing run files.
    with tempfile.NamedTemporaryFile(dir=root,prefix='.caitanya-preflight-',delete=False) as f:
        path=Path(f.name);f.write(b'CAITANYA storage probe\n');f.flush();os.fsync(f.fileno())
    try:
        if path.read_bytes()!=b'CAITANYA storage probe\n':raise ValueError('Storage readback mismatch')
    finally:path.unlink()
    return {'directory':str(root),'write_fsync_readback':True,
            'limitation':'Readback verifies mounted storage access, not remote replication durability.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');args=p.parse_args()
    print(verify_storage(args.directory))
