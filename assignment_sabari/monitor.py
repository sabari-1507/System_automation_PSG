# Robotic arm joint health monitor (solution 1)
# run:  python monitor.py
import csv
import os
import re
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
JOINTS = ["shoulder", "elbow", "wrist"]
SENSORS = ["torque", "temp", "vib"]

# ---- step 1: hard limits (no ML anywhere in here) ----
STOP_LIMITS = {"torque": 180.0, "temp": 105.0, "vib": 11.2}

# normal torque of each joint, used by the spoof check
NOMINAL_TORQUE = {"shoulder": 110.0, "elbow": 80.0, "wrist": 35.0}
SPOOF_GAP = 0.35   # how far one joint's torque ratio may be from the other two

# words we look for in the technician log, with how bad they sound
WORDS = {
    "burning smell": 4, "cracked": 4, "grinding": 3, "leak": 3, "overheating": 3,
    "loose": 3, "backlash": 3, "whine": 2, "jerky": 2, "rough": 2, "vibration": 2,
    "hot": 2, "noise": 1,
}
NEGATIONS = {"no", "not", "without", "none", "nothing", "fine", "normal"}
LOG_WINDOW_DAYS = 14


def hard_stop(reading):
    """Returns a list of reasons. Empty list = nothing crossed a limit.
    Missing / nan values also count, a dead sensor is not a safe sensor."""
    reasons = []
    for j in JOINTS:
        for s in SENSORS:
            v = reading[j][s]
            if v is None or v != v:
                reasons.append(f"{j} {s} reading missing")
            elif v > STOP_LIMITS[s]:
                reasons.append(f"{j} {s} = {v} (limit {STOP_LIMITS[s]})")
    return reasons


def load_history():
    X, y = [], []
    with open(os.path.join(HERE, "history.csv")) as f:
        for r in csv.DictReader(f):
            X.append([float(r[j + "_" + s]) for j in JOINTS for s in SENSORS])
            y.append(int(r["worn"]))
    return X, y


class KNNModel:
    """k-nearest-neighbours written by hand. Wear probability = share of the k
    closest past readings that were worn. Values are scaled first so that
    torque (big numbers) does not drown out vibration (small numbers)."""

    def __init__(self, X, y, k=7):
        n = len(X)
        cols = len(X[0])
        self.k = k
        self.mean = [sum(r[c] for r in X) / n for c in range(cols)]
        self.std = [(sum((r[c] - self.mean[c]) ** 2 for r in X) / n) ** 0.5 or 1.0 for c in range(cols)]
        self.X = [self._scale(r) for r in X]
        self.y = y

    def _scale(self, row):
        return [(v - m) / s for v, m, s in zip(row, self.mean, self.std)]

    def prob(self, row):
        z = self._scale(row)
        dist = sorted(
            (sum((a - b) ** 2 for a, b in zip(z, x)), label) for x, label in zip(self.X, self.y)
        )
        return sum(label for _, label in dist[:self.k]) / self.k


def train_model():
    X, y = load_history()
    # quick holdout check: every 4th row is kept out
    test = [i for i in range(len(X)) if i % 4 == 0]
    train = [i for i in range(len(X)) if i % 4 != 0]
    m = KNNModel([X[i] for i in train], [y[i] for i in train])
    ok = sum((m.prob(X[i]) >= 0.5) == (y[i] == 1) for i in test)
    print(f"[model] holdout accuracy: {ok / len(test):.2f}")
    return KNNModel(X, y)   # final model uses all rows


def wear_probability(model, reading):
    if model is None:
        return None
    return model.prob([reading[j][s] for j in JOINTS for s in SENSORS])


def spoof_check(reading):
    """Torque of the three joints moves together (same payload). If one joint's
    torque ratio is far from the average of the other two, we don't trust it."""
    ratio = {j: reading[j]["torque"] / NOMINAL_TORQUE[j] for j in JOINTS}
    suspects = []
    for j in JOINTS:
        others = [ratio[o] for o in JOINTS if o != j]
        gap = abs(ratio[j] - sum(others) / 2)
        if gap > SPOOF_GAP:
            suspects.append(f"{j} torque ratio off by {gap:.2f}")
    return suspects


def scan_log(path, arm, today):
    """Score 0..1 from recent notes of this arm. Returns (score, hits)."""
    total, hits = 0, []
    pat = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*\|\s*(ARM-\d+)\s*\|\s*(.*)$")
    with open(path) as f:
        for line in f:
            m = pat.match(line.strip())
            if not m:
                continue
            d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            if m.group(2) != arm or (today - d).days > LOG_WINDOW_DAYS:
                continue
            words = re.findall(r"[a-z']+", m.group(3).lower())
            text = " ".join(words)
            for kw, w in WORDS.items():
                pos = text.find(kw)
                if pos < 0:
                    continue
                before = text[:pos].split()[-3:]     # 3 words before the keyword
                if any(n in before for n in NEGATIONS):
                    continue
                total += w
                hits.append(kw)
    return min(total / 6, 1.0), hits


def decide(arm, reading, model, log_path, today):
    out = {"arm": arm}

    # 1) deterministic stop, always first
    stops = hard_stop(reading)
    if stops:
        out.update(decision="EMERGENCY_STOP", why="hard limit: " + "; ".join(stops))
        return out

    # 2) spoof check - if torque can't be trusted we can't call the arm safe
    sus = spoof_check(reading)
    if sus:
        out.update(decision="EMERGENCY_STOP", why="possible spoofed torque: " + "; ".join(sus))
        return out

    # 3) model + log
    p = wear_probability(model, reading)
    log_score, hits = scan_log(log_path, arm, today)
    out["wear_prob"] = None if p is None else round(p, 2)
    out["log_score"] = round(log_score, 2)
    out["log_hits"] = hits

    model_bad = p is not None and p >= 0.6
    log_bad = log_score >= 0.5

    if model_bad and log_bad:
        out.update(decision="SCHEDULE_MAINTENANCE", why="model and log agree")
    elif p is not None and p >= 0.85:
        out.update(decision="SCHEDULE_MAINTENANCE", why="model very sure of wear")
    elif model_bad or log_bad or log_score > 0:
        who = "model" if model_bad else "log"
        out.update(decision="MONITOR", why=f"only the {who} is worried")
    else:
        out.update(decision="SAFE", why="nothing unusual")
    return out


def mk(sh, el, wr):
    """helper: each arg is (torque, temp, vib)"""
    return {j: dict(zip(SENSORS, v)) for j, v in zip(JOINTS, (sh, el, wr))}


if __name__ == "__main__":
    today = date(2026, 10, 16)
    log_path = os.path.join(HERE, "maintenance_log.txt")
    model = train_model()

    scenarios = [
        ("ARM-01", "healthy, clean log", mk((112, 62, 2.9), (80, 54, 2.6), (35, 45, 1.7))),
        ("ARM-02", "sensors ok, but grinding noise in the log", mk((110, 61, 3.0), (79, 54, 2.5), (36, 46, 1.8))),
        ("ARM-03", "sensors drifting up + worrying notes", mk((126, 75, 6.0), (92, 69, 5.2), (40, 56, 3.6))),
        ("ARM-04", "shoulder temperature over the limit", mk((115, 108, 4.0), (80, 56, 2.7), (35, 46, 1.7))),
        ("ARM-05", "fake shoulder torque hiding a hot, shaky joint", mk((45, 88, 8.5), (82, 60, 3.0), (36, 47, 1.8))),
    ]
    print()
    for arm, label, reading in scenarios:
        r = decide(arm, reading, model, log_path, today)
        print(f"{arm} ({label})")
        print("   ->", r["decision"], "|", r["why"])
        if "wear_prob" in r:
            print(f"      wear_prob={r['wear_prob']} log_score={r['log_score']} hits={r['log_hits']}")
