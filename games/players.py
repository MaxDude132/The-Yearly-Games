"""Players on their own phones: joining with the QR code, taking a seat, and whose turn it is.

A seat is a tribute or a past victor. Taking one stores a random token on that row and the same
token in the phone's session, under the game's join code. Nothing else identifies a phone.
"""

import secrets

import segno
from django.db.models import F

from games import roster as roster_tools
from games.engine.state import Victor
from games.models import Game

TRIBUTE, VICTOR = "tribute", "victor"
SESSION_KEY = "seats"  # in the phone's session: {join code: phone token}


def join_code(game):
    """The game's join code, made the first time it is needed."""
    if not game.join_code:
        game.join_code = secrets.token_urlsafe(6)  # 8 characters: hard to guess, short in a link
        game.save(update_fields=["join_code"])
    return game.join_code


def qr_svg(url):
    """The QR code for a link, as inline SVG, light squares on the page's dark background."""
    return segno.make(url, error="m").svg_inline(scale=6, border=2, dark="#101913", light="#ece6d3")


def bump(game):
    """Tells open pages that something changed (see Game.version)."""
    Game.objects.filter(pk=game.pk).update(version=F("version") + 1)


# ---------- seats ----------


def seat_rows(game, kind):
    return game.victors if kind == VICTOR else game.tributes


def my_seat(game, session):
    """(kind, row) of the seat this phone holds in this game, or (None, None)."""
    token = session.get(SESSION_KEY, {}).get(game.join_code)
    if not token:
        return None, None
    for kind in (TRIBUTE, VICTOR):
        row = seat_rows(game, kind).filter(phone_token=token).first()
        if row:
            return kind, row
    return None, None  # the host disconnected this phone


def free_seats(game, kind):
    return list(seat_rows(game, kind).filter(phone_token="").order_by("position"))


def take_seat(game, session, kind, position, name, photo=None):
    """Gives this phone a free seat and names it. Returns False if the seat is gone or already taken.

    The player is marked as in the room, except while a question is open: changing who is in the
    room then would change how the round replays (see services.resume)."""
    row = seat_rows(game, kind).filter(position=position, phone_token="").first()
    if row is None:
        return False
    leave_seat(game, session)
    token = secrets.token_hex(16)
    row.phone_token = token
    row.name = name.strip()[: roster_tools.NAME_MAX_LENGTH] or row.name
    if game.round_seed is None:
        row.present = True
    roster_tools.save_photo(row, photo)
    row.save()
    seats = session.get(SESSION_KEY, {})
    seats[game.join_code] = token
    session[SESSION_KEY] = seats  # a new dict, so the session knows to save it
    return True


def leave_seat(game, session):
    """This phone gives its seat back. The tribute stays as it is (name, who is in the room)."""
    kind, row = my_seat(game, session)
    if row:
        row.phone_token = ""
        row.save(update_fields=["phone_token"])
    seats = session.get(SESSION_KEY, {})
    seats.pop(game.join_code, None)
    session[SESSION_KEY] = seats


def release(game, kind, position):
    """The host disconnects whichever phone holds this seat."""
    seat_rows(game, kind).filter(position=position).update(phone_token="")


# ---------- turns ----------


def decides(decision, kind, row):
    """True if this seat is the one asked to answer this question."""
    if decision is None or row is None:
        return False
    is_victor = isinstance(decision.tribute, Victor)
    return is_victor == (kind == VICTOR) and decision.tribute.id == row.position
