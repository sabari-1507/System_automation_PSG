# makes history.csv - fake past readings from the arm fleet
# each row = one snapshot of one arm (3 joints x torque/temp/vib) + was it worn?
import csv
import random

random.seed(7)

JOINTS = ["shoulder", "elbow", "wrist"]
NOMINAL = {"shoulder": 110, "elbow": 80, "wrist": 35}   # normal torque in Nm


def one_row(worn):
    k = random.gauss(1.0, 0.08)          # payload factor, same for the whole arm
    sev = random.uniform(0.15, 1.2) if worn else 0
    row = {}
    for j in JOINTS:
        torque = NOMINAL[j] * k + random.gauss(0, 3) + 10 * sev
        temp = 38 + 0.2 * torque + random.gauss(0, 2) + 8 * sev
        vib = 0.8 + 0.02 * torque + abs(random.gauss(0, 0.3)) + 2.5 * sev
        row[j + "_torque"] = round(torque, 1)
        row[j + "_temp"] = round(temp, 1)
        row[j + "_vib"] = round(vib, 2)
    row["worn"] = 1 if worn else 0
    return row


rows = [one_row(False) for _ in range(70)] + [one_row(True) for _ in range(50)]
random.shuffle(rows)

with open("history.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print("wrote", len(rows), "rows")
