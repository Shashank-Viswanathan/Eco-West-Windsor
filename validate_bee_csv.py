import csv
import sys
import math
from collections import defaultdict, Counter


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def check_grouping(rows):
    """Adjacent rows should share video_file (script writes per-video)."""
    violations = 0
    for i in range(1, len(rows)):
        if rows[i]["video_file"] != rows[i - 1]["video_file"]:
            violations += 1
    return violations


def check_video_row_counts(rows):
    """How many rows per video_file. Real output: several per video."""
    counts = Counter(r["video_file"] for r in rows)
    singletons = sum(1 for v in counts.values() if v == 1)
    return counts, singletons


def check_reentry_parents(rows):
    """
    For every re-entry row, look for an earlier same-video row with a smaller
    first_frame. Report orphans and inversions.
    """
    # Build per-video index of (first_frame, row_index)
    per_video = defaultdict(list)
    for i, r in enumerate(rows):
        per_video[r["video_file"]].append((int(r["first_frame"]), i))

    for v in per_video:
        per_video[v].sort()

    total = 0
    orphaned = 0
    inverted = 0
    positive_gap = 0

    for i, r in enumerate(rows):
        vt = r.get("visit_type", "")
        if not vt.startswith("Re-entry"):
            continue
        total += 1
        ff = int(r["first_frame"])
        parents = [(f, j) for f, j in per_video[r["video_file"]] if j < i]
        if not parents:
            orphaned += 1
            continue
        latest_parent_frame = max(f for f, _ in parents)
        if ff <= latest_parent_frame:
            inverted += 1
        else:
            positive_gap += 1

    return {
        "total_reentries": total,
        "orphaned": orphaned,
        "inverted_first_frame": inverted,
        "positive_gap": positive_gap,
    }


def check_probability_ceiling(rows, tau=300.0):
    """
    For each re-entry with a positive gap, verify
        P <= exp(-dt / tau)
    (distance term only reduces P further, so this is the true ceiling).
    """
    per_video = defaultdict(list)
    for i, r in enumerate(rows):
        per_video[r["video_file"]].append((int(r["first_frame"]), i))
    for v in per_video:
        per_video[v].sort()

    checked = 0
    violations = 0
    worst = (0.0, None)

    for i, r in enumerate(rows):
        vt = r.get("visit_type", "")
        if not vt.startswith("Re-entry"):
            continue
        try:
            p = float(r["reentry_probability"])
        except (ValueError, KeyError):
            continue
        ff = int(r["first_frame"])
        parents = [f for f, j in per_video[r["video_file"]] if j < i]
        if not parents:
            continue
        parent_frame = max(parents)
        dt = ff - parent_frame
        if dt <= 0:
            continue
        ceiling = math.exp(-dt / tau)
        checked += 1
        if p > ceiling + 1e-9:
            violations += 1
            excess = p - ceiling
            if excess > worst[0]:
                worst = (excess, (r["video_file"], parent_frame, ff, dt, p, ceiling))

    return {
        "tau_used": tau,
        "checked_positive_gap": checked,
        "above_ceiling": violations,
        "worst_violation": worst,
    }


def check_id_schemes(rows):
    """Detect ID formats. Script emits BEE_EVENT_### per run."""
    patterns = Counter()
    for r in rows:
        eid = r.get("unique_bee_event_id", "")
        if eid.startswith("BEE_EVENT_CHN_"):
            patterns["CHN_####"] += 1
        elif eid.startswith("BEE_EVENT_") and eid[10:].isdigit():
            digits = len(eid[10:])
            patterns[f"NNN_{digits}digits"] += 1
        else:
            patterns["other"] += 1
    return patterns


def report(path):
    rows, fields = load_rows(path)
    print(f"File: {path}")
    print(f"Rows: {len(rows)}")
    print(f"Columns: {len(fields)}")
    print()

    grouping = check_grouping(rows)
    print(f"[grouping] adjacent rows with differing video_file: {grouping}")
    print(f"           (real output: 0, since script writes per video)")
    print()

    counts, singletons = check_video_row_counts(rows)
    print(f"[videos]  distinct video_file values: {len(counts)}")
    print(f"          videos appearing exactly once: {singletons}")
    print(f"          (real output: most videos appear multiple times)")
    print()

    re = check_reentry_parents(rows)
    print(f"[re-entry parents]")
    print(f"  total re-entry rows:        {re['total_reentries']}")
    print(f"  orphaned (no same-video parent): {re['orphaned']}")
    print(f"  inverted first_frame:       {re['inverted_first_frame']}")
    print(f"  positive gap (usable):      {re['positive_gap']}")
    print()

    pc = check_probability_ceiling(rows)
    print(f"[probability ceiling]  tau={pc['tau_used']}")
    print(f"  checked (positive-gap re-entries): {pc['checked_positive_gap']}")
    print(f"  above exp(-dt/tau) ceiling:        {pc['above_ceiling']}")
    if pc["worst_violation"][1]:
        w = pc["worst_violation"][1]
        print(f"  worst: file={w[0]} parent={w[1]} child={w[2]} dt={w[3]} "
              f"P={w[4]:.3f} ceiling={w[5]:.3f}")
    print()

    ids = check_id_schemes(rows)
    print(f"[id schemes]")
    for k, v in ids.items():
        print(f"  {k}: {v}")
    print()

    verdict = (
        grouping == 0
        and singletons < len(counts) * 0.2
        and re["orphaned"] == 0
        and re["inverted_first_frame"] == 0
        and pc["above_ceiling"] == 0
    )
    print("VERDICT:", "PASS — consistent with real pipeline output"
          if verdict else "FAIL — not consistent with real pipeline output")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python validate_bee_csv.py <csv path>")
        sys.exit(1)
    report(sys.argv[1])
