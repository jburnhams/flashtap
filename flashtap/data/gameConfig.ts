import { GameAsset } from '../types';

/**
 * CONFIGURATION
 * Add your assets here. In a real deployment, 'content' could be an image path like '/images/sheep.png'.
 * For this demo, we use high-quality emojis.
 */

export const ANIMAL_ASSETS: GameAsset[] = [
  { id: 'sheep', content: '🐑', label: 'Sheep', category: 'animals' },
  { id: 'cow', content: '🐄', label: 'Cow', category: 'animals' },
  { id: 'pig', content: '🐖', label: 'Pig', category: 'animals' },
  { id: 'horse', content: '🐎', label: 'Horse', category: 'animals' },
  { id: 'chicken', content: '🐓', label: 'Chicken', category: 'animals' },
  { id: 'dog', content: '🐕', label: 'Dog', category: 'animals' },
  { id: 'cat', content: '🐈', label: 'Cat', category: 'animals' },
  { id: 'duck', content: '🦆', label: 'Duck', category: 'animals' },
  { id: 'lion', content: '🦁', label: 'Lion', category: 'animals' },
  { id: 'tiger', content: '🐅', label: 'Tiger', category: 'animals' },
  { id: 'elephant', content: '🐘', label: 'Elephant', category: 'animals' },
  { id: 'monkey', content: '🐒', label: 'Monkey', category: 'animals' },
];

export const SHAPE_ASSETS: GameAsset[] = [
  { id: 'red_circle', content: '🔴', label: 'Red Circle', category: 'shapes', tags: ['red', 'circle'] },
  { id: 'blue_circle', content: '🔵', label: 'Blue Circle', category: 'shapes', tags: ['blue', 'circle'] },
  { id: 'green_circle', content: '🟢', label: 'Green Circle', category: 'shapes', tags: ['green', 'circle'] },
  { id: 'yellow_circle', content: '🟡', label: 'Yellow Circle', category: 'shapes', tags: ['yellow', 'circle'] },
  { id: 'red_square', content: '🟥', label: 'Red Square', category: 'shapes', tags: ['red', 'square'] },
  { id: 'blue_square', content: '🟦', label: 'Blue Square', category: 'shapes', tags: ['blue', 'square'] },
  { id: 'green_square', content: '🟩', label: 'Green Square', category: 'shapes', tags: ['green', 'square'] },
  { id: 'orange_square', content: '🟧', label: 'Orange Square', category: 'shapes', tags: ['orange', 'square'] },
  { id: 'white_square', content: '⬜', label: 'White Square', category: 'shapes', tags: ['white', 'square'] },
  { id: 'black_square', content: '⬛', label: 'Black Square', category: 'shapes', tags: ['black', 'square'] },
  { id: 'diamond', content: '🔶', label: 'Orange Diamond', category: 'shapes', tags: ['orange', 'diamond'] },
];

export const FRUIT_ASSETS: GameAsset[] = [
  { id: 'apple', content: '🍎', label: 'Apple', category: 'food' },
  { id: 'banana', content: '🍌', label: 'Banana', category: 'food' },
  { id: 'grapes', content: '🍇', label: 'Grapes', category: 'food' },
  { id: 'watermelon', content: '🍉', label: 'Watermelon', category: 'food' },
  { id: 'carrot', content: '🥕', label: 'Carrot', category: 'food' },
  { id: 'corn', content: '🌽', label: 'Corn', category: 'food' },
  { id: 'pepper', content: '🌶️', label: 'Pepper', category: 'food' },
  { id: 'cheese', content: '🧀', label: 'Cheese', category: 'food' },
];

export const VEHICLE_ASSETS: GameAsset[] = [
  { id: 'car', content: '🚗', label: 'Car', category: 'vehicles' },
  { id: 'taxi', content: '🚕', label: 'Taxi', category: 'vehicles' },
  { id: 'bus', content: '🚌', label: 'Bus', category: 'vehicles' },
  { id: 'police', content: '🚓', label: 'Police Car', category: 'vehicles' },
  { id: 'ambulance', content: '🚑', label: 'Ambulance', category: 'vehicles' },
  { id: 'fire', content: '🚒', label: 'Fire Engine', category: 'vehicles' },
  { id: 'bicycle', content: '🚲', label: 'Bicycle', category: 'vehicles' },
  { id: 'airplane', content: '✈️', label: 'Airplane', category: 'vehicles' },
  { id: 'rocket', content: '🚀', label: 'Rocket', category: 'vehicles' },
];

// Combine all for mixed modes
export const ALL_ASSETS = [
  ...ANIMAL_ASSETS,
  ...SHAPE_ASSETS,
  ...FRUIT_ASSETS,
  ...VEHICLE_ASSETS
];
