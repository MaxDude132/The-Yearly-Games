// Disasters the Gamemakers can unleash on the whole arena.
// "counter" is the kind of item that can save a tribute from that event.
import { KIND } from './items.js';

export const ARENA_EVENTS = [
  {
    name: ['Wall of fire', 'Mur de feu'],
    counter: KIND.HEALING,
    intro: ['The Gamemakers set the forest on fire.', 'Les Juges mettent le feu à la forêt.'],
  },
  {
    name: ['Flood', 'Inondation'],
    counter: KIND.TRAP,
    intro: ['A dam bursts. The arena floods.', "Un barrage cède. L'arène est inondée."],
  },
  {
    name: ['Muttations', 'Mutations'],
    counter: KIND.WEAPON,
    intro: ['A pack of mutts is released into the arena.', "Une meute de mutations est lâchée dans l'arène."],
  },
  {
    name: ['Deep freeze', 'Gel soudain'],
    counter: KIND.GEAR,
    intro: ['The temperature drops far below zero.', 'La température chute bien sous zéro.'],
  },
  {
    name: ['Wasp swarm', 'Essaim de guêpes'],
    counter: KIND.ARMOR,
    intro: ['Clouds of killer wasps sweep the arena.', "Des nuées de guêpes tueuses balaient l'arène."],
  },
];

/** The feast is offered as an arena event too, but it plays out differently (see feast() in events.js). */
export const FEAST = {
  name: ['Feast at the Cornucopia', "Festin à la Corne d'abondance"],
  isFeast: true,
};
