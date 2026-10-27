"""Reminder content: a big pool of varied messages so it never feels repetitive.

Every reminder has a category (shown as a little label on the card), a headline,
a body, and a line to speak out loud. Selection takes into account:

* time of day (morning / afternoon / evening / night specific messages)
* today's progress (first glass, halfway, one-to-go, goal reached, streaks)
* what you've seen recently (never repeats the last few reminders)
"""
import random
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Reminder:
    id: str
    category: str
    headline: str
    body: str
    speech: str


# (id, category, headline, body, time-of-day tags or None for "any time")
_STATIC = [
    # --- gentle nudges --------------------------------------------------
    ("nudge1", "Sip check", "Quick pause", "A glass of water is calling your name. Answer it.", None),
    ("nudge2", "Sip check", "Water o'clock", "Your future self says thanks for this one.", None),
    ("nudge3", "Sip check", "Hey, hydrate", "Tiny habit, big payoff. Take a few good sips.", None),
    ("nudge4", "Sip check", "Time to refill", "Top up your tank. You've been working hard.", None),
    ("nudge5", "Sip check", "Take five sips", "Doesn't have to be a whole glass. Just start.", None),
    # --- science & fun facts -------------------------------------------
    ("fact1", "Fun fact", "Brain fuel", "Even mild dehydration can make it harder to concentrate. A glass helps.", None),
    ("fact2", "Fun fact", "Did you know?", "Water makes up roughly 60% of an adult's body. Keep it topped up.", None),
    ("fact3", "Fun fact", "Mostly water", "Your brain is roughly three quarters water. Treat it kindly.", None),
    ("fact4", "Fun fact", "Headache incoming?", "Mild dehydration can trigger headaches. A glass now might head one off.", None),
    ("fact5", "Fun fact", "Energy dip?", "Feeling sluggish? Fatigue is one of the early signs you're low on fluids.", None),
    ("fact6", "Fun fact", "Kidneys at work", "They filter all day long. Return the favour with some water.", None),
    # --- developer humour ------------------------------------------------
    ("dev1", "Dev humour", "Garbage collection", "Flush the cache. Drink some water before your next commit.", None),
    ("dev2", "Dev humour", "Hot reload yourself", "Refresh your brain with a glass of water. No build step required.", None),
    ("dev3", "Dev humour", "Unhandled exception", "User is dehydrated. Catch it with a glass of water.", None),
    ("dev4", "Dev humour", "Debug mode", "The rubber duck can wait. Water first, then the bug.", None),
    ("dev5", "Dev humour", "Deploy hydration", "Push one glass to production. Your body. No rollback needed.", None),
    ("dev6", "Dev humour", "Memory leak", "You've been focused for a while. Free up some mental RAM with a drink.", None),
    # --- move / eyes / posture combos -------------------------------------
    ("move1", "Move and sip", "Walk it off", "Stand up, go get water, and roll your shoulders on the way back.", None),
    ("move2", "Eye break", "The 20-20-20 rule", "Look at something 20 feet away for 20 seconds while you sip.", None),
    ("move3", "Posture check", "Sit tall", "Unclench your jaw, drop your shoulders, then drink.", None),
    # --- challenges ------------------------------------------------------
    ("chal1", "Mini challenge", "Beat the clock", "Finish this glass before you finish your next task.", None),
    ("chal2", "Mini challenge", "Sip, don't chug", "Steady sips are easier on your stomach than gulping it all at once.", None),
    ("chal3", "Mini challenge", "Refill ritual", "Drink this glass, then refill it so the next one is ready.", None),
    # --- morning -----------------------------------------------------------
    ("am1", "Good morning", "Start hydrated", "You've gone hours without water. Begin the day with a full glass.", {"morning"}),
    ("am2", "Good morning", "Wake up your brain", "Water first, then coffee. Your morning self will thank you.", {"morning"}),
    ("am3", "Good morning", "Fresh start", "New day, new glass. Get the first one in early.", {"morning"}),
    # --- afternoon -------------------------------------------------------------
    ("pm1", "Afternoon", "Slump alert", "Before you reach for more coffee, try a glass of water.", {"afternoon"}),
    ("pm2", "Afternoon", "Halfway through", "The day is half done. How is your water count looking?", {"afternoon"}),
    ("pm3", "Afternoon", "Second wind", "A cold glass is the cheapest productivity boost around.", {"afternoon"}),
    # --- evening ---------------------------------------------------------------
    ("eve1", "Evening", "Wind down", "Sip steadily this evening so your sleep isn't interrupted later.", {"evening"}),
    ("eve2", "Evening", "Last call soon", "Have a final glass or two while the evening is calm.", {"evening"}),
    # --- late night ------------------------------------------------------------
    ("night1", "Late night", "Small sips only", "A few sips, then rest. Your body repairs while you sleep.", {"night"}),
]

# Dynamic messages that depend on today's progress. Each builder returns
# (category, headline, body) or None if it doesn't apply right now.


def _dyn_first(p):
    if p["glasses"] == 0:
        return ("Fresh start", "Let's get glass one", f"Nothing logged yet today. Your goal is {p['goal']} glasses.")


def _dyn_mid(p):
    g, goal = p["glasses"], p["goal"]
    if 0 < g < goal - 1:
        left = goal - g
        return ("Progress", f"Glass number {g + 1}", f"{left} to go to hit your goal of {goal}. You've got this.")


def _dyn_almost(p):
    g, goal = p["glasses"], p["goal"]
    if g == goal - 1:
        return ("Almost there", "Just one more!", "One glass left to reach today's goal.")


def _dyn_done(p):
    g, goal = p["glasses"], p["goal"]
    if g >= goal:
        return ("Goal smashed", "Already there", f"You've hit {goal} glasses today. Extra sips are a bonus.")


def _dyn_streak(p):
    s = p["streak"]
    if s >= 2:
        return ("Streak", f"{s}-day streak", f"You've hit your water goal {s} days in a row. Keep the chain going.")


_DYNAMIC = [("dyn_first", _dyn_first), ("dyn_mid", _dyn_mid), ("dyn_almost", _dyn_almost),
            ("dyn_done", _dyn_done), ("dyn_streak", _dyn_streak)]

_GREETINGS = ["", "", "Hey! ", "Quick reminder: ", "Psst. ", "Friendly nudge: "]


def part_of_day(now=None):
    h = (now or datetime.now()).hour
    if 5 <= h < 11:
        return "morning"
    if 11 <= h < 17:
        return "afternoon"
    if 17 <= h < 22:
        return "evening"
    return "night"


def _speech(headline, body, name, rng):
    prefix = rng.choice(_GREETINGS)
    if name and rng.random() < 0.4:
        prefix = f"Hey {name}. "
    # Sometimes lead with the headline, sometimes just the body, for variety.
    if rng.random() < 0.35:
        return f"{prefix}{headline}. {body}".strip()
    return f"{prefix}{body}".strip()


def pick_reminder(progress, recent_ids, name="", now=None, rng=None):
    """Choose a reminder. `progress` = {glasses, goal, streak}."""
    rng = rng or random
    now = now or datetime.now()
    pod = part_of_day(now)
    recent = set(recent_ids)

    candidates = []  # (weight, Reminder)

    for rid, cat, head, body, tags in _STATIC:
        if rid in recent:
            continue
        if tags is not None and pod not in tags:
            continue
        weight = 3.0 if tags else 1.0  # time-of-day messages are more relevant
        candidates.append((weight, Reminder(rid, cat, head, body, _speech(head, body, name, rng))))

    for rid, fn in _DYNAMIC:
        if rid in recent:
            continue
        result = fn(progress)
        if result:
            cat, head, body = result
            candidates.append((2.5, Reminder(rid, cat, head, body, _speech(head, body, name, rng))))

    if not candidates:  # everything was "recent" - reset and allow anything
        return pick_reminder(progress, [], name, now, rng)

    weights = [w for w, _ in candidates]
    return rng.choices([r for _, r in candidates], weights=weights, k=1)[0]


def done_message(glasses, goal, streak=0):
    """Text shown on the card right after the user logs a glass."""
    left = goal - glasses
    if left <= 0 and glasses == goal:
        tail = f"Goal reached: {goal} of {goal} glasses today."
        if streak >= 2:
            tail += f" That's {streak} days in a row!"
        return "Goal reached!", tail
    if left <= 0:
        return "Bonus glass!", f"{glasses} glasses today. Above and beyond."
    if left == 1:
        return "Nice one!", f"Glass {glasses} logged. Just one more to go."
    return "Nice one!", f"Glass {glasses} logged. {left} more to reach your goal."
