"""Alerte places Max Jeune Lyon <-> Paris (week-end). Gratuit, via GitHub Actions + ntfy."""
import os, json, datetime as dt
import requests

API = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/records"
TOPIC = os.environ["NTFY_TOPIC"]
TEST = os.environ.get("TEST") == "1"
STATE = "state.json"

ORIG, DEST = "LYON", "PARIS"
OUT_FRI_FROM = "19:00"   # vendredi: départ >= 19h
OUT_SAT_BEFORE = "12:00"  # samedi matin: départ < 12h
RET_ARR_MAX = "23:00"    # dimanche: arrivée à Lyon <= 23h


def trains(day, origin, dest):
    where = (f"date=date'{day}' and od_happy_card=\"OUI\" "
             f"and startswith(origine,\"{origin}\") and startswith(destination,\"{dest}\")")
    r = requests.get(API, params={"where": where, "limit": 100, "order_by": "heure_depart"}, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def fmt(t):
    return f"{t['heure_depart']}→{t['heure_arrivee']}"


def main():
    today = dt.date.today()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    seen_total, msgs = 0, []
    d = today
    while (d - today).days <= 31:
        if d.weekday() == 4 and d >= today:  # vendredi
            fri, sat, sun = d, d + dt.timedelta(1), d + dt.timedelta(2)
            out_f = [t for t in trains(fri, ORIG, DEST) if t["heure_depart"] >= OUT_FRI_FROM]
            out_s = [t for t in trains(sat, ORIG, DEST) if t["heure_depart"] < OUT_SAT_BEFORE]
            ret = [t for t in trains(sun, DEST, ORIG) if t["heure_arrivee"] <= RET_ARR_MAX]
            seen_total += len(out_f) + len(out_s) + len(ret)
            if (out_f or out_s) and ret:
                key = f"{fri}|" + ",".join(sorted(f"{t['date']}{t['train_no']}" for t in out_f + out_s + ret))
                if key not in state:
                    state[key] = True
                    lines = [f"Week-end du {fri:%d/%m}"]
                    if out_f: lines.append("Ven: " + ", ".join(fmt(t) for t in out_f))
                    if out_s: lines.append("Sam: " + ", ".join(fmt(t) for t in out_s))
                    lines.append("Dim retour: " + ", ".join(fmt(t) for t in ret))
                    msgs.append("\n".join(lines))
        d += dt.timedelta(1)

    for m in msgs:
        requests.post(f"https://ntfy.sh/{TOPIC}", data=m.encode("utf-8"),
                      headers={"Title": "Places Max dispo Lyon-Paris", "Priority": "high", "Tags": "train"})
    if TEST:
        requests.post(f"https://ntfy.sh/{TOPIC}",
                      data=f"Test OK: {seen_total} trains Max vus sur tes créneaux, {len(msgs)} alerte(s).".encode(),
                      headers={"Title": "Bot Max: test"})
    json.dump(state, open(STATE, "w"))
    print(f"{seen_total} trains vus, {len(msgs)} alertes")


main()
