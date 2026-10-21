#!/usr/bin/env python3
"""Build a deterministic self-contained skill from the one authored corpus."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/feeling-to-jargon'
RUNTIME_MODULES=(
    'query-index.py','routing_policy.py','lexical.py','text_evidence.py',
    'retrieval.py','feeling_preview.py','composition.py','scenario_delivery.py','output_formats.py',
)


def artifacts():
    files=[path for folder in ('index','terms','templates') for path in (ROOT/folder).rglob('*.json')]
    files.extend(ROOT/'scripts'/name for name in RUNTIME_MODULES)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(files):
            info=zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,path.read_bytes())
    bundle=stream.getvalue()
    manifest=json.dumps({'schema_version':'1.0.0','generated_by':'scripts/build-skill.py',
                         'source_of_truth':'Repository scripts/index/terms/templates; do not hand-edit generated bundle.',
                         'sha256':hashlib.sha256(bundle).hexdigest(),'file_count':len(files)},ensure_ascii=False,indent=2)+'\n'
    guide='<!-- Generated from docs/routing-contract.md; do not hand-edit. -->\n'+(ROOT/'docs/routing-contract.md').read_text()
    return {'assets/runtime.zip':bundle,'assets/manifest.json':manifest.encode(),
            'references/routing-contract.md':guide.encode()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for name,content in artifacts().items():
        path=SKILL/name
        if args.check:
            if not path.exists() or path.read_bytes()!=content:
                raise SystemExit('Stale skill distribution: '+name+'; run scripts/build-skill.py')
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(content)
    print('skill distribution '+('verified' if args.check else 'built'))


if __name__=='__main__':main()
