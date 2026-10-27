"""Tiny persistent tracker: glasses today, goal streak, recently shown reminders."""
import json
import os
import threading
from datetime import date, timedelta

STATS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")
RECENT_LIMIT = 12


class Stats:
    def __init__(self, goal=8, path=STATS_PATH):
        self.goal = goal
        self.path = path
        self._lock = threading.Lock()
        self._d = {"date": str(date.today()), "glasses": 0, "streak": 0,
                   "last_goal_date": None, "recent": []}
        self._load()
        self._rollover()

    # ---- persistence ----------------------------------------------------
    def _load(self):
        try:
            with open(self.path, "r") as f:
                self._d.update(json.load(f))
        except Exception:
            pass

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self._d, f, indent=2)
        except Exception as e:
            print(f"[stats] Could not save stats: {e}")

    def _rollover(self):
        today = str(date.today())
        if self._d.get("date") != today:
            self._d["date"] = today
            self._d["glasses"] = 0
            self._save()

    # ---- queries -----------------------------------------------------------
    @property
    def glasses(self):
        with self._lock:
            self._rollover()
            return self._d["glasses"]

    @property
    def streak(self):
        """Consecutive days the goal was met (counting today if already met)."""
        with self._lock:
            last = self._d.get("last_goal_date")
            if not last:
                return 0
            today = date.today()
            if last in (str(today), str(today - timedelta(days=1))):
                return self._d.get("streak", 0)
            return 0

    def progress(self):
        return {"glasses": self.glasses, "goal": self.goal, "streak": self.streak}

    @property
    def recent_ids(self):
        with self._lock:
            return list(self._d.get("recent", []))

    # ---- updates -----------------------------------------------------------
    def add_glass(self):
        """Log a glass. Returns the updated progress dict."""
        with self._lock:
            self._rollover()
            self._d["glasses"] += 1
            today = date.today()
            if self._d["glasses"] == self.goal:
                last = self._d.get("last_goal_date")
                if last == str(today - timedelta(days=1)):
                    self._d["streak"] = self._d.get("streak", 0) + 1
                else:
                    self._d["streak"] = 1
                self._d["last_goal_date"] = str(today)
            self._save()
        return self.progress()

    def remember(self, reminder_id):
        with self._lock:
            recent = self._d.setdefault("recent", [])
            recent.append(reminder_id)
            del recent[:-RECENT_LIMIT]
            self._save()
