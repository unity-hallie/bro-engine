"""
Seed journal entries as moments in bro-engine.

Scans bro/journal/*.md, extracts date from filename,
reads first meaningful line as note, chains them in order.
"""

import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

JOURNAL_DIR = Path('/Users/hallie/Documents/repos/bro/journal')
VIA = 'journal_seed'

def extract_date(filename: str) -> datetime | None:
    """Extract date from filename like 2025-09-17-something.md or 20251201-thing.md"""
    name = Path(filename).stem
    # Try YYYY-MM-DD prefix
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', name)
    if m:
        try:
            return datetime.fromisoformat(m.group(1))
        except ValueError:
            pass
    # Try YYYYMMDD prefix
    m = re.match(r'^(\d{8})', name)
    if m:
        try:
            s = m.group(1)
            return datetime(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            pass
    return None


def extract_note(filepath: Path) -> str:
    """Extract first meaningful line as note."""
    try:
        lines = filepath.read_text(errors='replace').splitlines()
        for line in lines[:5]:
            line = line.strip()
            if not line or line.startswith('*Migrated') or line.startswith('**Date'):
                continue
            # Strip markdown heading
            line = re.sub(r'^#+\s*', '', line)
            # Strip date prefix like "2025-09-17: "
            line = re.sub(r'^\d{4}-\d{2}-\d{2}:\s*', '', line)
            if line:
                return line[:120]
    except Exception:
        pass
    return ''


def moment_name(filepath: Path) -> str:
    """Derive moment name from filename."""
    stem = filepath.stem
    # Normalize to something graph-friendly
    name = re.sub(r'^(\d{4}-\d{2}-\d{2})-', r'\1_', stem)
    name = re.sub(r'^(\d{8})-', r'\1_', name)
    return name


def run(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return False
    return True


def main():
    # Gather all .md journal files with parseable dates
    entries = []
    for f in JOURNAL_DIR.glob('*.md'):
        dt = extract_date(f.name)
        if dt:
            entries.append((dt, f))

    entries.sort(key=lambda x: x[0])
    print(f"Found {len(entries)} dated journal entries\n")

    prev_name = None
    for i, (dt, filepath) in enumerate(entries):
        name = moment_name(filepath)
        note = extract_note(filepath)
        when = dt.strftime('%Y-%m-%d')

        cmd = [
            'edge', 'moment', name,
            '--when', when,
            '--confidence', '0.8',
            '--via', VIA,
        ]
        if note:
            cmd += ['--note', note]
        if prev_name:
            cmd += ['--after', prev_name]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  [{i+1}/{len(entries)}] {name} ({when})")
            if note:
                print(f"    {note}")
            prev_name = name
        else:
            print(f"  SKIP {name}: {result.stderr.strip()}")

    print(f"\nDone. {len(entries)} moments seeded.")
    print(f"Last moment: {prev_name}")
    print(f"\nChain continues from: {prev_name}")
    print(f"Next moment to add manually:")
    print(f"  edge moment <name> --when <date> --after {prev_name}")


if __name__ == '__main__':
    main()
