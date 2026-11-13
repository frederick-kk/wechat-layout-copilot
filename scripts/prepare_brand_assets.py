"""Prepare display-sized WebP copies without changing source artwork."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--ffmpeg', required=True, type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text(encoding='utf-8'))
    target = args.root / 'assets/brand'
    masters = args.root / 'output/imagegen'
    target.mkdir(parents=True, exist_ok=True)
    masters.mkdir(parents=True, exist_ok=True)
    index_path = target / 'assets.json'
    records = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    for key, item in sources.items():
        source = Path(item['file']).resolve()
        destination = target / (key + '.webp')
        if destination.exists() and not args.overwrite:
            raise ValueError(f'Output exists {destination}')
        if not source.is_file():
            raise ValueError(f'Missing image {key}')
        width = 480 if key == 'avatar' else 1200
        command = [str(args.ffmpeg), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
                   '-vf', f'scale=min({width}\\,iw):-1', '-frames:v', '1', '-c:v', 'libwebp',
                   '-quality', '90', '-compression_level', '6', str(destination)]
        subprocess.run(command, check=True, capture_output=True)
        if item.get('generated'):
            master = masters / (key + source.suffix.lower())
            if not master.exists():
                shutil.copy2(source, master)
        records[key] = {'file': destination.name, 'bytes': destination.stat().st_size,
                        'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                        'direction': item.get('direction', '')}
    (target / 'assets.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
