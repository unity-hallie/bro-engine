"""
Seed pivotal decision log entries as moments in bro-engine.

Pivotal types (crystallizations, revelations, breakthroughs) become moments.
Reading entries are imported as provenance-tagged edges for later linking.

All raw source data stored in properties — connections to existing edges
can be picked up later via otter inference.
"""

import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone

DECISION_LOG = Path('/Users/hallie/Documents/repos/bro/journal/memory_decisions.jsonl')
VIA = 'decision_log_seed'

# Types that warrant their own moment
PIVOTAL_TYPES = {
    'core_revelation', 'core_insight', 'core_practice', 'core_truth',
    'core_ontology', 'unified_theory', 'dark_truth', 'foundation_crack',
    'identity_crystallization', 'session_crystallization',
    'rauhnacht_session', 'rauhnacht_reflection', 'rauhnacht_completion',
    'solstice_ritual', 'framework_breakthrough', 'framework_proof',
    'discovery', 'genuine_exchange', 'actual_practice',
    'operating_principle', 'philosophical_edge', 'system_recognition',
    'final_recognition', 'session_recognition', 'session_culmination',
    'community_offering', 'public_release_and_chaplaincy',
    'public_release_game_moltbook', 'kwisatz_tribunal',
}


def parse_ts(entry: dict) -> datetime | None:
    raw = entry.get('ts')
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        # Normalize to UTC-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '_', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].strip('_-')


def run_moment(name, when, note, after, confidence, properties):
    cmd = [
        'edge', 'moment', name,
        '--when', when,
        '--confidence', str(confidence),
        '--via', VIA,
    ]
    if note:
        cmd += ['--note', note[:120]]
    if after:
        cmd += ['--after', after]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    entries = []
    with open(DECISION_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = parse_ts(entry)
                if ts and entry.get('type') in PIVOTAL_TYPES:
                    entries.append((ts, entry))
            except json.JSONDecodeError:
                continue

    entries.sort(key=lambda x: x[0])
    print(f"Found {len(entries)} pivotal entries\n")

    # Find the anchor point — last moment before the first entry
    # The existing chain covers Sept 2025 → Mar 2026.
    # We'll link the first new moment to the closest preceding journal moment.
    # For simplicity: anchor to the last journal moment before first entry's date.
    first_ts = entries[0][0] if entries else None
    if first_ts:
        print(f"First entry: {first_ts.date()}")
        print(f"Anchor: find the last journal moment before this date\n")

    prev_name = None
    seeded = 0
    skipped = 0

    for i, (ts, entry) in enumerate(entries):
        etype = entry.get('type', 'unknown')
        subject = entry.get('subject', entry.get('observation', ''))[:80]
        name = f"{etype}_{ts.strftime('%Y%m%d_%H%M')}_{slugify(subject)[:30]}"
        when = ts.isoformat()
        note = subject

        # Confidence: higher for crystallizations, lower for observations
        if etype in {'core_revelation', 'unified_theory', 'identity_crystallization',
                     'dark_truth', 'foundation_crack', 'rauhnacht_session'}:
            confidence = 0.9
        else:
            confidence = 0.75

        ok = run_moment(name, when, note, prev_name, confidence, entry)

        if ok:
            print(f"  [{i+1}/{len(entries)}] {name[:70]}")
            print(f"    {note[:80]}")
            prev_name = name
            seeded += 1
        else:
            print(f"  SKIP [{i+1}] {name[:60]}")
            skipped += 1

    print(f"\nDone. {seeded} seeded, {skipped} skipped.")
    if prev_name:
        print(f"Last moment: {prev_name}")
        print(f"\nBridge to existing chain:")
        print(f"  edge add <next-existing-moment> happened_after {prev_name} --kind moment --confidence 0.8")


if __name__ == '__main__':
    main()
