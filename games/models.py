"""A game, saved in the database. Every browser session has one: first the setup, then the play.

Nothing is stored as JSON: tributes, what they carry, their grudges and the story are all rows.
"""

from django.db import models

from content.models import Item, StoryLine


class Game(models.Model):
    class Status(models.TextChoices):
        SETUP = "setup", "Setup"  # choosing names and who is in the room
        PLAYING = "playing", "Playing"  # includes a finished game that shows its winner

    class Voters(models.TextChoices):
        """Who votes for a tribute who is not in the room when they face a big decision."""

        NOBODY = "nobody", "Nobody (the arena decides)"
        PAST_WINNERS = "past_winners", "Past victors"
        DEAD = "dead", "The dead"
        PAST_WINNERS_AND_DEAD = "past_winners_and_dead", "Past victors and the dead"
        EVERYONE = "everyone", "Everyone in the room"

    session_key = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SETUP)
    voters = models.CharField(max_length=30, choices=Voters.choices, default=Voters.DEAD)
    # A rehearsal: a test run before game night. Not kept in the hall of fame; quitting frees the phones.
    rehearsal = models.BooleanField(default=False)
    # Fair play: nobody votes on a decision about their own tribute or their own alliance.
    no_conflict_votes = models.BooleanField(default=True)
    round = models.PositiveIntegerField(default=0)  # 1 = Bloodbath, 2 = Day 1, 3 = Night 1...
    day = models.PositiveIntegerField(default=0)
    alliance_count = models.PositiveIntegerField(default=0)
    feast_happened = models.BooleanField(default=False)
    winner = models.ForeignKey("Tribute", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Set while a round waits for a player's answer. The round is replayed from this seed
    # and the saved answers, so it always unfolds the same way.
    round_seed = models.BigIntegerField(null=True, blank=True)
    first_new_entry = models.PositiveIntegerField(default=0)  # story entries from here on are new
    # Players join from their phones at /play/<join_code>/ (the QR code). Set the first time it is needed.
    join_code = models.CharField(max_length=12, unique=True, null=True, blank=True)
    # Goes up by one after every change, so open pages (the host's and the phones') know to reload.
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.session_key[:8]} ({self.status})"


class Tribute(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="tributes")
    position = models.PositiveIntegerField()  # 0, 1, 2...: districts are pairs (0 & 1, 2 & 3...)
    name = models.CharField(max_length=30, blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True)
    present = models.BooleanField(default=True)  # in the room: makes their own choices
    # Set when a player took this tribute from their phone; their phone's session holds the same token.
    phone_token = models.CharField(max_length=32, blank=True, db_index=True)
    goal = models.CharField(
        max_length=10, blank=True
    )  # what the tribute does today: hunt, hide, scavenge, guard
    alive = models.BooleanField(default=True)
    wounded = models.BooleanField(default=False)
    alliance = models.PositiveIntegerField(default=0)  # 0 means no alliance
    kills = models.PositiveIntegerField(default=0)
    died_on_day = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["game", "position"], name="unique_tribute_position")]

    @property
    def district(self):
        return self.position // 2 + 1

    def __str__(self):
        return self.name or f"#{self.position + 1}"


class PastVictor(models.Model):
    """Someone who won an earlier Yearly Games. Not a tribute in this game: when in the room,
    they sponsor tributes and may vote for absent ones (see Game.voters)."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="victors")
    position = models.PositiveIntegerField()  # 0, 1, 2...
    name = models.CharField(max_length=30, blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True)
    present = models.BooleanField(default=True)  # in the room
    phone_token = models.CharField(max_length=32, blank=True, db_index=True)  # see Tribute.phone_token
    edition = models.PositiveSmallIntegerField(null=True, blank=True)  # which Games they won: 1 = the first
    year = models.PositiveSmallIntegerField(null=True, blank=True)  # the year they won (flavour only)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["game", "position"], name="unique_victor_position")]

    def __str__(self):
        return self.name or f"victor #{self.position + 1}"


class TributeItem(models.Model):
    tribute = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="carried")
    position = models.PositiveIntegerField()
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["tribute", "position"], name="unique_carried_item")]


class Grudge(models.Model):
    tribute = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="grudges")
    position = models.PositiveIntegerField()
    target = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["tribute", "position"], name="unique_grudge_position")]


class Debt(models.Model):
    """The tribute owes a life to the target, who spared them."""

    tribute = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="debts")
    position = models.PositiveIntegerField()
    target = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["tribute", "position"], name="unique_debt_position")]


class TributeTag(models.Model):
    """A reputation the story gave a tribute: feared, hidden or betrayer."""

    tribute = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="tags")
    position = models.PositiveIntegerField()
    tag = models.CharField(max_length=20)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["tribute", "position"], name="unique_tribute_tag_position")
        ]


class LogEntry(models.Model):
    """One line of the story. The line and its values are stored, never the text, so each viewer
    reads it in their own language."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="log")
    position = models.PositiveIntegerField()
    style = models.CharField(max_length=20, blank=True)
    line = models.ForeignKey(StoryLine, on_delete=models.PROTECT, related_name="+")
    a = models.ForeignKey(Tribute, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    b = models.ForeignKey(Tribute, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    sponsor = models.ForeignKey(Tribute, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    # A past victor who sent a gift. SET_NULL: removing a victor from the setup keeps old stories readable.
    victor = models.ForeignKey(PastVictor, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    n = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["game", "position"], name="unique_log_position")]


class LogEntryName(models.Model):
    """A name in the {names} placeholder of a log entry (the fallen of a round), in order."""

    entry = models.ForeignKey(LogEntry, on_delete=models.CASCADE, related_name="names")
    position = models.PositiveIntegerField()
    tribute = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["entry", "position"], name="unique_log_name_position")]


class Answer(models.Model):
    """A choice a player made during a round, in the order they were asked. Kept after the round,
    so Undo can replay the game (see PlayedRound)."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="answers")
    round = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField()
    choice = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["round", "position"]
        constraints = [
            models.UniqueConstraint(fields=["game", "round", "position"], name="unique_answer_position")
        ]


class PlayedRound(models.Model):
    """What it takes to play a round again: its seed, its answers (Answer.round) and who was in the room."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="played_rounds")
    number = models.PositiveIntegerField()  # Game.round once the round is over
    seed = models.BigIntegerField()
    present_tributes = models.ManyToManyField(Tribute, related_name="+")
    present_victors = models.ManyToManyField(PastVictor, related_name="+")

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["game", "number"], name="unique_played_round")]


class Bet(models.Model):
    """Before a night, a player in the room guesses who dies first that night.
    The player is a tribute (bettor) or a past victor (victor): exactly one of the two is set."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="bets")
    round = models.PositiveIntegerField()  # the night round the bet is about
    bettor = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="bets", null=True, blank=True)
    victor = models.ForeignKey(
        PastVictor, on_delete=models.CASCADE, related_name="bets", null=True, blank=True
    )
    target = models.ForeignKey(Tribute, on_delete=models.CASCADE, related_name="+")
    points = models.PositiveSmallIntegerField(null=True, blank=True)  # None until the night is over

    class Meta:
        ordering = ["round", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "round", "bettor"],
                condition=models.Q(bettor__isnull=False),
                name="unique_bet_per_round",
            ),
            models.UniqueConstraint(
                fields=["game", "round", "victor"],
                condition=models.Q(victor__isnull=False),
                name="unique_victor_bet_per_round",
            ),
            models.CheckConstraint(
                condition=models.Q(bettor__isnull=False, victor__isnull=True)
                | models.Q(bettor__isnull=True, victor__isnull=False),
                name="bet_has_one_bettor",
            ),
        ]

    @property
    def player(self):
        """The tribute or past victor who placed the bet."""
        return self.bettor or self.victor
