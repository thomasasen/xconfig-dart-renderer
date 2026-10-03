#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNK_DIR = ROOT / 'assets' / 'source-bundle'
SOURCE_DIR = ROOT / 'assets' / 'source'


def main() -> None:
    chunks = sorted(CHUNK_DIR.glob('source-images.tar.gz.b64.part-*'))
    if not chunks:
        raise SystemExit('source bundle chunks missing')

    payload = ''.join(p.read_text(encoding='ascii').strip() for p in chunks)
    archive = base64.b64decode(payload)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tf:
        members = []
        for member in tf.getmembers():
            name = Path(member.name)
            if member.isfile() and len(name.parts) == 1 and name.suffix.lower() == '.webp':
                members.append(member)
        tf.extractall(SOURCE_DIR, members=members, filter='data')

    print(f'restored {len(members)} source images from {len(chunks)} bundle chunks')


if __name__ == '__main__':
    main()
