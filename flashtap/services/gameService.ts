import { GameMode, GameRound, GameAsset, GameOption } from "../types";
import { ALL_ASSETS, ANIMAL_ASSETS, FRUIT_ASSETS, SHAPE_ASSETS, VEHICLE_ASSETS } from "../data/gameConfig";

// --- Helper Functions ---

const getRandomItem = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

const shuffleArray = <T>(array: T[]): T[] => {
    const newArr = [...array];
    for (let i = newArr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [newArr[i], newArr[j]] = [newArr[j], newArr[i]];
    }
    return newArr;
};

const getDistractors = (correctItem: GameAsset, pool: GameAsset[], count: number): GameAsset[] => {
    const potential = pool.filter(i => i.id !== correctItem.id);
    return shuffleArray(potential).slice(0, count);
};

// --- Game Logic Generators ---

const generateMatchingRound = (difficulty: number): GameRound => {
    // Pick a random category pool for consistency in a round
    const pools = [ANIMAL_ASSETS, FRUIT_ASSETS, VEHICLE_ASSETS];
    const pool = getRandomItem(pools);
    
    const correctItem = getRandomItem(pool);
    const distractors = getDistractors(correctItem, pool, difficulty - 1);
    
    const options = shuffleArray([correctItem, ...distractors]).map(item => ({
        id: item.id,
        content: item.content,
        label: item.label, // Optional: hide label if we want pure picture matching
        isCorrect: item.id === correctItem.id
    }));

    return {
        questionText: `Find the ${correctItem.label}`,
        questionDisplay: correctItem.content,
        successMessage: `That's correct! You found the ${correctItem.label}.`,
        options,
        correctOptionId: correctItem.id,
        category: 'Matching',
        mode: GameMode.MATCHING
    };
};

const generateColorRound = (difficulty: number): GameRound => {
    // Filter shapes that have color tags
    const colorShapes = SHAPE_ASSETS.filter(a => a.tags && a.tags.includes('circle')); // Simplify to just circles for colors, or any
    const pool = SHAPE_ASSETS;
    
    // Pick a target color
    const correctItem = getRandomItem(pool);
    const targetColor = correctItem.tags?.find(t => ['red','blue','green','yellow','orange','purple','black','white'].includes(t));
    
    if (!targetColor) return generateMatchingRound(difficulty); // Fallback

    // Distractors must be different colors
    const distractors = getDistractors(correctItem, pool, difficulty - 1);
    
    const options = shuffleArray([correctItem, ...distractors]).map(item => ({
        id: item.id,
        content: item.content,
        label: item.label,
        isCorrect: item.id === correctItem.id
    }));

    return {
        questionText: `Which one is ${targetColor}?`,
        questionDisplay: targetColor.toUpperCase(), // Or show a paint bucket emoji?
        successMessage: `That's correct! It is ${targetColor}.`,
        options,
        correctOptionId: correctItem.id,
        category: 'Colors',
        mode: GameMode.COLORS
    };
};

const generateCountingRound = (difficulty: number): GameRound => {
    const itemToCount = getRandomItem([...ANIMAL_ASSETS, ...FRUIT_ASSETS]);
    const correctNumber = Math.floor(Math.random() * 5) + 1; // 1 to 5 items to keep it simple for visuals
    
    // Display string: "🍎 🍎 🍎"
    const displayString = Array(correctNumber).fill(itemToCount.content).join(' ');
    
    // Generate number options
    const correctOpt: GameOption = { 
        id: `num_${correctNumber}`, 
        content: correctNumber.toString(), 
        label: correctNumber.toString(),
        isCorrect: true 
    };
    
    const distractorOpts: GameOption[] = [];
    while (distractorOpts.length < difficulty - 1) {
        const n = Math.floor(Math.random() * 10) + 1;
        if (n !== correctNumber && !distractorOpts.find(d => d.content === n.toString())) {
            distractorOpts.push({ 
                id: `num_${n}`, 
                content: n.toString(), 
                label: n.toString(),
                isCorrect: false 
            });
        }
    }

    const options = shuffleArray([correctOpt, ...distractorOpts]);

    return {
        questionText: `How many ${itemToCount.label}s are there?`,
        questionDisplay: displayString,
        successMessage: `That's correct! There are ${correctNumber} ${itemToCount.label}s.`,
        options,
        correctOptionId: correctOpt.id,
        category: 'Counting',
        mode: GameMode.COUNTING
    };
};

const generateLetterRound = (difficulty: number): GameRound => {
    const pool = [...ANIMAL_ASSETS, ...FRUIT_ASSETS];
    const correctItem = getRandomItem(pool);
    const letter = correctItem.label.charAt(0).toUpperCase();

    // Distractors should NOT start with the same letter
    const validDistractors = pool.filter(i => i.label.charAt(0).toUpperCase() !== letter);
    const distractors = shuffleArray(validDistractors).slice(0, difficulty - 1);

    const options = shuffleArray([correctItem, ...distractors]).map(item => ({
        id: item.id,
        content: item.content,
        label: item.label,
        isCorrect: item.id === correctItem.id
    }));

    return {
        questionText: `What starts with the letter ${letter}?`,
        questionDisplay: letter,
        successMessage: `That's correct! ${correctItem.label} starts with ${letter}.`,
        options,
        correctOptionId: correctItem.id,
        category: 'Letters',
        mode: GameMode.LETTERS
    };
};

// --- Main Generator ---

export const generateGameRound = async (mode: GameMode, difficulty: number): Promise<GameRound> => {
    // Simulate async to keep interface consistent if we ever fetch data
    return new Promise((resolve) => {
        let round: GameRound;

        switch (mode) {
            case GameMode.MATCHING:
                round = generateMatchingRound(difficulty);
                break;
            case GameMode.COLORS:
                round = generateColorRound(difficulty);
                break;
            case GameMode.SHAPES:
                // Reuse matching logic but restrict pool to shapes
                const shapeTarget = getRandomItem(SHAPE_ASSETS);
                const shapeDist = getDistractors(shapeTarget, SHAPE_ASSETS, difficulty - 1);
                round = {
                    questionText: `Find the ${shapeTarget.label}`,
                    questionDisplay: shapeTarget.content,
                    successMessage: `That's correct! You found the ${shapeTarget.label}.`,
                    options: shuffleArray([shapeTarget, ...shapeDist]).map(i => ({
                        id:i.id, 
                        content: i.content, 
                        label: i.label,
                        isCorrect: i.id === shapeTarget.id
                    })),
                    correctOptionId: shapeTarget.id,
                    category: 'Shapes',
                    mode: GameMode.SHAPES
                };
                break;
            case GameMode.LETTERS:
                round = generateLetterRound(difficulty);
                break;
            case GameMode.COUNTING:
                round = generateCountingRound(difficulty);
                break;
            case GameMode.MIXED:
            default:
                const modes = [GameMode.MATCHING, GameMode.COUNTING, GameMode.LETTERS, GameMode.COLORS, GameMode.SHAPES];
                const randomMode = getRandomItem(modes);
                return resolve(generateGameRound(randomMode, difficulty));
        }

        resolve(round);
    });
};