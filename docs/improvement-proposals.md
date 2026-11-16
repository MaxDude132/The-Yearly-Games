# Improvement proposals: more interactive, bigger consequences

Status: every proposal is implemented (see the **Implemented** line under each). "Where the game was" below describes the game before this work.
Each proposal has an ID so we can refer to it ("drop 2c", "do 1a first"). Edit the **Decision** line under each one.

## Where the game was (before this work)

- **Decision points:** Bloodbath (rush, grab a pack, flee), meeting someone, alliance offer, sleeper encounter, loyalty or betrayal, berries, traps, final duel. Also sponsor gifts (fallen players) and Gamemaker disasters (any player in the room).
- **Pacing:** `MAX_CHOICES_PER_ROUND = 2` in `games/engine/rounds.py`, about 15 to 20 pop-ups per game. Everyone present chooses only in the Bloodbath and the final duel.
- **Most choices have no memory.** A choice resolves in one roll (`fight()` or `dice.chance()`) and is forgotten. The only things that persist are grudges, alliances, wounds and items.
- **Balance rule:** `test_being_in_the_room_does_not_help_you_win` and the README ("choices change the story, not the odds") require that choices never change who wins. Options are tuned to be roughly equal, so no choice can matter much.
- **Absent players:** the engine rolls weighted dice for them. They get no pop-ups.
- **Not verified:** what the pop-up shows the player (odds, items, history). Proposals in section 4 assume it shows little. To check before starting.

## 1. Choices carry forward

### 1a. Reputation tags
**Implemented**: tags `feared`, `hidden`, `betrayer`, `merciful` and `trusted` (table `TributeTag`), plus life debts (table `Debt`). Trusted: stayed loyal when the loyalty question was asked; a trusted tribute's refused offer can turn into a yes (50%). See `games/engine/state.py`, `combat.py`, `encounters.py`, `rounds.py`.
Per-tribute tags such as `Betrayer`, `Merciful`, `Feared`, `Trusted`, stored like `Grudge`. They change later odds: betraying an ally lowers everyone's alliance acceptance toward you, sparing someone creates a debt that can trigger a rescue later.
- Touches: `games/models.py` (new table), `state.py`, `encounters.py`, new story lines.
- Cost: medium. Risk: needs the balance rule (3a) to change.
- Decision:

### 1b. Callback story lines
**Implemented** (`games/engine/memory.py`): a kill with a killer looks back through the log and tells one of 7 callbacks (betrayal avenged or finished, theft repaid, mercy repaid, former allies, unfinished business, district partners). No dice used.
Lines that fire when an earlier event matters ("X remembers that Y spared them in the Bloodbath"). The log already stores line, a, b, so the engine can look up past entries.
- Touches: `content/fixtures/story.json` (EN and FR), `render.py`, the engine's log lookup.
- Cost: low to medium. Works even without 1a, using only existing grudges and log history.
- Decision:

### 1c. Bloodbath sets your starting condition
**Implemented**: a rusher who kills becomes feared, a fleer is hidden for two nights.
Rushers start `Feared`, pack grabbers keep their item advantage, fleers start `Hidden` (safe from sleeper attacks on night 1).
- Cost: low once 1a exists.
- Decision:

## 2. Bigger, longer choices

### 2a. Multi-step encounters
**Implemented**: a fight that would kill now asks the winner "finish or spare?" (question `mercy`). Sparing wounds the loser, takes one of their items, gives the winner the `merciful` tag and creates a debt (table `Debt`): if the debtor later wins a fight against the benefactor, they let them go once. A merciful tribute can win over a refused alliance (50%). Also: a tribute who spots someone slipping away chooses to follow or let them go (question `chase`, dice 70/30).
A meeting becomes a short chain. Attack, then "finish them or spare them?". Slip away, then "follow or let go?". Spare creates a debt (1a).
- Touches: `encounters.py`, `questions.json`. The replay-from-seed design already supports more questions.
- Cost: medium. Raises pop-up count unless the cap changes (see 2e).
- Decision:

### 2b. Alliance leadership
**Implemented**: the leader is the alliance's deadliest member (no extra data to store). On 30% of mornings with two alliances of 2 or more, a leader decides whether to raid another alliance (question `raid`, dice 40/60). A raid pairs members off for fights. The board marks the leader.
The tribute who formed an alliance decides group choices (where to camp, whether to attack another alliance). Today an alliance is only a number on `Tribute`.
- Touches: `Tribute` model, `encounters.py`, `rounds.py`.
- Cost: high.
- Decision:

### 2c. A daily goal per tribute
**Implemented**: each morning every living tribute gets a goal (`Tribute.goal`): hunt, hide, scavenge or stay with allies. Up to 3 players in the room choose theirs (question `goal`); the dice choose for the rest. The goal shifts the turn weights in `everyones_turn` (`GOAL_EFFECTS` in `rounds.py`) and shows on the board.
At the start of a day, a present player picks: hunt, hide, scavenge, or guard the alliance. It changes the turn weights in `everyones_turn`, so one choice shapes the whole day.
- Cost: medium. Needs a new field per tribute for the current day.
- Decision:

### 2d. Gamemaker targets
**Implemented**: after picking a disaster, a fallen Gamemaker shields one of four random tributes (question `shield`). Living Gamemakers do not shield: they could never shield themselves, which made being in the room a small disadvantage.
The Gamemaker picks an event and also who it hits, or who gets a mercy.
- Touches: `start_of_day` in `rounds.py`, `arena_event` in `events.py`.
- Cost: low to medium.
- Decision:

### 2e. Pop-up budget
**Implemented**: `choice_budget()` in `rounds.py`: 3 pop-ups per round, 4 with 8 or fewer left, 6 with 4 or fewer. Daily goal pop-ups (up to 3 a day) and votes come on top. About 63 choices per game in the simulation with half the tributes in the room (was 28).
- Decision:

## 3. Rebalance so choices can matter

### 3a. Relax the balance rule
**Implemented**: the room-versus-absent test and a new "no Bloodbath option clearly better" test replace the idea that every individual option is equal.
**Accepted** (see "Answers so far"). Replace "every option is equally good" with "being in the room doesn't raise your overall win rate". This permits safe-versus-bold options (low versus high variance) and betrayal that pays off now and costs later. The simulation test must change with it.
- Touches: `games/tests/test_engine.py`, README section "Check the game rules", the tuned constants in `combat.py`, `encounters.py`, `rounds.py`.
- Cost: medium. Prerequisite for the full effect of 1a and 2a.
- Decision:

## 4. Better information in pop-ups

### 4a. Show context before choosing
**Implemented**: the pop-up shows both tributes' condition and items, grudges, same district, alliance size and tributes left. Sponsor gift options show each tribute's condition.
Items carried, whether the other tribute is wounded, grudges between you, alliance size.
- Decision:

### 4b. Plain-word risk hints
**Implemented**: when another tribute is involved, the pop-up says whether a fight would likely go their way, be close, or go against them. Based on weapon, armour, wounds and the feared tag (`strength_bonus` in `combat.py`), never on the dice.
"Likely to win", "risky". No exact numbers.
- Decision:

### 4c. Known locations or setups
**Implemented as rumours** (`beats.py`): each morning the arena announces a rumour (supplies, hunters, storm) before players choose their goal. The goal that fits it works better that day and night, and the goal pop-up says which one. Full map locations were not built: rumours give the same "react to what the story told you" choice without a map.
Tactics chosen against a situation the story already described (for example an ambush at a place mentioned earlier).
- Cost: high. Needs locations in the model.
- Decision:

## 5. Involve the whole room

### 5a. Fallen players do more
**Implemented**: at the start of a day, 20% of the time a fallen player in the room picks one of 4 living tributes to put a bounty on; 2 random non-allies gain a grudge against them. When 2 or more fallen players are in the room, half of the Gamemaker turns become a vote of all of them on the 3 offered disasters (tie: dice).
Beyond sponsor gifts: vote on a twist, or place a bounty that creates grudges.
- Decision:

### 5b. Room votes for absent tributes
**Implemented**: setup has a voter select (nobody, the dead, past winners, both, everyone; default the dead) and a fair-play box (on by default). Past winners are set with a "Won in" year per tribute (a single year field instead of a checkbox plus year: an empty field means not a past winner). One vote per round, on meeting, alliance_offer, sleeper, loyalty and mercy. Each voter gets their own pop-up ("Vote 2 of 3, for X"), so the existing one-answer-per-question replay works unchanged. Ties go to the dice (weighted by the usual odds).
When a tribute not in the room faces a big decision, a group of players votes instead of the dice.
**Kept, with a configurable voter group** (setting chosen at setup, see "Answers so far"):
- **Past winners:** tributes marked at setup as having won an earlier Yearly Games, with the year. They are playing in this game. No identity across games needed.
- **The dead:** tributes already eliminated in this game.
- **Past winners and the dead.**
- **Everyone** in the room.
Absent tributes are the only ones who get voted for. The vote replaces the weighted dice for them, with the vote result shown as a pop-up to the voters.
Fairness risk: living voters can steer an absent rival or friend. Only the dead are out of the running. Past winners are alive and competing, so "past winners" and "everyone" carry the same risk. Guard: a second setting, on by default, stops voters from voting on decisions involving their own tribute or alliance. It can be turned off. The simulation test must cover each setting.
Ties go to the dice. An empty voter group falls back to the weighted dice.
Setup also gains the past-winner fields (a checkbox and a year per name), stored on `Tribute`.
- Touches: setup screen and `Game` model (the setting), `Decision` in `state.py` (a decision with several voters), `services.py` and `views.py` (collecting several answers per decision), questions fixtures.
- Cost: high. The replay-from-seed design stores one answer per question, so a vote needs several saved answers per decision and a rule for ties.
- Decision: keep, configurable.

### 5c. Betting round
**Implemented**: before each night (not the final duel) a "Bets for the night" panel lets each player in the room pick a tribute. The Continue button sends the bets (table `Bet`). 3 points for the first to fall, 1 for falling later that night. Scores show on the board and in the recap.
Before each night, everyone picks who they think dies first. Keeps players engaged during other players' turns. Needs a score or recap to pay off.
- Decision:

## 6. Story shape

### 6a. Acts
**Implemented** (`beats.py`): two acts on top of the feast. With 12 left (once someone has killed), the Gamemakers name the deadliest tribute, who becomes feared. With 4 left, the story names the final four and recalls what links each pair: life debts, alliances, mutual grudges, betrayals.
Fixed beats (opening, middle, feast, finale) whose content depends on earlier choices (who holds the best weapon, who has allies, who is `Feared`).
- Decision:

### 6b. End-of-game recap
**Implemented**: after the winner line: the victor's kill count, the deadliest tribute, the turning points (betrayals, mercy, debts repaid, feared, shields, bounties, callbacks, the victor's kills) and the bet ranking.
Shows the decisive moments, for example "the choice that changed the game", picked from the log.
- Cost: low to medium. Independent of everything else.
- Decision:

## Suggested order

1. 4a context in pop-ups, and 1b callback lines (no balance change needed).
2. 3a relax the balance rule, then 1a reputation tags and 1c.
3. 2a multi-step encounters with 2e, then 2d.
4. 2c, 5a to 5c, 6a and 6b as wanted. 2b and 4c last.

## Answers so far

1. **Longer game is fine.** The 15 to 20 pop-up budget is no longer a constraint. 2e (pop-up budget) is accepted in principle: raise `MAX_CHOICES_PER_ROUND` or make it depend on the moment.
2. **Choices may change a tribute's odds.** 3a is accepted: individual options no longer have to be equally good, so safe-versus-bold choices and betrayal that pays now and costs later are allowed.
3. **No edge for being in the room.** The aggregate rule stays: a tribute whose player is in the room must not win more often than an absent one.

### What this means for the design

- **The simulation test is rewritten, not removed.** `test_being_in_the_room_does_not_help_you_win` keeps its purpose (room versus absent win rate) but must stop requiring that each option be equal. The "every tribute wins about equally often" check also stays.
- **The dice player for absent tributes becomes the baseline.** If a choice is genuinely better or worse, the weights used for absent tributes (e.g. `[45, 20, 35]` in `face_to_face`) must produce play of similar quality to a typical human. Otherwise the room gains or loses an edge by design. Tune with the simulation, using several human-like strategies (always bold, always safe, mixed) against the dice.
- **Keep bold versus safe symmetric on average.** Make bold options high variance and safe options low variance, with similar average results, so no single strategy wins.
- **5b (voting for absent tributes) is kept and configurable.** The voter group (past winners, the dead, both, or everyone) is a setting. Tests must pass for every setting.
- **1a (reputation) must be symmetric.** Tags apply to every tribute whether present or absent, driven only by what happened in the story.

4. **Priorities:** story richness, tension and risk, and social play all matter. Social play matters most.
5. **Order:** follow the suggested order above.
6. **5b:** keep it, with a setting to choose who votes: past winners, the dead, past winners and the dead, or everyone.
7. **Past winners** are set up when the game is created, each with the year they won. No stored player profiles or history across games. They play as tributes.
8. **Order:** 5a and 5b stay in step 4, to be done later.
9. **Ties and empty groups:** a tied vote goes to the dice. If the voter group is empty (nobody dead yet, no past winners), the weighted dice decide.

10. **Conflict rule is a setting.** "Voters can't vote on decisions involving their own tribute or alliance" is a configurable option, on by default (the fair setting). Turning it off is allowed; the game does not stop people from making it unfair. Tests run with it on for every voter group.
11. **A past win is flavour only.** The year appears in intro and callback lines (for example "the 2023 victor"). It has no gameplay effect.
12. **One past-winning year per person.** Setup shows a "past winner" checkbox next to each name, with a single year field that appears when ticked.

## Later change: past victors are not tributes

Past victors are now their own list at setup (table `PastVictor`: name, year, photo, here), outside the 24 tributes. The "Won in" field on tributes is gone. In the engine they are `Victor` objects in `Arena.victors`.
- **Sponsor gifts** come from the past victors in the room (question `victor_sponsor`, story line `item.from_victor`). When no past victor is in the room, the fallen in the room send them, as before.
- **Disasters** are chosen only by the fallen in the room (before, any player in the room could be the Gamemaker).
- **Votes:** the "past winners" voter groups now mean the past victors in the room. They have no tribute or alliance, so fair play never keeps them out. The setting values (`past_winners`...) are unchanged.
- This replaces answers 7, 11 and 12 below.

## Open questions

None at the moment. Next step: pick the first items from the suggested order and turn them into a concrete implementation plan (data model changes, files, tests).

## Balance after all proposals

Measured by `make test` (4000 simulated games per habit, half the tributes in the room):
- Votes off: players in the room win 48.1% (random answers), 48.8% (always first option), 48.2% (always middle), 48.5% (always last). The test allows 46% to 54%.
- Votes on, fair play on: 50.3% (the dead), 51.6% (past winners), 52.2% (both), 51.8% (everyone).
- Bloodbath options win about equally: 33.9 / 33.5 / 32.5%.
- A gap of about 1.5 points against the room remains with votes off, whatever the habit, so it is structural rather than tied to one choice. Removing the living Gamemaker's shield closed part of it. The room never has an edge.
