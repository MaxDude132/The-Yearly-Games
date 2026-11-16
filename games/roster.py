"""Editing the list of tributes on the setup screen."""

import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from games.models import Game, PastVictor, Tribute

NAME_MAX_LENGTH = Tribute._meta.get_field("name").max_length
FIRST_YEAR, LAST_YEAR = 1900, 2200  # a past victor's year outside this range is ignored
PHOTO_SIZE = 192  # pixels: a small square is plenty for a round avatar
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


def photo_to_small_square(uploaded):
    """A JPEG of the uploaded photo, cropped to a centred square. None if it is not a readable image."""
    if uploaded.size > MAX_UPLOAD_BYTES:
        return None
    try:
        image = ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
        square = ImageOps.fit(image, (PHOTO_SIZE, PHOTO_SIZE))
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    buffer = BytesIO()
    square.save(buffer, "JPEG", quality=80)
    return ContentFile(buffer.getvalue())


def save_photo(row, uploaded):
    """Replaces a row's photo with the uploaded one. Not an image: the old photo is kept."""
    photo = photo_to_small_square(uploaded) if uploaded else None
    if photo:
        row.photo.delete(save=False)
        row.photo.save(f"{uuid.uuid4().hex}.jpg", photo, save=False)


def save_roster(game, post, files):
    """Applies the setup form: tributes and past victors (names, who is here, photos) and the vote settings.
    Tribute fields are named name-3, here-3, photo-3; past victor fields victor-name-3, victor-here-3..."""
    rows = list(game.tributes.order_by("position"))
    for row in rows:
        row.name = post.get(f"name-{row.position}", row.name).strip()[:NAME_MAX_LENGTH]
        row.present = f"here-{row.position}" in post
        save_photo(row, files.get(f"photo-{row.position}"))
    Tribute.objects.bulk_update(rows, ["name", "present", "photo"])

    victors = list(game.victors.order_by("position"))
    for row in victors:
        prefix = f"victor-{{}}-{row.position}"
        row.name = post.get(prefix.format("name"), row.name).strip()[:NAME_MAX_LENGTH]
        row.present = prefix.format("here") in post
        row.year = parse_year(post.get(prefix.format("year"), ""))
        save_photo(row, files.get(prefix.format("photo")))
    PastVictor.objects.bulk_update(victors, ["name", "present", "year", "photo"])

    voters = post.get("voters", game.voters)
    if voters in Game.Voters.values:
        game.voters = voters
    game.no_conflict_votes = "no_conflict_votes" in post
    game.save(update_fields=["voters", "no_conflict_votes", "updated_at"])


def parse_year(text):
    """The year a past victor won the Games, or None if the field is empty or not a sensible year."""
    text = text.strip()
    if not text.isdigit():
        return None
    year = int(text)
    return year if FIRST_YEAR <= year <= LAST_YEAR else None


def add_tribute(game):
    Tribute.objects.create(game=game, position=game.tributes.count())


def remove_tribute(game, position):
    """Removes a tribute and closes the gap, so positions (and so districts) stay 0, 1, 2..."""
    remove_and_close_gap(game.tributes, position)


def add_victor(game):
    PastVictor.objects.create(game=game, position=game.victors.count())


def remove_victor(game, position):
    remove_and_close_gap(game.victors, position)


def remove_and_close_gap(rows, position):
    """Deletes the row at position and moves the rows after it up by one, so positions stay 0, 1, 2..."""
    removed = rows.filter(position=position).first()
    if removed is None:
        return
    removed.photo.delete(save=False)
    removed.delete()
    for row in rows.filter(position__gt=position).order_by("position"):
        row.position -= 1
        row.save(update_fields=["position"])
