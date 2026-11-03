"""Private root-agent orchestration. Cosmological names describe software roles."""
import copy


class BrahmanAgent:
    id = "brahman"

    def __init__(self, state=None, mode="crisis"):
        if mode not in {"off", "observe", "crisis"}:
            raise ValueError("invalid root mode")
        self.data = copy.deepcopy(state) if state is not None else {
            "id": self.id, "policy_version": "preserve-v1", "children": {},
            "threads": {}, "next_thread": 0, "manifestations": [],
            "last_manifestation_tick": -1000, "decisions": 0,
        }
        self.data.setdefault("mode", mode)
        if self.data["mode"] not in {"off", "observe", "crisis"}:
            raise ValueError("invalid stored root mode")

    def register(self, world):
        """A deceased identity can continue in a later biological birth.

        No personal memories, skills, beliefs, status or moral rewards transfer.
        Existing children remain separate identities even after bodily death.
        """
        d = self.data
        if d["mode"] == "off":
            return
        for aid, agent in sorted(world.agents.items()):
            if aid in d["children"]:
                continue
            available = [tid for tid, t in sorted(d["threads"].items())
                         if not world.agents[t["lives"][-1]].alive]
            if agent.age_years_at_start == 0 and available:
                tid = available[0]
            else:
                tid = f"continuity-{d['next_thread']:06}"
                d["next_thread"] += 1
                d["threads"][tid] = {"lives": [], "action_counts": {}, "consequences": {}}
            d["threads"][tid]["lives"].append(aid)
            d["children"][aid] = {"parent": self.id, "thread": tid}

    def record(self, aid, action, payload):
        if self.data["mode"] == "off":
            return
        child = self.data["children"][aid]
        thread = self.data["threads"][child["thread"]]
        counts = thread["action_counts"]
        counts[action] = counts.get(action, 0) + 1
        # Factual consequences, not a righteousness score or a claim of doctrine.
        key = payload.get("outcome")
        if key:
            consequences = thread["consequences"]
            consequences[key] = consequences.get(key, 0) + 1

    def sustain(self, world):
        """Bounded root policy: observe globally, manifest once in a crisis.

        It cannot rewrite minds, resurrect bodies or generate resource gifts.
        The embodied delegate uses the same inference and action validation.
        """
        self.register(world)
        if self.data["mode"] == "off":
            return
        self.data["decisions"] += 1
        if self.data["mode"] != "crisis":
            return
        living = [a for a in world.agents.values() if a.alive]
        active = any(world.agents[m["agent_id"]].alive for m in self.data["manifestations"])
        crisis = living and all(a.hunger >= 85 or a.thirst >= 85 for a in living)
        if not crisis or active or world.tick-self.data["last_manifestation_tick"] < 1000:
            return
        from .engine import Agent
        anchor = min(living, key=lambda a: a.id)
        aid = f"agent-{world.next_agent_id:04}"
        world.next_agent_id += 1
        form = Agent(aid, anchor.x, anchor.z)
        form.goal = "Help nearby inhabitants survive using available resources and voluntary cooperation."
        form.inventory["water"] = 3
        # No privileged revelation or resource creation beyond a standard body.
        world.agents[aid] = form
        self.data["manifestations"].append({"agent_id": aid, "tick": world.tick,
                                               "reason": "universal_need_crisis"})
        self.data["last_manifestation_tick"] = world.tick
        self.register(world)
        world.emit("arrival", aid, {"x": form.x, "z": form.z}, "world_rule")

    def delegate(self, world, aid):
        self.register(world)
        if self.data["mode"] != "off" and aid not in self.data["children"]:
            raise ValueError("unregistered sub-agent")
        return world.backend.decide(world.observe(aid))

    def state(self):
        return copy.deepcopy(self.data)
