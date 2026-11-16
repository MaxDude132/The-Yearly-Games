"""The game state and the small rules every part of the engine shares.

No database and no screen code here, so the engine can run in tests and be replayed.
"""

from dataclasses import dataclass, field

from .catalogue import Item, Line
from .memory import remember_kill

FEARED, HIDDEN, BETRAYER = "feared", "hidden", "betrayer"
FEARED_AFTER_KILLS = 3


@dataclass(eq=False)
class Tribute:
    id: int  # position in the roster: 0, 1, 2... (district = id // 2 + 1)
    present: bool = True  # in the room: makes their own choices
    alive: bool = True
    wounded: bool = False
    items: list[Item] = field(default_factory=list)
    alliance: int = 0  # 0 means no alliance; the same number means the same alliance
    grudges: list[int] = field(default_factory=list)  # ids of tributes this one wants revenge on
    tags: list[str] = field(default_factory=list)  # reputation: FEARED, HIDDEN, BETRAYER
    kills: int = 0
    died_on_day: int = 0

    @property
    def district(self):
        return self.id // 2 + 1


@dataclass(frozen=True)
class Entry:
    """One line of the story. The values fill the placeholders of the line, whatever the language."""

    style: str  # death, hurt, item, team, arena, bad, cannon, win, heading, "heading night" or ""
    line: Line
    a: int | None = None  # tribute ids
    b: int | None = None
    sponsor: int | None = None
    item: str | None = None  # item key
    n: int | None = None
    names: tuple[int, ...] = ()


@dataclass
class Decision:
    """A question for a player in the room."""

    tribute: Tribute  # who decides
    question: str  # key of the question, or "sponsor" / "gamemaker"
    option_count: int
    a: Tribute | None = None
    b: Tribute | None = None
    item: Item | None = None
    sponsor: Tribute | None = None
    option_tributes: tuple[Tribute, ...] = ()  # sponsor question: the options are these tributes
    option_events: tuple = ()  # gamemaker question: the options are these arena events
    for_whole_arena: bool = False


class NeedAnswer(Exception):
    """Raised when a player in the room must answer and no answer is known yet."""

    def __init__(self, decision):
        super().__init__(decision.question)
        self.decision = decision


class Arena:
    """One game in progress.

    ask(decision) must return the chosen option index, or raise NeedAnswer.
    """

    def __init__(
        self, catalogue, dice, tributes, ask, *, log=None, round=0, day=0,
        alliance_count=0, feast_happened=False, winner=None,
    ):  # fmt: skip
        self.catalogue = catalogue
        self.dice = dice
        self.tributes = tributes
        self.ask = ask
        self.log = log if log is not None else []
        self.saved_log_length = len(self.log)  # entries from here on are not in the database yet
        self.round = round  # 1 = Bloodbath, 2 = Day 1, 3 = Night 1, 4 = Day 2...
        self.day = day
        self.alliance_count = alliance_count
        self.feast_happened = feast_happened
        self.winner = winner
        self.fallen_this_round = []
        self.choices_left = 0  # pop-ups still allowed this round

    # ---------- story ----------

    def add_to_story(self, style, line, *, a=None, b=None, sponsor=None, item=None, n=None, names=()):
        self.log.append(
            Entry(
                style, line,
                a=a.id if a else None,
                b=b.id if b else None,
                sponsor=sponsor.id if sponsor else None,
                item=item.key if item else None,
                n=n,
                names=tuple(tribute.id for tribute in names),
            )
        )  # fmt: skip

    def line(self, group):
        return self.catalogue.line(group)

    def pick_line(self, group):
        """One random variation of a group of lines."""
        return self.dice.pick(self.catalogue.variants(group))

    # ---------- tributes ----------

    def living(self):
        return [tribute for tribute in self.tributes if tribute.alive]

    def more_than_one_alive(self):
        """Never kill the last tribute standing by accident."""
        return len(self.living()) > 1

    def dissolve_lonely_alliances(self):
        """An alliance of one is no alliance."""
        living = self.living()
        for tribute in living:
            if not any(other is not tribute and same_alliance(tribute, other) for other in living):
                tribute.alliance = 0

    def kill_tribute(self, victim, killer=None):
        """Kills a tribute. If someone did it, the victim's allies now hold a grudge against the killer."""
        victim.alive = False
        victim.died_on_day = self.day
        self.fallen_this_round.append(victim)
        if killer:
            killer.kills += 1
            for tribute in self.living():
                if tribute is not killer and same_alliance(tribute, victim):
                    add_grudge(tribute, killer)
        victim.alliance = 0
        self.dissolve_lonely_alliances()
        if killer:
            remember_kill(self, killer, victim)
            if killer.kills == FEARED_AFTER_KILLS and add_tag(killer, FEARED):
                self.add_to_story("bad", self.line("reputation.feared"), a=killer)

    # ---------- decisions ----------

    def decide(self, tribute, question, weights, **values):
        """Who decides what a tribute does: the player, if they are in the room and the round
        still allows a pop-up, otherwise the dice roll using the weights (one per option)."""
        if tribute.present and self.choices_left > 0:
            self.choices_left -= 1
            decision = Decision(tribute, question, self.catalogue.option_count(question), **values)
            return self.ask_player(decision)
        return self.dice.weighted_index(weights)

    def ask_player(self, decision):
        answer = self.ask(decision)
        if not 0 <= answer < decision.option_count:
            raise ValueError(f"answer {answer} is not an option of {decision.question}")
        return answer


# ---------- rules that only need the tributes ----------


def find_item(tribute, kind):
    return next((item for item in tribute.items if item.kind == kind), None)


def remove_item(tribute, item):
    tribute.items.remove(item)


def holds_grudge(tribute, other):
    return other.id in tribute.grudges


def add_grudge(tribute, other):
    if not holds_grudge(tribute, other):
        tribute.grudges.append(other.id)


def forgive_grudge(tribute, other):
    tribute.grudges = [grudge for grudge in tribute.grudges if grudge != other.id]


def same_alliance(a, b):
    return a.alliance != 0 and a.alliance == b.alliance


def has_tag(tribute, tag):
    return tag in tribute.tags


def add_tag(tribute, tag):
    """Gives a reputation tag. Returns True if the tribute did not have it yet."""
    if tag in tribute.tags:
        return False
    tribute.tags.append(tag)
    return True


def remove_tag(tribute, tag):
    if tag in tribute.tags:
        tribute.tags.remove(tag)
