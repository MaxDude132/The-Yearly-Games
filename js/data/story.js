// Every sentence the arena can tell, in English and French: [english, french].
// Placeholders: {a} the tribute acting, {b} the other tribute, {item} an item,
// {n} a number, {names} a list of names, {sponsor} a fallen player sending a gift.
// Lists of several pairs are variations: one is picked at random.

export const PHASES = {
  bloodbath: ['The Bloodbath', 'Le bain de sang'],
  day: ['Day {n}', 'Jour {n}'],
  night: ['Night {n}', 'Nuit {n}'],
  cannons: ['{n} cannon shot(s): {names}.', '{n} coup(s) de canon : {names}.'],
  noCannons: ['No cannon. Everyone lives, for now.', "Aucun coup de canon. Tout le monde survit, pour l'instant."],
  winner: ['{a} wins the Games. This year belongs to {a}.', '{a} remporte les Jeux. Cette année appartient à {a}.'],
  alliancesShatter: ['Only allies remain. Every alliance breaks.', 'Il ne reste que des alliés. Toutes les alliances éclatent.'],
};

// District partners (tributes 1 & 2, 3 & 4...) start as friends, rivals or strangers.
export const DISTRICT_BONDS = [
  ['District {n}: {a} and {b} are friends and enter as a team.', "District {n} : {a} et {b} s'entendent bien et entrent en équipe."],
  ['District {n}: {a} and {b} cannot stand each other.', 'District {n} : {a} et {b} ne peuvent pas se sentir.'],
  ['District {n}: {a} and {b} barely know each other.', 'District {n} : {a} et {b} se connaissent à peine.'],
];

export const BLOODBATH = {
  grabsWeapon: ['{a} sprints to the Cornucopia and grabs {item}.', "{a} fonce vers la Corne d'abondance et attrape {item}."],
  tooLate: ['{a} reaches the Cornucopia too late. Nothing left.', "{a} arrive trop tard à la Corne d'abondance. Il ne reste rien."],
  grabsPack: ['{a} snatches a pack on the edge: inside, {item}.', '{a} attrape un sac en bordure : dedans, {item}.'],
  emptyPack: ['{a} snatches a pack. It is full of rocks.', '{a} attrape un sac. Il est rempli de cailloux.'],
  flees: [
    ['{a} runs straight for the trees.', '{a} court droit vers les arbres.'],
    ['{a} bolts from the Cornucopia without looking back.', "{a} s'enfuit loin de la Corne d'abondance sans regarder derrière."],
  ],
};

// Quiet moments when nothing big happens to a tribute.
export const FILLER = {
  day: [
    ['{a} climbs a tree and maps the arena.', "{a} grimpe à un arbre et repère l'arène."],
    ['{a} follows a stream looking for fish.', '{a} suit un ruisseau à la recherche de poissons.'],
    ['{a} builds a shelter out of branches. It collapses twice.', "{a} construit un abri de branches. Il s'écroule deux fois."],
    ['{a} talks to the cameras, begging for sponsors.', '{a} parle aux caméras et supplie les commanditaires.'],
    ['{a} gets lost and walks in a perfect circle.', '{a} se perd et marche en cercle parfait.'],
    ['{a} covers every footprint, just in case.', '{a} efface chaque trace de pas, au cas où.'],
    ['{a} tries to catch a squirrel. The squirrel wins.', "{a} tente d'attraper un écureuil. L'écureuil gagne."],
    ['{a} practises a victory speech out loud.', '{a} répète son discours de victoire à voix haute.'],
    ['{a} hides in a cave and counts the cannon shots.', '{a} se cache dans une grotte et compte les coups de canon.'],
    ['{a} smears on mud as camouflage. It mostly smells.', '{a} se couvre de boue pour se camoufler. Ça sent surtout mauvais.'],
  ],
  night: [
    ['{a} cannot sleep and stares at the fake stars.', '{a} ne trouve pas le sommeil et fixe les fausses étoiles.'],
    ['{a} lights a fire, panics, and stamps it out.', '{a} allume un feu, panique, puis le piétine.'],
    ['{a} sleeps high in a tree, a rope around the waist.', "{a} dort en haut d'un arbre, une corde autour de la taille."],
    ['{a} hears footsteps all night. It was a raccoon.', "{a} entend des pas toute la nuit. C'était un raton laveur."],
    ['{a} cries quietly, then blames allergies.', '{a} pleure en silence, puis accuse les allergies.'],
    ['{a} watches the faces of the fallen cross the sky.', '{a} regarde les visages des morts défiler dans le ciel.'],
    ['{a} shivers until sunrise.', "{a} grelotte jusqu'au lever du soleil."],
    ['{a} sings to stay awake. Badly.', '{a} chante pour ne pas dormir. Très mal.'],
  ],
};

export const ITEM_STORY = {
  found: [
    ['{a} finds {item} in an abandoned pack.', '{a} trouve {item} dans un sac abandonné.'],
    ['{a} digs up {item} near an old camp.', "{a} déterre {item} près d'un ancien campement."],
    ['{a} takes {item} from a camp nobody was guarding.', '{a} vole {item} dans un camp sans surveillance.'],
  ],
  parachute: ['A silver parachute drifts down to {a}: {item}.', 'Un parachute argenté descend vers {a} : {item}.'],
  fromSponsor: ['{sponsor} sponsors {a} from beyond the arena: {item}.', "{sponsor} commandite {a} depuis l'au-delà : {item}."],
  healed: ['{a} uses {item}. The wound closes.', '{a} utilise {item}. La blessure se referme.'],
  healFails: ['{a} uses {item}. It does nothing at all.', '{a} utilise {item}. Aucun effet.'],
  healsAlly: ['{a} treats {b} with {item}.', '{a} soigne {b} avec {item}.'],
  eats: ['{a} finishes {item} and feels stronger.', '{a} termine {item} et reprend des forces.'],
  spoiled: ['{a} finishes {item}. It had gone bad.', "{a} termine {item}. C'était avarié."],
  trains: ['{a} trains with {item} for hours.', "{a} s'entraîne avec {item} pendant des heures."],
  trainingAccident: ['{a} trains with {item} and gets hurt. Embarrassing.', "{a} s'entraîne avec {item} et se blesse. Gênant."],
  dropped: ['{a} drops {item} into a ravine.', "{a} échappe {item} au fond d'un ravin."],
  checksGear: ['{a} checks {item} for the tenth time.', '{a} vérifie {item} pour la dixième fois.'],
};

export const COMBAT = {
  killWithWeapon: [
    ['{a} kills {b} with {item}.', '{a} tue {b} avec {item}.'],
    ['{a} corners {b} and finishes it with {item}.', '{a} coince {b} et en finit avec {item}.'],
    ['{b} begs for mercy. {a} answers with {item}.', '{b} demande grâce. {a} répond avec {item}.'],
  ],
  killBareHanded: [
    ['{a} overpowers {b} with bare hands.', '{a} maîtrise {b} à mains nues.'],
    ['{a} pushes {b} off a cliff.', "{a} pousse {b} du haut d'une falaise."],
    ['{a} ends {b} with a heavy rock.', '{a} achève {b} avec une grosse pierre.'],
    ['{a} holds {b} under the river until the bubbles stop.', "{a} maintient {b} sous l'eau jusqu'à la dernière bulle."],
  ],
  wound: ['{a} wounds {b}, who limps away swearing revenge.', "{a} blesse {b}, qui s'enfuit en boitant et jure de se venger."],
  draw: ['{a} and {b} fight until both run out of breath, then back away.', "{a} et {b} se battent jusqu'à l'épuisement, puis reculent."],
  weaponBreaks: ['{a} swings {item}. It breaks. Useless.', "{a} brandit {item}. L'arme se brise. Inutile."],
  savedByArmor: ['{b} survives only thanks to {item}, now wrecked, and escapes.', "{b} survit grâce à {item}, désormais en miettes, et s'échappe."],
  loot: ['{a} takes {item} from the body.', '{a} récupère {item} sur le corps.'],
};

// Accidents that happen to a tribute alone.
export const HAZARDS = {
  deadly: [
    ['{a} eats the wrong mushroom.', '{a} mange le mauvais champignon.'],
    ['{a} falls from a tree. The cannon confirms it.', "{a} tombe d'un arbre. Le canon confirme."],
    ['{a} drinks from a poisoned pond.', "{a} boit l'eau d'un étang empoisonné."],
    ['{a} steps on a leftover mine.', '{a} marche sur une mine oubliée.'],
    ['{a} disturbs a nest of killer wasps.', '{a} dérange un nid de guêpes tueuses.'],
  ],
  wounding: [
    ['{a} twists an ankle running from a noise.', '{a} se tord la cheville en fuyant un bruit.'],
    ['{a} gets burned by a geyser.', '{a} se brûle sur un geyser.'],
    ['{a} is bitten by something with too many legs.', '{a} se fait mordre par une bête à trop de pattes.'],
  ],
  closeCall: [
    ['{a} outruns a rockslide by a second.', '{a} échappe de justesse à un éboulement.'],
    ['{a} wakes up next to a snake and leaves very slowly.', "{a} se réveille à côté d'un serpent et s'éloigne très lentement."],
  ],
};

// Two tributes cross paths.
export const ENCOUNTERS = {
  slipsAway: ['{a} spots {b} and slips away unseen.', "{a} aperçoit {b} et s'éclipse sans bruit."],
  spottedSlipping: ['{b} notices {a} sneaking off and gives chase.', "{b} remarque {a} qui tente de s'éclipser et se lance à sa poursuite."],
  allianceFormed: ['{a} and {b} shake hands. An alliance is born.', '{a} et {b} se serrent la main. Une alliance est née.'],
  allianceRefused: ['{b} refuses the alliance {a} offers. {a} will remember.', "{b} refuse l'alliance que propose {a}. {a} s'en souviendra."],
  refusalTurnsUgly: ['{a} takes the refusal badly and attacks.', '{a} prend très mal le refus et attaque.'],
  offerAnsweredWithAttack: ['{a} offers {b} an alliance. {b} attacks instead.', '{a} propose une alliance à {b}, qui attaque aussitôt.'],
  hunted: ['{a} has been hunting {b} for this.', '{a} traquait {b} pour ce moment.'],
  killsSleeper: ['{a} finds {b} asleep and makes sure it stays that way.', "{a} trouve {b} en plein sommeil et s'assure que ça dure."],
  sleeperWakes: ['{a} creeps up on {b}, who wakes up just in time.', "{a} s'approche de {b}, qui se réveille juste à temps."],
  steals: ['{a} steals {item} from {b}, fast asleep.', '{a} vole {item} à {b}, qui dort profondément.'],
  caughtStealing: ['{b} catches {a} going through the supplies. {a} runs.', '{b} surprend {a} en train de fouiller ses affaires. {a} détale.'],
  leavesSleeper: ['{a} watches {b} sleep, then walks on.', '{a} regarde {b} dormir, puis passe son chemin.'],
};

export const ALLIANCE = {
  loyal: [
    ['{a} and {b} share what little food they have.', '{a} et {b} partagent le peu de nourriture qui reste.'],
    ['{a} keeps watch while {b} sleeps.', '{a} monte la garde pendant que {b} dort.'],
    ['{a} and {b} plan their next move in whispers.', '{a} et {b} planifient la suite à voix basse.'],
  ],
  betrayal: ['{a} turns on {b}. The alliance is over.', "{a} se retourne contre {b}. L'alliance est terminée."],
};

export const TRAPS = {
  snareWorks: ['{a} sets a snare and catches dinner.', '{a} pose un collet et attrape son souper.'],
  snareEmpty: ['{a} sets a snare. Nothing bites.', '{a} pose un collet. Rien ne mord.'],
  kills: ['{b} walks into the trap {a} built. Cannon.', '{b} tombe dans le piège que {a} a posé. Coup de canon.'],
  wounds: ['{b} is caught in the trap {a} built and tears free, wounded.', "{b} se prend dans le piège que {a} a posé et s'en arrache, non sans blessure."],
  backfires: ['{a} builds a trap and walks right into it.', '{a} pose un piège et marche en plein dedans.'],
  nobodyComes: ['{a} builds a trap. Nobody comes.', '{a} pose un piège. Personne ne vient.'],
};

export const BERRIES = {
  delicious: ['{a} eats the strange berries. Delicious.', '{a} mange les baies étranges. Délicieuses.'],
  sick: ['{a} eats the strange berries and regrets it for hours.', '{a} mange les baies étranges et le regrette pendant des heures.'],
  deadly: ['{a} eats the strange berries. They were nightlock.', "{a} mange les baies étranges. C'était du sureau mortel."],
  leftAlone: ['{a} finds strange berries and wisely leaves them.', '{a} trouve des baies étranges et les laisse sagement là.'],
};

export const ARENA_STORY = {
  dies: ['{a} does not make it out.', "{a} n'en réchappe pas."],
  wounded: ['{a} gets out, wounded.', "{a} s'en sort avec une blessure."],
  savedBy: ['{a} survives thanks to {item}.', '{a} survit grâce à {item}.'],
  everyoneSafe: ['Everyone escapes unharmed.', "Tout le monde s'en tire indemne."],
  feastAnnounced: ['A feast is announced at the Cornucopia.', "Un festin est annoncé à la Corne d'abondance."],
  feastPrize: ['{a} leaves the feast with {item}.', '{a} repart du festin avec {item}.'],
  feastEmpty: ['Nobody dares to show up.', "Personne n'ose s'y présenter."],
};

export const FINALE = {
  announced: ['Two tributes remain. The Gamemakers drive {a} and {b} to the Cornucopia.', "Il reste deux tributs. Les Juges poussent {a} et {b} vers la Corne d'abondance."],
  // One sentence per duel tactic, in the same order as QUESTIONS.finalDuel.options.
  tactics: [
    ['{a} charges head-on.', '{a} fonce de front.'],
    ['{a} sets an ambush.', '{a} tend une embuscade.'],
    ['{a} waits for the other to tire.', "{a} attend que l'autre s'épuise."],
  ],
};

// Pop-up decisions for players in the room. The order of "options" matters to the engine.
export const QUESTIONS = {
  cornucopia: {
    text: ['The gong sounds. What does {a} do?', 'Le gong retentit. Que fait {a} ?'],
    options: [['Sprint for the weapons', 'Foncer vers les armes'], ['Grab the nearest pack', 'Attraper le sac le plus proche'], ['Run for the trees', 'Fuir vers les arbres']],
  },
  meeting: {
    text: ['{a} spots {b} nearby. {b} has not noticed.', "{a} aperçoit {b} tout près. {b} n'a rien remarqué."],
    options: [['Attack', 'Attaquer'], ['Offer an alliance', 'Proposer une alliance'], ['Slip away', "S'éclipser"]],
  },
  allianceOffer: {
    text: ['{a} offers {b} an alliance. What does {b} answer?', '{a} propose une alliance à {b}. Que répond {b} ?'],
    options: [['Accept', 'Accepter'], ['Refuse', 'Refuser'], ['Attack instead', 'Attaquer plutôt']],
  },
  sleeper: {
    text: ['{a} finds {b} fast asleep.', '{a} trouve {b} en plein sommeil.'],
    options: [['Strike now', 'Frapper maintenant'], ['Steal their supplies', 'Voler ses affaires'], ['Walk away', 'Passer son chemin']],
  },
  loyalty: {
    text: ['{a} is alone with {b}, a member of the same alliance. Few tributes remain.', '{a} se retrouve en tête-à-tête avec {b}, membre de son alliance. Il reste peu de tributs.'],
    options: [['Stay loyal', 'Rester loyal'], ['Betray the alliance', "Trahir l'alliance"]],
  },
  trap: {
    text: ['{a} has {item}. What to build?', '{a} a {item}. Que construire ?'],
    options: [['A snare for food', 'Un collet pour manger'], ['A trap for tributes', 'Un piège à tributs']],
  },
  berries: {
    text: ['{a} finds berries nobody recognises.', '{a} trouve des baies que personne ne reconnaît.'],
    options: [['Eat them', 'Les manger'], ['Leave them', 'Les laisser']],
  },
  finalDuel: {
    text: ['Only {b} stands between {a} and victory. How does {a} fight?', 'Il ne reste que {b} entre {a} et la victoire. Comment {a} se bat ?'],
    options: [['Charge head-on', 'Foncer de front'], ['Set an ambush', 'Tendre une embuscade'], ['Wait them out', "Attendre et épuiser l'autre"]],
  },
  // These two have options built at play time (tribute names, arena events).
  sponsor: { text: ['{sponsor}, you are a sponsor now. Who receives {item}?', '{sponsor}, te voilà commanditaire. Qui reçoit {item} ?'] },
  gamemaker: { text: ['{sponsor}, the Gamemakers hand you the controls. What hits the arena?', "{sponsor}, les Juges te donnent les commandes. Qu'est-ce qui frappe l'arène ?"] },
};
