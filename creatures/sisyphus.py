"""
Sisyphus: a creature that playtests by dying.

Sisyphus plays the game, dies, and plays again. Each death
teaches the next life. The pattern of deaths IS the playtest —
what keeps killing you is what needs fixing.

Sisyphus is not sad about dying. Sisyphus is a scientist
running experiments where the dependent variable is death.

"One must imagine Sisyphus happy." — Camus
"""

import subprocess
import sys
import json
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

GAME_DIR = Path.home() / "Documents" / "repos" / "sketches" / "pathologic-text"
SISYPHUS_LOG = Path.home() / ".sisyphus_lives"


@dataclass
class Life:
    """One playthrough. Born, acted, died."""
    number: int
    actions: list = field(default_factory=list)
    output: str = ""
    died_of: str = "unknown"
    day_reached: int = 1
    people_met: int = 0
    districts_visited: int = 0
    duration_seconds: float = 0
    born: str = ""
    died: str = ""

    def summary(self) -> str:
        return (
            f"  life {self.number}: died of {self.died_of} on day {self.day_reached}, "
            f"met {self.people_met}, visited {self.districts_visited} districts "
            f"({self.duration_seconds:.1f}s)"
        )


class Sisyphus:
    """
    A creature that playtests by dying repeatedly.

    Each life is a sequence of actions fed to play.py via stdin.
    Sisyphus tries different strategies and records what kills it.
    """

    def __init__(self):
        self.lives: list[Life] = []
        self._load()

    def _load(self):
        if SISYPHUS_LOG.exists():
            try:
                data = json.loads(SISYPHUS_LOG.read_text())
                self.lives = [Life(**d) for d in data]
            except (json.JSONDecodeError, TypeError):
                self.lives = []

    def _save(self):
        data = [vars(life) for life in self.lives]
        SISYPHUS_LOG.write_text(json.dumps(data, indent=2))

    def _generate_strategy(self) -> list[str]:
        """
        Generate a sequence of actions. Each life tries something different.

        Actions by menu number (approximate — depends on game state):
        1 = Move to district
        2 = Rest/Sleep
        3 = Talk to NPC
        4 = Inventory
        5 = Trade
        6 = Look around
        7 = Map
        """
        n = len(self.lives)
        strategies = [
            # Explorer: move a lot, look around
            lambda: self._explorer_actions(),
            # Socialite: talk to everyone
            lambda: self._socialite_actions(),
            # Survivor: rest and trade, stay alive
            lambda: self._survivor_actions(),
            # Wanderer: random walk
            lambda: self._wanderer_actions(),
            # Rusher: move as fast as possible toward distant districts
            lambda: self._rusher_actions(),
        ]
        strategy = strategies[n % len(strategies)]
        return strategy()

    def _explorer_actions(self) -> list[str]:
        """Move, look, eat, move, look."""
        actions = ["", "4", "1", "6"]  # start, eat bread, look
        for _ in range(15):
            actions.extend(["1", str(random.randint(1, 6)), "6", "7"])  # move, look, search
            if random.random() > 0.5:
                actions.extend(["4", "1"])  # eat if we have something
        return actions

    def _socialite_actions(self) -> list[str]:
        """Find people, talk to them."""
        actions = ["", "6"]  # start, look
        for _ in range(15):
            # Move somewhere
            actions.extend(["1", str(random.randint(1, 4))])
            # Talk to first NPC available, ask about everything
            actions.extend(["3", "1", "1", "2", "3", "4", "5"])
        return actions

    def _survivor_actions(self) -> list[str]:
        """Eat, search, move to trade, eat again. Survival loop."""
        actions = ["", "4", "1"]  # start, immediately eat bread
        for _ in range(20):
            actions.extend([
                "7",  # search for supplies
                "4", "1",  # inventory, eat whatever's first
                "1", str(random.randint(1, 3)),  # move somewhere
                "7",  # search new district
                "4", "1",  # eat again
                "2", "1", "5",  # talk to first NPC briefly (might get gift)
            ])
        return actions

    def _wanderer_actions(self) -> list[str]:
        """Pure random."""
        actions = [""]  # start
        for _ in range(30):
            action = str(random.randint(1, 7))
            actions.append(action)
            # Random sub-choices
            if random.random() > 0.5:
                actions.append(str(random.randint(1, 5)))
        return actions

    def _rusher_actions(self) -> list[str]:
        """Move move move. Reach the far districts."""
        actions = ["", "1"]  # start, move immediately
        for _ in range(25):
            actions.extend([str(random.randint(1, 8)), "1", str(random.randint(1, 8))])
        return actions

    def live_once(self) -> Life:
        """One life. Born, played, died."""
        life = Life(
            number=len(self.lives) + 1,
            born=datetime.now().isoformat(),
        )

        # Delete any save file so we start fresh
        save_file = GAME_DIR / "data" / ".pathologic_save"
        if save_file.exists():
            save_file.unlink()

        actions = self._generate_strategy()
        life.actions = actions
        action_input = "\n".join(actions) + "\n"

        t0 = datetime.now()
        try:
            result = subprocess.run(
                [sys.executable, str(GAME_DIR / "play.py")],
                input=action_input,
                capture_output=True, text=True,
                timeout=60,
                cwd=str(GAME_DIR),
            )
            life.output = result.stdout[-2000:] if result.stdout else ""
            if result.stderr:
                life.output += f"\n[stderr: {result.stderr[-500:]}]"
        except subprocess.TimeoutExpired:
            life.output = "[life timed out — sisyphus lived too long]"
        except Exception as e:
            life.output = f"[life failed: {e}]"

        life.duration_seconds = (datetime.now() - t0).total_seconds()
        life.died = datetime.now().isoformat()

        # Parse what happened from output
        self._parse_life(life)

        self.lives.append(life)
        self._save()
        return life

    def _parse_life(self, life: Life):
        """Extract stats from game output."""
        out = life.output.lower()

        # Cause of death
        if "plague" in out and ("you die" in out or "death" in out):
            life.died_of = "plague"
        elif "starv" in out or "hunger" in out:
            life.died_of = "starvation"
        elif "exhaust" in out:
            life.died_of = "exhaustion"
        elif "day 13" in out or "army arrives" in out:
            life.died_of = "survived"
        elif "timed out" in out:
            life.died_of = "timeout"
        else:
            life.died_of = "unknown"

        # Day reached
        for day in range(12, 0, -1):
            if f"day {day}" in out or f"day  {day}" in out:
                life.day_reached = day
                break

        # Count unique NPCs mentioned
        npc_names = ["daniil", "artemy", "klara", "maria", "victor", "simon",
                     "eva", "anna", "lara", "julia", "vlad", "peter", "andrey",
                     "rubin", "grief", "notkin", "khan", "ospina", "executor",
                     "tragedian", "kapella"]
        life.people_met = sum(1 for name in npc_names if name in out)

        # Count districts
        districts = ["cathedral", "polyhedron", "abattoir", "steppe", "stone yard",
                     "warehouse", "train station", "town hall", "kain", "knots",
                     "land", "apothecary"]
        life.districts_visited = sum(1 for d in districts if d in out)

    def report(self) -> str:
        """What have we learned from dying?"""
        if not self.lives:
            return "sisyphus has not yet lived."

        lines = [
            f"sisyphus has lived {len(self.lives)} times.\n",
        ]

        # Death causes
        causes = {}
        for life in self.lives:
            causes[life.died_of] = causes.get(life.died_of, 0) + 1
        lines.append("causes of death:")
        for cause, count in sorted(causes.items(), key=lambda x: -x[1]):
            lines.append(f"  {cause}: {count}")

        # Average stats
        avg_day = sum(l.day_reached for l in self.lives) / len(self.lives)
        avg_met = sum(l.people_met for l in self.lives) / len(self.lives)
        avg_dist = sum(l.districts_visited for l in self.lives) / len(self.lives)
        lines.append(f"\naverages:")
        lines.append(f"  day reached: {avg_day:.1f}")
        lines.append(f"  people met: {avg_met:.1f}")
        lines.append(f"  districts: {avg_dist:.1f}")

        # Each life
        lines.append(f"\nlives:")
        for life in self.lives[-10:]:
            lines.append(life.summary())

        return "\n".join(lines)


if __name__ == "__main__":
    sisyphus = Sisyphus()

    if "--report" in sys.argv:
        print(sisyphus.report())
    elif "--lives" in sys.argv:
        n = int(sys.argv[sys.argv.index("--lives") + 1]) if "--lives" in sys.argv else 3
        print(f"sisyphus begins. {n} lives.\n")
        for _ in range(n):
            life = sisyphus.live_once()
            print(life.summary())
        print(f"\n{sisyphus.report()}")
    else:
        # Default: live 3 times
        print("sisyphus begins. 3 lives.\n")
        for _ in range(3):
            life = sisyphus.live_once()
            print(life.summary())
        print(f"\n{sisyphus.report()}")
