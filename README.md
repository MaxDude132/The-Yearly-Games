# The Yearly Games

A Hunger Games-style simulator for our yearly game with friends. 24 tributes, one random victor, and the people in the room make choices that change the story. English and French.

**Play it:** https://spendrax.github.io/The-Yearly-Games/

## How a game works

1. Type the names in district order: tributes 1 & 2 are District 1, 3 & 4 District 2, and so on. Tap the circle next to a name to add a photo.
2. Tick **here** for everyone in the room. You can change this during the game on the tribute board.
3. Tap through the rounds: the Bloodbath, then Day 1, Night 1, Day 2...
4. When a player in the room has a choice to make, a pop-up shows their name. Pass the phone or tap for them. The app decides for everyone who isn't there.

What makes each game different:

- **Districts:** partners start as friends (allied), rivals (they hate each other) or strangers.
- **Items:** weapons, armour, ointments, food, rope, gear from the Cornucopia, sponsors and the feast. The board shows who has what. Items help most of the time, not always: weapons break, medicine can fail, food can be spoiled.
- **Alliances and grudges:** tributes team up, betray each other late in the game, and hunt the people who hurt their friends.
- **Fallen players keep playing:** dead players in the room send sponsor gifts, and any player in the room may be handed the Gamemaker controls to pick the disaster that hits everyone.
- **Final duel:** the last two each pick a tactic (charge, ambush, wait). It works like rock-paper-scissors: the better tactic gives an edge, but luck decides.
- **Save:** the game saves after every round in this browser. Close the app and pick up later.

## Install it

Open the link above on your phone or computer.

- **Android / Chrome / Edge:** tap **Install app** at the top of the setup screen.
- **iPhone / iPad:** in Safari, tap Share, then **Add to Home Screen** (the button in the app shows this too).

## The code

Plain HTML, CSS and JavaScript modules. No build step, nothing to install.

```
index.html              the page
manifest.webmanifest    app name, colours and icons (for installing)
sw.js                   service worker: install + works offline
version.json            bump this number when you publish an update
css/style.css           all the styles
icons/                  the logo (icon.svg) and its PNG sizes

js/
  utils/random.js       dice rolls: random numbers, picks, shuffles, weighted choices
  data/                 everything that is text or a list, no logic
    items.js            the items and their kinds
    arena-events.js     disasters the Gamemakers can unleash
    story.js            every story sentence, in English and French
    ui-text.js          button and screen labels
  engine/               the game rules (no screen code, so the test can run them)
    state.js            the game state, saving/loading, shared rules (kill, grudges, who decides)
    text.js             fills story templates with names and items
    combat.js           how a fight is decided
    events.js           arena disasters, the feast, accidents, berries, traps, using items
    encounters.js       two tributes meet: fights, alliances, sleeping targets, betrayal
    rounds.js           the Bloodbath, each day and night, the final duel
  ui/                   everything on screen
    app.js              starts the app, button actions, saving
    views.js            builds the HTML for each screen
    install.js          the Install app button
    photos.js           shrinks photos so they fit in storage
    storage.js          reads and writes browser storage
    updates.js          the Update available button (compares version.json)

test/simulate.test.js   plays 5000 games and checks they always end fairly
```

### Run it on your computer

Modules need a web server (opening `index.html` directly won't work):

```
python -m http.server
```

Then open http://localhost:8000.

### Check the game rules

```
npm test
```

This plays 5000 games with random answers and checks that every game ends with exactly one winner, no story line is missing text, and every tribute wins about equally often. It also checks that players in the room don't win more often than absent ones, whatever options they tend to pick: choices change the story, not the odds.

### Publish an update

Push your changes and add 1 to the number in `version.json`. Anyone with the app open sees an **Update available** button within a few minutes (or as soon as they come back to the app). Tapping it reloads the new version. The game is saved between rounds, so the button waits until the current round ends.

### Change the game

- **New story lines:** add an `[english, french]` pair to the right list in `js/data/story.js`.
- **New items:** add a line to `js/data/items.js`.
- **New disasters:** add an entry to `js/data/arena-events.js` (`counter` is the item kind that can save you).
- **Odds:** the numbers in `js/engine/` (for example `[45, 20, 35]` means 45% attack, 20% alliance, 35% slip away).
