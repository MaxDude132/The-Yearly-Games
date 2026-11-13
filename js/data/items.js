// Everything a tribute can carry. Each item has a kind and an English/French name.
import { pickRandom } from '../utils/random.js';

export const KIND = {
  WEAPON: 'weapon',   // better odds in a fight, can break
  ARMOR: 'armor',     // can save you from a killing blow once
  HEALING: 'healing', // can close a wound (or do nothing)
  FOOD: 'food',       // gives strength (or is spoiled)
  TRAP: 'trap',       // rope, net, wire: lets you set snares and traps
  GEAR: 'gear',       // matches, sleeping bag... helps against some arena events
};

const { WEAPON, ARMOR, HEALING, FOOD, TRAP, GEAR } = KIND;

export const ITEMS = [
  [WEAPON, 'a sword', 'une épée'],
  [WEAPON, 'a bow and twelve arrows', 'un arc et douze flèches'],
  [WEAPON, 'a set of throwing knives', 'un jeu de couteaux de lancer'],
  [WEAPON, 'a spear', 'une lance'],
  [WEAPON, 'an axe', 'une hache'],
  [WEAPON, 'a trident', 'un trident'],
  [WEAPON, 'a mace', 'une masse'],
  [WEAPON, 'a sickle', 'une faucille'],
  [WEAPON, 'a machete', 'une machette'],
  [WEAPON, 'a slingshot', 'un lance-pierre'],
  [WEAPON, 'a blowgun', 'une sarbacane'],
  [ARMOR, 'a wooden shield', 'un bouclier en bois'],
  [ARMOR, 'body armour', 'une armure légère'],
  [HEALING, 'burn ointment', 'un onguent contre les brûlures'],
  [HEALING, 'a vial of medicine', 'une fiole de médicament'],
  [HEALING, 'a roll of bandages', 'un rouleau de bandages'],
  [FOOD, 'a loaf of bread', 'une miche de pain'],
  [FOOD, 'dried beef', 'du bœuf séché'],
  [FOOD, 'a canteen of water', 'une gourde pleine'],
  [FOOD, 'a pot of hot soup', 'un pot de soupe chaude'],
  [FOOD, 'a bag of apples', 'un sac de pommes'],
  [TRAP, 'a coil of rope', 'un rouleau de corde'],
  [TRAP, 'a net', 'un filet'],
  [TRAP, 'a spool of wire', 'une bobine de fil de fer'],
  [GEAR, 'a box of matches', "une boîte d'allumettes"],
  [GEAR, 'a sleeping bag', 'un sac de couchage'],
  [GEAR, 'night-vision glasses', 'des lunettes de vision nocturne'],
].map(([kind, english, french]) => ({ kind, name: [english, french] }));

/** A random item, optionally of one kind. Returns a fresh copy so tributes never share an item. */
export function randomItem(kind) {
  const choices = kind ? ITEMS.filter((item) => item.kind === kind) : ITEMS;
  return { ...pickRandom(choices) };
}
