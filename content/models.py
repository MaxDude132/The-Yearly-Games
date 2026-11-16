"""Everything the game says or hands out, in every language.

Each thing is a parent row with a unique key, plus one translation row per language.
The rows come from content/fixtures/*.json (see `make content`). Every model has a natural key,
so reloading the fixtures updates rows instead of duplicating them.
"""

from django.conf import settings
from django.db import models


class Kind(models.TextChoices):
    WEAPON = "weapon", "Weapon"  # better odds in a fight, can break
    ARMOR = "armor", "Armor"  # can save you from a killing blow once
    HEALING = "healing", "Healing"  # can close a wound (or do nothing)
    FOOD = "food", "Food"  # gives strength (or is spoiled)
    TRAP = "trap", "Trap"  # rope, net, wire: lets you set snares and traps
    GEAR = "gear", "Gear"  # matches, sleeping bag... helps against some arena events


def language_field():
    return models.CharField(max_length=8, choices=settings.LANGUAGES)


# ---------- managers: look rows up by natural key ----------


class KeyManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)


class StoryLineManager(models.Manager):
    def get_by_natural_key(self, group, variant):
        return self.get(group=group, variant=variant)


class QuestionOptionManager(models.Manager):
    def get_by_natural_key(self, question_key, position):
        return self.get(question__key=question_key, position=position)


class TranslationManager(models.Manager):
    """Finds a translation by the natural key of its parent plus the language."""

    parent_field = ""  # set by translation_manager()

    def get_by_natural_key(self, *key):
        *parent_key, language = key
        parent_model = self.model._meta.get_field(self.parent_field).related_model
        parent = parent_model._default_manager.get_by_natural_key(*parent_key)
        return self.get(**{self.parent_field: parent, "language": language})


def translation_manager(parent_field):
    """A manager for a translation model whose parent is the foreign key named parent_field."""
    manager_class = type("TranslationManager", (TranslationManager,), {"parent_field": parent_field})
    return manager_class()


# ---------- things the game hands out or asks ----------


class Item(models.Model):
    key = models.SlugField(max_length=60, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)

    objects = KeyManager()

    class Meta:
        ordering = ["key"]

    def natural_key(self):
        return (self.key,)

    def __str__(self):
        return self.key


class ArenaEvent(models.Model):
    """A disaster the Gamemakers can unleash. The feast is one too, but it plays out differently.

    Its announcement is the story line in the group "arena_event.<key>".
    """

    key = models.SlugField(max_length=60, unique=True)
    # The kind of item that can save a tribute from this event. Empty for the feast.
    counter = models.CharField(max_length=10, choices=Kind.choices, blank=True)
    is_feast = models.BooleanField(default=False)

    objects = KeyManager()

    class Meta:
        ordering = ["key"]

    def natural_key(self):
        return (self.key,)

    def __str__(self):
        return self.key


class StoryLine(models.Model):
    """One sentence the arena can tell. Lines in the same group are variations: one is picked at random.

    Placeholders in the text: {a} the tribute acting, {b} the other tribute, {item} an item,
    {n} a number, {names} a list of names, {sponsor} a fallen player sending a gift.
    """

    group = models.CharField(max_length=80)
    variant = models.PositiveSmallIntegerField(default=0)

    objects = StoryLineManager()

    class Meta:
        ordering = ["group", "variant"]
        constraints = [models.UniqueConstraint(fields=["group", "variant"], name="unique_story_line")]

    def natural_key(self):
        return (self.group, self.variant)

    def __str__(self):
        return f"{self.group}#{self.variant}"


class Question(models.Model):
    """A pop-up decision for a player in the room. The order of its options matters to the engine."""

    key = models.SlugField(max_length=60, unique=True)

    objects = KeyManager()

    class Meta:
        ordering = ["key"]

    def natural_key(self):
        return (self.key,)

    def __str__(self):
        return self.key


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    position = models.PositiveSmallIntegerField()

    objects = QuestionOptionManager()

    class Meta:
        ordering = ["question", "position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "position"], name="unique_question_option")
        ]

    def natural_key(self):
        return (*self.question.natural_key(), self.position)

    natural_key.dependencies = ["content.question"]

    def __str__(self):
        return f"{self.question}#{self.position}"


# ---------- translations: one row per parent and language ----------


class ItemTranslation(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="translations")
    language = language_field()
    name = models.CharField(max_length=120)

    objects = translation_manager("item")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["item", "language"], name="unique_item_translation")]

    def natural_key(self):
        return (*self.item.natural_key(), self.language)

    natural_key.dependencies = ["content.item"]


class ArenaEventTranslation(models.Model):
    event = models.ForeignKey(ArenaEvent, on_delete=models.CASCADE, related_name="translations")
    language = language_field()
    name = models.CharField(max_length=120)

    objects = translation_manager("event")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "language"], name="unique_event_translation")]

    def natural_key(self):
        return (*self.event.natural_key(), self.language)

    natural_key.dependencies = ["content.arenaevent"]


class StoryLineTranslation(models.Model):
    line = models.ForeignKey(StoryLine, on_delete=models.CASCADE, related_name="translations")
    language = language_field()
    text = models.TextField()

    objects = translation_manager("line")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["line", "language"], name="unique_line_translation")]

    def natural_key(self):
        return (*self.line.natural_key(), self.language)

    natural_key.dependencies = ["content.storyline"]


class QuestionTranslation(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="translations")
    language = language_field()
    text = models.TextField()

    objects = translation_manager("question")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["question", "language"], name="unique_question_translation")
        ]

    def natural_key(self):
        return (*self.question.natural_key(), self.language)

    natural_key.dependencies = ["content.question"]


class QuestionOptionTranslation(models.Model):
    option = models.ForeignKey(QuestionOption, on_delete=models.CASCADE, related_name="translations")
    language = language_field()
    label = models.CharField(max_length=120)

    objects = translation_manager("option")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["option", "language"], name="unique_option_translation")
        ]

    def natural_key(self):
        return (*self.option.natural_key(), self.language)

    natural_key.dependencies = ["content.questionoption"]
