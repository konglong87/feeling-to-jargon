#!/usr/bin/env python3
"""Installed read-only entrypoint; no extraction, cache, network or CWD dependency."""
import hashlib
import json
import runpy
import sys
import zipfile
from pathlib import Path, PurePosixPath

SKILL=Path(__file__).resolve().parents[1]
MAX_BUNDLE_BYTES=10*1024*1024


def main():
    bundle=SKILL/'assets/runtime.zip'
    try:
        manifest=json.loads((SKILL/'assets/manifest.json').read_text())
        if hashlib.sha256(bundle.read_bytes()).hexdigest()!=manifest['sha256']:
            raise ValueError('skill bundle checksum mismatch; reinstall the skill')
        with zipfile.ZipFile(bundle) as archive:
            if sum(item.file_size for item in archive.infolist())>MAX_BUNDLE_BYTES:
                raise ValueError('skill bundle exceeds resource budget')
            for member in archive.namelist():
                path=PurePosixPath(member)
                if path.is_absolute() or '..' in path.parts or '\\' in member:
                    raise ValueError('unsafe skill bundle path')
        sys.dont_write_bytecode=True
        sys.path.insert(0,str(bundle)+'/scripts')
        sys.argv[0]=str(bundle)+'/scripts/query-index.py'
        runpy.run_module('query-index',run_name='__main__')
        return 0
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        print('feeling-to-jargon: '+str(error),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
