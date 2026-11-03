"""Fair, budget-aware decision scheduling and bounded multi-step intentions.

Separation of concerns
----------------------
* **Cognition** - the shared model picks *what to attempt, why, and when to
  reconsider*.  That choice is one *decision* and is the only thing that calls
  the model.
* **Mechanical execution** - once an intention (``TRAVEL_TO``, ``GATHER_AT``,
  ``REST_FOR``) is accepted, deterministic code performs its individual steps
  through the same validated ``World.apply`` path.  Those steps are journaled
  with ``origin='mechanical_execution'`` and never counted as decisions.
* **Physiology** - advances on simulated time in ``physiology.py`` regardless of
  how many decisions were made.

The scheduler never invents an objective.  It only decides *when an inhabitant is
asked*, keeps waiting bounded, and ends an intention whose premises have
changed (the inhabitant is then asked again with interrupt priority).
"""
import copy
import heapq
import math
import time

from .lifecycle import age

TASK_SPECS = {  # action -> (required parameters, optional parameters)
    "TRAVEL_TO": ({"x", "z"}, {"reconsider_hours"}),
    "GATHER_AT": ({"resource_id", "amount"}, {"reconsider_hours"}),
    "REST_FOR": ({"hours"}, {"reconsider_hours"}),
    "CANCEL_TASK": (set(), set()),
}
TASK_ACTIONS = frozenset(TASK_SPECS)
MAX_GATHER_AMOUNT = 8
MAX_REST_HOURS = 12
MAX_RECONSIDER_HOURS = 24
MAX_REPLANS = 2
DECISION_ORIGINS = ("lfm_decision", "mock_policy")
MIN_DECISION_AGE = 3


def _new_record():
    return {"next_due": 0, "due_since": None, "last_decision": None, "decisions": 0, "failures": 0,
            "streak": 0, "wake": None, "last_wake": -10 ** 9, "wait_total": 0, "wait_max": 0,
            "interval_total": 0, "interval_max": 0, "intervals": 0, "tasks": 0, "last_seq": -1}


def _new_totals():
    return {"lfm_decisions": 0, "mock_decisions": 0, "rejected_decisions": 0, "failed_decisions": 0,
            "mechanical_steps": 0, "mechanical_rejections": 0, "reflex_interventions": 0,
            "tasks_started": 0, "tasks_completed": 0, "tasks_superseded": 0, "tasks_cancelled": 0,
            "tasks_interrupted": {}, "ticks_with_decisions": 0, "budget_exhausted_ticks": 0,
            "max_queue": 0, "next_task": 0, "decision_seq": 0, "memory_recalls": 0, "memory_items": 0}


def find_path(world, start, goal, max_expansions, max_length):
    """Deterministic A* over walkable tiles.  Returns tiles after ``start`` or ``None``."""
    from .nature import geography

    def walkable(x, z):
        return 0 <= x < world.width and 3 <= z < world.depth and \
            geography(x, z, world.width, world.depth, world.seed)["walkable"]

    if start == goal:
        return []
    if not walkable(*goal):
        return None
    heuristic = lambda p: abs(p[0] - goal[0]) + abs(p[1] - goal[1])
    frontier = [(heuristic(start), 0, start)]
    came, cost = {start: None}, {start: 0}
    expansions = 0
    while frontier and expansions < max_expansions:
        _, steps, node = heapq.heappop(frontier)
        if steps > cost[node]:
            continue
        expansions += 1
        if node == goal:
            path = []
            while node != start:
                path.append(list(node))
                node = came[node]
            path.reverse()
            return path if len(path) <= max_length else None
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (node[0] + dx, node[1] + dz)
            if not walkable(*nxt) or steps + 1 > max_length:
                continue
            if nxt not in cost or steps + 1 < cost[nxt]:
                cost[nxt] = steps + 1
                came[nxt] = node
                heapq.heappush(frontier, (steps + 1 + heuristic(nxt), steps + 1, nxt))
    return None


class DecisionScheduler:
    def __init__(self, config, state=None):
        self.config = config
        self.data = copy.deepcopy(state) if state else {"agents": {}, "totals": _new_totals()}
        for key, value in _new_totals().items():  # forward-compatible with older snapshots
            self.data["totals"].setdefault(key, value)

    def state(self):
        return copy.deepcopy(self.data)

    def record(self, aid):
        return self.data["agents"].setdefault(aid, _new_record())

    # ------------------------------------------------------------------ plans
    def plan(self, world, a, action, p):
        """Validate an intention and build its task.  Returns ``(error, task)``."""
        cfg = self.config
        hours = world.hours_per_tick
        years = age(world, a)
        if "reconsider_hours" in p:
            r = p["reconsider_hours"]
            if type(r) is not int or not 1 <= r <= MAX_RECONSIDER_HOURS:
                return "invalid reconsideration time", None
        reconsider = cfg.default_reconsider_ticks if "reconsider_hours" not in p else \
            max(1, math.ceil(p["reconsider_hours"] / hours))
        reconsider = min(reconsider, cfg.max_task_ticks)
        path, progress = [], {}
        if action == "TRAVEL_TO":
            if any(type(p[k]) is not int for k in ("x", "z")):
                return "invalid destination", None
            path = find_path(world, (a.x, a.z), (p["x"], p["z"]), cfg.max_path_expansions, cfg.max_path_length)
            if path is None:
                return "no walkable route within the planning bound", None
            if not path:
                return "already at destination", None
        elif action == "GATHER_AT":
            node = world.resources.get(p["resource_id"]) if isinstance(p["resource_id"], str) else None
            if not node or node["amount"] <= 0:
                return "resource unavailable", None
            if type(p["amount"]) is not int or not 1 <= p["amount"] <= MAX_GATHER_AMOUNT:
                return "invalid amount", None
            if years < 6:
                return "not old enough to gather independently", None
            path = find_path(world, (a.x, a.z), (node["x"], node["z"]), cfg.max_path_expansions, cfg.max_path_length)
            if path is None:
                return "no walkable route within the planning bound", None
            progress = {"gathered": 0}
        elif action == "REST_FOR":
            if type(p["hours"]) is not int or not 1 <= p["hours"] <= MAX_REST_HOURS:
                return "invalid rest duration", None
            progress = {"rest_total": max(1, math.ceil(p["hours"] / hours)), "rest_done": 0}
        duration = len(path) + (p.get("amount", 0) if action == "GATHER_AT" else 0) + progress.get("rest_total", 0)
        duration = max(duration, 1)
        if duration > cfg.max_task_ticks:
            return "intention exceeds the maximum task duration", None
        task = {"kind": action, "params": copy.deepcopy(p), "path": path, "step": 0, "progress": progress,
                "created_tick": world.tick, "reconsider_tick": world.tick + reconsider,
                "expires_tick": world.tick + min(cfg.max_task_ticks, duration + 4),
                "start": {"health": a.health, "critical_hunger": a.hunger >= cfg.critical_need,
                          "critical_thirst": a.thirst >= cfg.critical_need, "ill": bool(a.illness)}}
        return None, task

    def start(self, world, a, task, selected_by):
        totals = self.data["totals"]
        self.supersede(world, a, "new_decision")
        task["id"] = f"task-{totals['next_task']:06}"
        totals["next_task"] += 1
        task["selected_by"] = selected_by
        a.task = task
        totals["tasks_started"] += 1
        self.record(a.id)["tasks"] += 1
        return task["id"]

    def supersede(self, world, a, reason):
        if a.task:
            self._end(world, a, "superseded", {"reason": reason})
            self.data["totals"]["tasks_superseded"] += 1

    def cancel(self, world, a, reason="cancelled_by_inhabitant"):
        if not a.task:
            return False
        self._end(world, a, "cancelled", {"reason": reason})
        self.data["totals"]["tasks_cancelled"] += 1
        return True

    def _end(self, world, a, status, payload):
        task = a.task
        a.task = None
        world.emit("task_" + status, a.id, dict(payload, task_id=task["id"], kind=task["kind"], step=task["step"]),
                   "task_execution", origin="mechanical_execution", task_id=task["id"])

    def _interrupt(self, world, a, reason):
        self._end(world, a, "interrupted", {"reason": reason})
        key = reason.split(":")[0]
        counts = self.data["totals"]["tasks_interrupted"]
        counts[key] = counts.get(key, 0) + 1
        rec = self.record(a.id)
        rec["wake"], rec["last_wake"] = key, world.tick
        a.memories.append({"tick": world.tick, "feedback": "Your intention was interrupted: " + reason})
        a.memories[:] = a.memories[-40:]

    def _complete(self, world, a):
        self._end(world, a, "completed", {})
        self.data["totals"]["tasks_completed"] += 1
        self.record(a.id)["next_due"] = world.tick + 1

    # -------------------------------------------------------------- execution
    def _check(self, world, a):
        cfg, t = self.config, a.task
        if world.tick >= t["expires_tick"]:
            return "time_limit"
        start = t["start"]
        if a.health < start["health"] - cfg.health_drop_interrupt or (a.health < 40 <= start["health"]):
            return "health_deteriorated"
        if a.thirst >= cfg.critical_need and not start["critical_thirst"]:
            return "thirst_critical"
        if a.hunger >= cfg.critical_need and not start["critical_hunger"]:
            return "hunger_critical"
        if a.illness and not start["ill"]:
            return "illness_started"
        if t["kind"] == "GATHER_AT":
            node = world.resources.get(t["params"]["resource_id"])
            if not node or node["amount"] <= 0:
                return "resource_unavailable"
        return None

    def _mechanical(self, world, a, action, params):
        from .engine import Intent
        accepted, reason = world.apply(Intent(a.id, world.tick, action, params), origin="mechanical_execution",
                                       task_id=a.task["id"] if a.task else None,
                                       selected_by=a.task["selected_by"] if a.task else None)
        totals = self.data["totals"]
        totals["mechanical_steps" if accepted else "mechanical_rejections"] += 1
        return accepted, reason

    def _follow_path(self, world, a):
        """One mechanical step.  Returns 'at_goal' (no action taken), 'moved' or ``None`` (interrupted)."""
        t = a.task
        while t["step"] < len(t["path"]) and [a.x, a.z] == t["path"][t["step"]]:
            t["step"] += 1
        if t["step"] >= len(t["path"]):
            return "at_goal"
        nx, nz = t["path"][t["step"]]
        dx, dz = nx - a.x, nz - a.z
        if abs(dx) + abs(dz) != 1:
            return "moved" if self._replan(world, a) is False else None
        accepted, reason = self._mechanical(world, a, "MOVE", {"dx": dx, "dz": dz})
        if not accepted:
            if reason in ("blocked terrain", "water requires a crossing"):
                return "moved" if self._replan(world, a) is False else None
            self._interrupt(world, a, "path_blocked: " + reason)
            return None
        t["step"] += 1
        return "moved"

    def _replan(self, world, a):
        t = a.task
        t["replans"] = t.get("replans", 0) + 1
        if t["replans"] > MAX_REPLANS:
            self._interrupt(world, a, "path_blocked: route repeatedly invalid")
            return None
        goal = (t["params"]["x"], t["params"]["z"]) if t["kind"] == "TRAVEL_TO" else \
            (lambda n: (n["x"], n["z"]))(world.resources[t["params"]["resource_id"]])
        path = find_path(world, (a.x, a.z), goal, self.config.max_path_expansions, self.config.max_path_length)
        if path is None:
            self._interrupt(world, a, "path_blocked: no remaining route")
            return None
        t["path"], t["step"] = path, 0
        return False

    def _execute(self, world, a):
        reason = self._check(world, a)
        if reason:
            return self._interrupt(world, a, reason)
        t = a.task
        if t["kind"] == "REST_FOR":
            accepted, why = self._mechanical(world, a, "REST", {})
            if not accepted:
                return self._interrupt(world, a, "rejected: " + why)
            t["progress"]["rest_done"] += 1
            if t["progress"]["rest_done"] >= t["progress"]["rest_total"]:
                self._complete(world, a)
            return
        state = self._follow_path(world, a)
        if state is None:
            return
        if t["kind"] == "TRAVEL_TO":
            if state == "at_goal" or t["step"] >= len(t["path"]):
                self._complete(world, a)
            return
        if state != "at_goal":  # a move consumed this tick; gathering starts on the next one
            return
        node = world.resources[t["params"]["resource_id"]]
        accepted, why = self._mechanical(world, a, "GATHER", {"resource_id": node["id"]})
        if not accepted:
            return self._interrupt(world, a, "rejected: " + why)
        t["progress"]["gathered"] += 1
        if t["progress"]["gathered"] >= t["params"]["amount"] or node["amount"] <= 0:
            self._complete(world, a)

    def _reflex(self, world):
        cfg = world.autonomy.reflex
        if not cfg.enabled:
            return
        from .engine import Intent
        from .nature import EDIBLE
        for aid in sorted(world.agents):
            a = world.agents[aid]
            if not a.alive or age(world, a) < MIN_DECISION_AGE or a.busy_until_tick > world.tick:
                continue
            action = "DRINK" if a.thirst >= cfg.drink_at and a.inventory.get("water", 0) else \
                "EAT" if a.hunger >= cfg.eat_at and any(a.inventory.get(k, 0) for k in EDIBLE) else None
            if action and world.apply(Intent(aid, world.tick, action), origin="survival_reflex")[0]:
                self.data["totals"]["reflex_interventions"] += 1

    def _wake_guardians(self, world):
        cfg = self.config
        for child in world.agents.values():
            if not child.alive or not child.guardian_ids or age(world, child) >= world.biology.adulthood_years:
                continue
            if max(child.hunger, child.thirst) < cfg.dependent_alert_need:
                continue
            for gid in child.guardian_ids:
                g = world.agents.get(gid)
                if not g or not g.alive or age(world, g) < world.biology.adulthood_years:
                    continue
                rec = self.record(gid)
                if rec["wake"] is None and world.tick - rec["last_wake"] >= cfg.wake_cooldown_ticks and \
                        abs(g.x - child.x) + abs(g.z - child.z) <= 12:
                    rec["wake"], rec["last_wake"] = "dependent_need", world.tick

    # ------------------------------------------------------------- scheduling
    def _due(self, world):
        cfg, queue = self.config, []
        for aid in sorted(world.agents):
            a = world.agents[aid]
            if not a.alive or age(world, a) < MIN_DECISION_AGE or a.busy_until_tick > world.tick:
                continue
            rec = self.record(aid)
            due = (rec["wake"] is not None or world.tick >= a.task["reconsider_tick"]) if a.task \
                else world.tick >= rec["next_due"]
            if not due:
                rec["due_since"] = None
                continue
            if rec["due_since"] is None:
                rec["due_since"] = world.tick
            wait = world.tick - rec["due_since"]
            urgency = max(a.hunger, a.thirst, 100 - a.health)
            priority = 0 if wait >= cfg.max_wait_ticks else 1 if rec["wake"] else 2
            # Ties are broken by who was served longest ago, which keeps the rotation a true FIFO.
            queue.append((priority, -wait, rec["last_seq"], -urgency, aid))
        queue.sort()
        return queue

    def run(self, world):
        """One tick of scheduling: reflex, mechanical execution, then decisions."""
        cfg, totals = self.config, self.data["totals"]
        self._reflex(world)
        for aid in sorted(world.agents):
            a = world.agents[aid]
            if a.alive and a.task and a.busy_until_tick <= world.tick:
                self._execute(world, a)
        self._wake_guardians(world)
        queue = self._due(world)
        totals["max_queue"] = max(totals["max_queue"], len(queue))
        real = world.is_real_backend
        started, made = time.monotonic(), 0
        for priority, *_, aid in queue:
            if made >= cfg.max_decisions_per_tick:
                break
            if real and made and time.monotonic() - started >= cfg.max_seconds_per_tick:
                break
            self._decide(world, aid, priority)
            made += 1
        if made:
            totals["ticks_with_decisions"] += 1
        if len(queue) > made:
            totals["budget_exhausted_ticks"] += 1

    def _decide(self, world, aid, priority):
        a, rec, totals = world.agents[aid], self.record(aid), self.data["totals"]
        wait = world.tick - (rec["due_since"] if rec["due_since"] is not None else world.tick)
        real = world.is_real_backend
        rec["wait_total"] += wait
        rec["wait_max"] = max(rec["wait_max"], wait)
        if rec["last_decision"] is not None:
            interval = world.tick - rec["last_decision"]
            rec["interval_total"] += interval
            rec["interval_max"] = max(rec["interval_max"], interval)
            rec["intervals"] += 1
        rec["last_decision"], rec["due_since"], rec["wake"] = world.tick, None, None
        rec["last_seq"] = totals["decision_seq"]
        totals["decision_seq"] += 1
        rec["decisions"] += 1
        origin = "lfm_decision" if real else "mock_policy"
        try:
            if world.autonomy.memory.enabled:
                from .memory import note_surroundings, recall
                note_surroundings(world, a)
                totals["memory_recalls"] += 1
                totals["memory_items"] += len(recall(world, a))
            intent = world.root.delegate(world, aid)
            request_id = world.backend.last_request["request_id"] if real else None
            accepted, reason = world.apply(intent, origin=origin, request_id=request_id,
                                           selected_by={"origin": origin, "request_id": request_id})
            totals["lfm_decisions" if real else "mock_decisions"] += 1
            rec["streak"] = 0
            rec["next_due"] = world.tick + self.config.min_decision_gap_ticks
            if not accepted:
                totals["rejected_decisions"] += 1
                if a.task:  # keep the running intention but ask again later
                    a.task["reconsider_tick"] = world.tick + self.config.default_reconsider_ticks
            a.memories.append({"tick": world.tick, "feedback": reason, "accepted": accepted})
            a.memories[:] = a.memories[-40:]
        except Exception as exc:  # no mock fallback: the inhabitant simply does nothing
            from .engine import Intent
            totals["failed_decisions"] += 1
            rec["failures"] += 1
            rec["streak"] += 1
            rec["next_due"] = world.tick + self.config.failure_backoff_ticks * min(rec["streak"], 4)
            world.reject(Intent(aid, world.tick, "WAIT"), "inference_failed: " + str(exc)[:200])
            world.emit("inference_failed", aid, {"error": str(exc)[:200]}, "inference_error")
            a.memories.append({"tick": world.tick, "feedback": "No action executed; decision failed."})
            a.memories[:] = a.memories[-40:]

    # ---------------------------------------------------------------- reports
    def report(self, world):
        """Fairness and attribution statistics (all measured, none estimated)."""
        living = [aid for aid, a in world.agents.items() if age(world, a) >= MIN_DECISION_AGE]
        recs = [self.data["agents"][aid] for aid in living if aid in self.data["agents"]]
        counts = [r["decisions"] for r in recs]
        intervals = [r["interval_total"] / r["intervals"] for r in recs if r["intervals"]]
        n = len(counts)
        return {"totals": copy.deepcopy(self.data["totals"]), "eligible_agents": n,
                "decisions_per_agent": {"min": min(counts, default=0), "max": max(counts, default=0),
                                        "mean": round(sum(counts) / n, 3) if n else 0},
                "mean_decision_interval_ticks": {"min": round(min(intervals, default=0), 3),
                                                 "max": round(max(intervals, default=0), 3),
                                                 "mean": round(sum(intervals) / len(intervals), 3) if intervals else 0},
                "max_wait_ticks": max((r["wait_max"] for r in recs), default=0),
                "max_interval_ticks": max((r["interval_max"] for r in recs), default=0),
                "failures_per_agent_max": max((r["failures"] for r in recs), default=0)}


def task_registry():
    """Intentions are ordinary validated actions whose effect is to start a bounded task."""
    from .actions import Spec

    def make(action):
        required, optional = TASK_SPECS[action]

        def run(world, a, p, payload):
            if action == "CANCEL_TASK":
                if not a.task:
                    return "no active intention"
                world.scheduler.cancel(world, a)
                payload["result"] = "intention_cancelled"
                return None
            error, task = world.scheduler.plan(world, a, action, p)
            if error:
                return error
            payload["task_id"] = world.scheduler.start(world, a, task, world._selected_by)
            payload["result"] = "intention_started"
            payload["planned_steps"] = len(task["path"])
            return None
        return Spec(frozenset(required), run, frozenset(optional), min_age=3.0)
    return {name: make(name) for name in TASK_SPECS}
