# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Iterable, Set


# config
WATCH_LIST = [
    {
        "label": "江東",
        "base_url": "https://license-test-tokyo-prd-police-pref-api.tokyo-madoguchi-yoyaku.com/calgetres",
        "params": {
            "date": "202603",
            "coursecode": "11",
            "placecode": "250",
            "user": "pub",
        },
    },
    {
        "label": "鮫洲",
        "base_url": "https://license-test-tokyo-prd-police-pref-api.tokyo-madoguchi-yoyaku.com/calgetres",
        "params": {
            "date": "202603",
            "coursecode": "11",
            "placecode": "280",
            "user": "pub",
        },
    },
    {
        "label": "府中",
        "base_url": "https://license-test-tokyo-prd-police-pref-api.tokyo-madoguchi-yoyaku.com/calgetres",
        "params": {
            "date": "202603",
            "coursecode": "11",
            "placecode": "270",
            "user": "pub",
        },
    },
]

CHECK_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 15
DEBUG = False
NOTIFY_ON_START = True
# 通知に載せる日付の上限
NOTIFY_DAY_LIMIT = 6
# 通知に載せる枠の上限
NOTIFY_SLOT_LIMIT = 12
# 過去日を除外する
IGNORE_PAST_DATES = True
# Discord webhook URL（空なら無視）
DISCORD_WEBHOOK_URL = ""
DISCORD_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# =================


@dataclass
class WatchTarget:
    label: str
    url: str


def build_url(base_url: str, params: Dict[str, str]) -> str:
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def to_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def payload_items(payload) -> Optional[list]:
    if isinstance(payload, dict):
        payload = payload.get("body")
    if isinstance(payload, list):
        return payload
    return None


def parse_yyyymmdd(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y%m%d")
    except Exception:
        return None


def license_tag(display: str) -> str:
    if "マイナ" in display:
        return "マイナ免許証"
    if "従来" in display:
        return "従来免許証"
    return "免許種別不明"


def iter_available_slots(payload) -> Iterable[Tuple[str, str, str, int, int, str]]:
    items = payload_items(payload)
    if items is None:
        return []
    today = datetime.now().date()
    slots: List[Tuple[str, str, str, int, int, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        day = str(item.get("date") or item.get("day") or "unknown")
        if IGNORE_PAST_DATES:
            day_dt = parse_yyyymmdd(day)
            if day_dt is not None and day_dt.date() < today:
                continue
        start = str(item.get("starttime") or "")
        end = str(item.get("endtime") or "")
        display = str(item.get("displaytime") or "")
        capacity = to_int(item.get("capacity"))
        reservation = to_int(item.get("reservation"))
        if capacity is None or reservation is None:
            continue
        if capacity > reservation:
            slots.append((day, start, end, capacity, reservation, display))
    return slots


def summarize_by_day(slots: Iterable[Tuple[str, str, str, int, int, str]]) -> List[Tuple[str, int]]:
    day_counts: Dict[str, int] = {}
    for day, _start, _end, capacity, reservation, _display in slots:
        day_counts[day] = day_counts.get(day, 0) + (capacity - reservation)
    return sorted(day_counts.items())


def format_notification(slots: Iterable[Tuple[str, str, str, int, int, str]]) -> str:
    slots = list(slots)
    if not slots:
        return "空きなし"

    day_summary_all = summarize_by_day(slots)
    day_summary = day_summary_all[:NOTIFY_DAY_LIMIT]
    day_text = "、 ".join([f"{day}(+{avail})" for day, avail in day_summary])
    if len(day_summary_all) > NOTIFY_DAY_LIMIT:
        day_text += "、 ..."

    slot_texts = []
    for day, start, end, capacity, reservation, display in slots[:NOTIFY_SLOT_LIMIT]:
        tag = license_tag(display)
        slot_texts.append(f"{day} {start}-{end} {tag} {reservation}/{capacity}")
    slot_text = "\n".join(slot_texts)
    if len(slots) > NOTIFY_SLOT_LIMIT:
        slot_text += "\n..."

    total_avail = sum([capacity - reservation for _d, _s, _e, capacity, reservation, _disp in slots])

    return (
        f"合計空き: {total_avail}\n"
        f"日付別: {day_text}\n"
        f"枠:\n{slot_text}"
    )


def fetch_json(url: str) -> Optional[object]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"[WARN] fetch failed: {url} ({exc})")
        return None


def notify(title: str, message: str) -> None:
    if DISCORD_WEBHOOK_URL:
        try:
            payload = json.dumps({"content": f"**{title}**\n{message}"}).encode("utf-8")
            req = urllib.request.Request(
                DISCORD_WEBHOOK_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": DISCORD_USER_AGENT,
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS):
                pass
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            msg = f"{exc}"
            if detail:
                msg += f" body={detail}"
            print(f"[WARN] discord webhook failed: {msg}")
        except Exception as exc:
            print(f"[WARN] discord webhook failed: {exc}")

    # try plyer first
    try:
        from plyer import notification  # type: ignore

        notification.notify(title=title, message=message, timeout=10)
        return
    except Exception:
        pass

    # try win10toast
    try:
        from win10toast import ToastNotifier  # type: ignore

        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=10, threaded=True)
        return
    except Exception:
        pass

    # fallback
    print(f"[NOTIFY] {title} - {message}")
    print("\a", end="")


def build_targets() -> List[WatchTarget]:
    targets: List[WatchTarget] = []
    for entry in WATCH_LIST:
        url = build_url(entry["base_url"], entry["params"])
        targets.append(WatchTarget(label=entry["label"], url=url))
    return targets


def main() -> int:
    targets = build_targets()
    if not targets:
        print("WATCH_LIST is empty. Please add targets.")
        return 2

    last_available: Dict[str, Set[str]] = {}

    print(f"Watching {len(targets)} targets every {CHECK_INTERVAL_SECONDS}s")
    for t in targets:
        print(f" - {t.label}: {t.url}")

    while True:
        for target in targets:
            try:
                payload = fetch_json(target.url)
                if payload is None:
                    continue

                available_slots = list(iter_available_slots(payload))
                available_keys = {
                    f"{day}|{start}|{end}|{capacity}|{reservation}|{display}"
                    for day, start, end, capacity, reservation, display in available_slots
                }
                prev_keys = last_available.get(target.url, set())
                last_available[target.url] = available_keys

                new_keys = available_keys - prev_keys
                new_slots = [
                    s
                    for s in available_slots
                    if f"{s[0]}|{s[1]}|{s[2]}|{s[3]}|{s[4]}|{s[5]}" in new_keys
                ]

                if DEBUG:
                    items = payload_items(payload)
                    items_count = len(items) if items is not None else "n/a"
                    print(
                        f"[DEBUG] {target.label}: items={items_count} "
                        f"available_slots={len(available_slots)} new_slots={len(new_slots)}"
                    )

                should_notify = False
                if new_slots:
                    should_notify = True
                elif NOTIFY_ON_START and available_slots and prev_keys == set():
                    should_notify = True

                if should_notify:
                    msg = format_notification(new_slots if new_slots else available_slots)
                    notify(f"空き検知: {target.label}", msg)
                    print(f"[INFO] availability detected for {target.label}: {msg}")
            except Exception as exc:
                print(f"[WARN] error processing {target.label}: {exc}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
