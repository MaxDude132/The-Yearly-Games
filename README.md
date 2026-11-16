# The Yearly Games
A Hunger Games-style simulator for our yearly game with friends. 24 tributes, one random victor, and the people in the room make choices that change the story. English and French.

## How a game works
1. Type the names in district order: tributes 1 & 2 are District 1, tributes 3 & 4 District 2, and so on. Tap the circle next to a name to add a photo.
2. Tick **here** for everyone in the room. You can change this during the game on the tribute board.
3. Tap through the rounds: the Bloodbath, then Day 1, Night 1, Day 2...
4. When a player in the room has a choice to make, a pop-up shows their name. Pass the phone or tap for them. The app decides for everyone who isn't there.

What makes each game different:
- **Districts:** partners start as friends (allied), rivals (they hate each other) or strangers.
- **Items:** weapons, armour, ointments, food, rope, gear from the Cornucopia, sponsors and the feast. Items help most of the time, not always: weapons break, medicine can fail, food can be spoiled.
- **Alliances and grudges:** tributes team up, betray each other late in the game, and hunt the people who hurt their friends.
- **Fallen players keep playing:** dead players in the room send sponsor gifts, and any player in the room may be handed the Gamemaker controls to pick the disaster that hits everyone.
- **Final duel:** the last two each pick a tactic (charge, ambush, wait). It works like rock-paper-scissors: the better tactic gives an edge, but luck decides.
- **Save:** the game is saved on the server after every round and belongs to your browser (a session cookie). Close the page and pick up later.

## Run it
Needs `uv` (Python 3.13). No Node: Tailwind runs as a standalone binary that `make install` downloads. Everything goes through the Makefile (`make help` lists it all).

```
make setup          # dependencies, CSS, translations, database, game content
make dev            # http://localhost:8150, rebuilds the CSS and reloads the browser on every change
make run            # the same server without the watcher
make test           # includes thousands of simulated games
make test-postgres  # the same tests on Postgres in Docker (port 5452), like production
```

Locally the database is SQLite (`db.sqlite3`), nothing to install. Production uses Postgres.

## The code
Django, with the game rules in plain Python (no database access inside the rules). The UI is Tailwind CSS v4 through django-tailwind.

```
config/                   settings and root URLs
content/                  everything the game says or hands out, in every language
  models.py               items, arena events, story lines, questions: a parent row + one translation row per language
  fixtures/*.json         the content itself (one entry per line); `make content` loads it
games/
  engine/                 the game rules, ported from the old JavaScript
    dice.py               random numbers, picks, shuffles, weighted choices
    catalogue.py          which items, events, lines and questions exist (no text)
    state.py              tributes, the story entries, shared rules (kill, grudges, who decides)
    combat.py             how a fight is decided
    events.py             arena disasters, the feast, accidents, berries, traps, using items
    encounters.py         two tributes meet: fights, alliances, sleeping targets, betrayal
    rounds.py             the Bloodbath, each day and night, the final duel
  models.py               a saved game: tributes, items, grudges, story, pending answers
  services.py             loads/saves a game and runs a round (see below)
  render.py               turns story entries into text in the viewer's language
  roster.py               setup screen: names, who is here, photos
  views.py, urls.py       the pages and actions
  styles.py               Tailwind classes chosen in Python (story line colours, status pills)
  templates/              HTML with Tailwind classes
  static/games/           a little JavaScript (press feedback, scrolling), icons
theme/                    the django-tailwind app
  static_src/src/styles.css  Tailwind input: colours, fonts, animations, the button style
locale/fr/                French interface text (buttons, labels)
compose.yaml              a local Postgres for `make test-postgres` and `make docker-run`
Dockerfile, railway.toml  the production image and its Railway settings (see Deploying)
gunicorn.conf.py          the production web server
```

### Styling
Templates use Tailwind utility classes. Colours and fonts are theme values in `theme/static_src/src/styles.css` (`bg-panel`, `text-gold`, `font-display`...). `make css` builds `theme/static/css/dist/styles.css`, which the `{% tailwind_css %}` tag in `base.html` links. The built file is not committed; the Docker build makes it. Tailwind only generates classes it finds in the templates, `app.js` and the Python files in `games/`. Write classes out in full there, never piece them together (`"text-" + colour` is invisible to Tailwind).

### How a question pauses a round
A web request cannot wait for a player to tap. So a round is replayed from its start each time: the same dice seed plus the answers saved so far give the same story, up to the first question with no answer. Nothing of an unfinished round is written to the story; when the last answer arrives, the round is saved. Answers are discarded once the round is saved.

### Languages
- **Game content** (story lines, item names, questions, events) is in the database, loaded from `content/fixtures/`. The story is saved as "which line, about whom", never as text, so each viewer reads it in their own language.
- **Interface text** (buttons, labels) is in `locale/fr/LC_MESSAGES/django.po`. Run `make messages` after editing it.
- Each language needs every line translated; a test checks it.

### Change the game
- **New story lines:** add a `content.storyline` entry (group + variant) and one `content.storylinetranslation` per language in `content/fixtures/story.json`, then `make content`. Several variants in one group are picked at random.
- **New items:** add an item and its translations to `content/fixtures/items.json`.
- **New disasters:** add to `content/fixtures/arena_events.json` (`counter` is the item kind that can save you) and add its announcement as a story line in the group `arena_event.<key>`.
- **Odds:** the numbers in `games/engine/` (for example `[45, 20, 35]` means 45% attack, 20% alliance, 35% slip away).

### Check the game rules
`make test` plays 5000 games with random answers and checks that every game ends with exactly one winner, no story line is missing text, and every tribute wins about equally often. It also checks that players in the room don't win more often than absent ones, whatever options they tend to pick: choices change the story, not the odds. Other tests cover the pages, the questions that pause a round, photos and languages.

### Deploying (Railway)
Railway builds the `Dockerfile` and follows `railway.toml`. The build installs the dependencies and builds the CSS, translations and static files. Before each deploy goes live, `scripts/predeploy.sh` migrates the database and reloads the game content. Gunicorn then serves the app, and Railway waits for `/health/` before sending traffic to the new version.

One-time setup in the Railway dashboard:
1. Create a project with a **Postgres** database and a service from this GitHub repo.
2. In the service **Variables**:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (a reference to the database)
   - `DJANGO_SECRET_KEY` = a long random string, e.g. from `uv run python -c "import secrets; print(secrets.token_urlsafe(50))"`
   - `DJANGO_ALLOWED_HOSTS` = your custom domain, if you add one. The Railway domain is allowed automatically.
3. Add a **Volume** to the service, mounted at `/data`. Uploaded photos live there (`/data/media`); without a volume they vanish on each deploy.
4. In **Settings > Networking**, generate a domain.

The app serves its own static files (WhiteNoise) and photos (Django), so it needs no separate web server. Railway allows only one deploy at a time on a service with a volume, so each deploy causes a few seconds of downtime.

To try the production image locally against the Docker Postgres: `make docker-run` (http://localhost:8160).
