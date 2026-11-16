"""The game state and the small rules every part of the engine shares.

No database and no screen code here, so the engine can run in tests and be replayed.
"""

from dataclasses import dataclass, field

from .catalogue import Item, Line
from .memory import remember_kill

FEARED, HIDDEN, BETRAYER, MERCIFUL, TRUSTED = "feared", "hidden", "betrayer", "merciful", "trusted"
FEARED_AFTER_KILLS = 3

# Who votes for an absent tribute facing a big decision (Game.Voters in the database).
NOBODY, PAST_WINNERS, DEAD, PAST_WINNERS_AND_DEAD, EVERYONE = (
    "nobody", "past_winners", "dead", "past_winners_and_dead", "everyone",
)  # fmt: skip
VOTED_QUESTIONS = {"meeting", "alliance_offer", "sleeper", "loyalty", "mercy"}
VOTES_PER_ROUND = 1


@dataclass(eq=False)
class Tribute:
    id: int  # position in the roster: 0, 1, 2... (district = id // 2 + 1)
    present: bool = True  # in the room: makes their own choices
    goal: str = ""  # what the tribute does today: HUNT, HIDE, SCAVENGE, GUARD
    alive: bool = True
    wounded: bool = False
    items: list[Item] = field(default_factory=list)
    alliance: int = 0  # 0 means no alliance; the same number means the same alliance
    grudges: list[int] = field(default_factory=list)  # ids of tributes this one wants revenge on
    tags: list[str] = field(default_factory=list)  # reputation: FEARED, HIDDEN, BETRAYER, MERCIFUL, TRUSTED
    debts: list[int] = field(
        default_factory=list
    )  # ids of tributes who spared this one: they owe them a life
    kills: int = 0
    died_on_day: int = 0

    @property
    def district(self):
        return self.id // 2 + 1


@dataclass(eq=False)
class Victor:
    """A past winner of the Yearly Games. Not a tribute: never in the arena, but when in the room
    they sponsor tributes and may vote for absent ones."""

    id: int  # position in the list of past victors: 0, 1, 2...
    present: bool = True  # in the room


@dataclass(frozen=True)
class Entry:
    """One line of the story. The values fill the placeholders of the line, whatever the language."""

    style: str  # death, hurt, item, team, arena, bad, cannon, win, heading, "heading night" or ""
    line: Line
    a: int | None = None  # tribute ids
    b: int | None = None
    sponsor: int | None = None
    victor: int | None = None  # a past victor's id (not a tribute id)
    item: str | None = None  # item key
    n: int | None = None
    names: tuple[int, ...] = ()


@dataclass
class Decision:
    """A question for a player in the room."""

    tribute: Tribute | Victor  # who decides: a tribute's player, or a past victor
    question: str  # key of the question, or "sponsor" / "victor_sponsor" / "gamemaker"
    option_count: int
    a: Tribute | None = None
    b: Tribute | None = None
    item: Item | None = None
    sponsor: Tribute | None = None
    victor: Victor | None = None  # fills {victor} in the question
    option_tributes: tuple[Tribute, ...] = ()  # sponsor question: the options are these tributes
    option_events: tuple = ()  # gamemaker question: the options are these arena events
    for_whole_arena: bool = False
    vote_for: Tribute | None = None  # a vote: the absent tribute the voters decide for
    vote_number: int = 0  # this voter is number vote_number of vote_total
    vote_total: int = 0


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
        alliance_count=0, feast_happened=False, winner=None, voters=NOBODY, no_conflict_votes=True,
        victors=(),
    ):  # fmt: skip
        self.catalogue = catalogue
        self.dice = dice
        self.tributes = tributes
        self.victors = list(victors)  # past victors: outside the arena
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
        self.voters = voters
        self.no_conflict_votes = no_conflict_votes
        self.votes_left = 0  # votes still allowed this round
        self.rumour = ""  # what the arena whispers today (see rounds.announce_rumour)

    # ---------- story ----------

    def add_to_story(
        self, style, line, *, a=None, b=None, sponsor=None, victor=None, item=None, n=None, names=()
    ):
        self.log.append(
            Entry(
                style, line,
                a=a.id if a else None,
                b=b.id if b else None,
                sponsor=sponsor.id if sponsor else None,
                victor=victor.id if victor else None,
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
        if (
            not tribute.present
            and question in VOTED_QUESTIONS
            and self.choices_left > 0
            and self.votes_left > 0
        ):
            voters = self.voters_for(tribute, values)
            if voters:
                self.choices_left -= 1
                self.votes_left -= 1
                return self.hold_vote(voters, tribute, question, weights, values)
        return self.dice.weighted_index(weights)

    def voters_for(self, tribute, values):
        """The people in the room who vote for this absent tribute, following the game's settings:
        tributes' players first, then past victors."""

        def in_group(voter):
            if self.voters == EVERYONE:
                return True
            if self.voters in (DEAD, PAST_WINNERS_AND_DEAD):
                return not voter.alive
            return False

        victors_vote = self.voters in (PAST_WINNERS, PAST_WINNERS_AND_DEAD, EVERYONE)
        # Past victors are never in a conflict: they have no tribute and no alliance.
        victor_voters = [victor for victor in self.victors if victor.present] if victors_vote else []

        involved = [t for t in (tribute, values.get("a"), values.get("b")) if t is not None]

        def has_conflict(voter):
            return any(voter is t or same_alliance(voter, t) for t in involved)

        tribute_voters = [
            voter for voter in self.tributes
            if voter.present and voter is not tribute and in_group(voter)
            and not (self.no_conflict_votes and has_conflict(voter))
        ]  # fmt: skip
        return tribute_voters + victor_voters

    def hold_vote(self, voters, tribute, question, weights, values):
        """Each voter picks an option. The most votes wins; a tie is settled by the dice."""
        option_count = self.catalogue.option_count(question)
        counts = [0] * option_count
        for number, voter in enumerate(voters, start=1):
            decision = Decision(
                voter, question, option_count, vote_for=tribute, vote_number=number, vote_total=len(voters),
                **values,
            )  # fmt: skip
            counts[self.ask_player(decision)] += 1
        best = max(counts)
        tied = [option for option, count in enumerate(counts) if count == best]
        if len(tied) == 1:
            return tied[0]
        return tied[self.dice.weighted_index([weights[option] or 1 for option in tied])]

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


def owes_life(tribute, other):
    """True if other once spared tribute."""
    return other.id in tribute.debts


def add_debt(tribute, benefactor):
    if not owes_life(tribute, benefactor):
        tribute.debts.append(benefactor.id)


def remove_debt(tribute, benefactor):
    tribute.debts = [debt for debt in tribute.debts if debt != benefactor.id]


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


def alliance_members(arena, alliance):
    return [t for t in arena.living() if alliance and t.alliance == alliance]


def alliance_leader(arena, alliance):
    """An alliance is led by its deadliest member (the first in the roster if tied)."""
    members = alliance_members(arena, alliance)
    return max(members, key=lambda t: (t.kills, -t.id)) if members else None
