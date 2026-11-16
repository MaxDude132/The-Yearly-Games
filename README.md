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
- **Reputation and memory:** killing three times makes a tribute *feared* (a small fighting bonus, but others go looking for them). Rushing the Cornucopia and killing makes you feared too. Fleeing the Bloodbath leaves you *hidden* for the first two nights, so sleepers are sometimes walked past. Betraying an ally makes you a *betrayer*: later alliances with you can fall through. When a tribute kills someone they have history with, the story says so (betrayal, theft, mercy, old alliance, a wound, same district). The pop-up also shows how the tributes involved are doing.
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
make docker-run     # the production image with Postgres and a local S3 server, on http://localhost:8160
```

Locally the database is SQLite (`db.sqlite3`) and photos go to `media/`, nothing to install. Production uses Postgres and an S3 bucket.

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
    state.py              tributes, the story entries, shared rules (kill, grudges, tags, who decides)
    memory.py             looks back through the story when someone is killed and tells a callback line
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
compose.yaml              local Postgres and S3 server, for `make test-postgres` and `make docker-run`
scripts/                  predeploy.sh (Railway runs it before each deploy), create_local_bucket.py
Dockerfile                the production image Railway builds
.railway/railway.py       the Railway project as code: the web service, its Postgres and the photo bucket
.github/workflows/ci.yml  CI: lint and tests on every push and pull request, then the Railway apply (main)
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
`make test` plays 5000 games with random answers and checks that every game ends with exactly one winner, no story line is missing text, and every tribute wins about equally often. It also checks that players in the room don't win more often than absent ones, whatever options they tend to pick, and that rushing, grabbing a pack and fleeing the Bloodbath lead to a win about equally often. Choices can change a tribute's odds (reputation, items), but the dice that play absent tributes must play about as well as a person. Other tests cover the pages, the questions that pause a round, photos and languages.

### Deploying (Railway)
The Railway project is described in `.railway/railway.py` (Railway Infrastructure as Code, Python authoring, beta). It declares three resources:
- the `web` service, built from this repository's `main` branch with the `Dockerfile`;
- the `postgres` database;
- the `photos` bucket, private, in the `iad` region (US East);
- the `postgres-volume` disk (50 GB), and the custom domain `yearlygames.maximetoussaint.com`.

The service gets the database URL and the bucket credentials as references, so Railway fills them in. Railway does not read the file during deploys: the CLI compares it with the project and applies the difference after you confirm. `make test` checks that the file compiles to the expected settings, without contacting Railway.

The build installs the dependencies and builds the CSS, translations and static files. Before each deploy goes live, `scripts/predeploy.sh` migrates the database and reloads the game content. Gunicorn then serves the app, and Railway waits for `/health/` before sending traffic to the new version.

The container keeps nothing on disk: game data is in Postgres and photos are in the bucket, so the service needs no volume. The page links each photo with a signed URL that expires after an hour, because Railway buckets are always private. Static files (CSS, icons) are served by the app itself (WhiteNoise).

**Once** (needs the [Railway CLI](https://docs.railway.com/cli), logged in with `railway login`):
1. `make railway-init` creates the `the-yearly-games` project and links this folder to it.
2. Check `BUCKET_REGION` in `.railway/railway.py` (`sjc`, `iad`, `ams` or `sin`). A bucket's region cannot change after it is created.
3. `make infra-plan` shows what will be created: the service, the database and the bucket. `make infra-apply` creates them after you confirm.
4. Set the one secret. The file declares it with `preserve()`, so its value stays in Railway and never in git, and piping it keeps it out of your shell history:
   ```
   uv run python -c "import secrets; print(secrets.token_urlsafe(50))" | railway variable set --service web --stdin DJANGO_SECRET_KEY
   ```
   Production refuses to start without it, so the first deploy after `make infra-apply` fails until this is set. Setting it starts a new deploy.

The site lives at **https://yearlygames.maximetoussaint.com**. `.railway/railway.py` declares the domain (`DOMAIN`) and sets `DJANGO_ALLOWED_HOSTS` from it. Railway configuration cannot register a new custom domain: to change the address, add it in the dashboard, run `railway config pull`, and update `DOMAIN`. The domain routes to the port the file pins with `PORT` and that gunicorn binds. A `*.up.railway.app` domain is optional (`railway domain --service web`); generated domains are not part of the IaC file, and the app allows one automatically.

Later changes to the infrastructure: edit `.railway/railway.py` and push to `main`. CI applies it (see below). To preview first, run `make infra-plan`. All the `infra-*` targets refuse to run unless this folder is linked to `the-yearly-games`. That matters because a parent folder (even your home folder) may be linked to another project, and plan and apply act on whatever project is linked.

**CI** (`.github/workflows/ci.yml`): every push to any branch and every pull request runs two jobs in parallel, `make lint` and `make test`. On a push to `main`, once both pass, a third job runs `make infra-apply-ci`, which applies `.railway/railway.py` to Railway without asking. A push that changes nothing in the file applies nothing. The apply refuses destructive changes, such as removing the bucket, the database or a variable, so the run fails instead. Apply those by hand with `make infra-apply`, which shows them and asks. Runs never overlap: a new push waits for the running apply.

To set it up once, after `make railway-init`:
1. In Railway, open the project's **Settings > Tokens** and create a project token for the `production` environment.
2. In GitHub, add it as the repository secret `RAILWAY_TOKEN` (**Settings > Secrets and variables > Actions**).
3. Optional: under **Settings > Environments > railway-production** (created on the first run), add a required reviewer if you want to approve each apply.

Production refuses to start without the Postgres URL or the bucket name, so a missing variable fails the deploy instead of losing data. The app works with any S3-compatible bucket, through the same `AWS_*` variables, if you ever move the photos elsewhere.

To try the production image locally: `make docker-run` (http://localhost:8160) starts Postgres, a local S3 server ([RustFS](https://rustfs.com)) and the image, as on Railway. `make docker-down` stops them.
