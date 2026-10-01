// Pitch coordinates per formation, in the SAME slot order as backend/app/solver/formations.py.
// [x, y] in percent of the pitch: x 0 = left touchline, y 0 = opponent's goal line (attacking
// upwards, as Ultimate Team shows a squad). Right-sided positions (RB, RM, RW, the first of
// two CBs/STs) are on the right, like in the game.
export type XY = [number, number];

const GK: XY = [50, 90];
const back4: XY[] = [[86, 66], [62, 69], [38, 69], [14, 66]]; // RB, CB, CB, LB
const back3: XY[] = [[72, 69], [50, 70], [28, 69]];
const back5: XY[] = [[89, 58], [70, 69], [50, 70], [30, 69], [11, 58]]; // RWB, CB, CB, CB, LWB
const twoST: XY[] = [[63, 14], [37, 14]];

export const FORMATION_LAYOUT: Record<string, XY[]> = {
  "4-4-2": [GK, ...back4, [86, 41], [62, 45], [38, 45], [14, 41], ...twoST],
  "4-3-3": [GK, ...back4, [72, 46], [50, 49], [28, 46], [82, 19], [50, 12], [18, 19]],
  "4-3-3(4)": [GK, ...back4, [68, 49], [32, 49], [50, 33], [82, 18], [50, 11], [18, 18]],
  "4-2-3-1": [GK, ...back4, [63, 52], [37, 52], [50, 33], [83, 30], [17, 30], [50, 11]],
  "4-1-2-1-2": [GK, ...back4, [50, 54], [74, 43], [26, 43], [50, 31], ...twoST],
  "4-2-2-2": [GK, ...back4, [63, 52], [37, 52], [78, 32], [22, 32], ...twoST],
  "3-5-2": [GK, ...back3, [63, 53], [37, 53], [88, 39], [12, 39], [50, 32], ...twoST],
  "3-4-3": [GK, ...back3, [86, 44], [62, 47], [38, 47], [14, 44], [80, 18], [50, 11], [20, 18]],
  "5-2-1-2": [GK, ...back5, [65, 47], [35, 47], [50, 31], ...twoST],
  "5-3-2": [GK, ...back5, [72, 45], [50, 48], [28, 45], ...twoST],
};

export const FORMATION_POSITIONS: Record<string, string[]> = {
  "4-4-2": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"],
  "4-3-3": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "CM", "RW", "ST", "LW"],
  "4-3-3(4)": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "CAM", "RW", "ST", "LW"],
  "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "CAM", "RM", "LM", "ST"],
  "4-1-2-1-2": ["GK", "RB", "CB", "CB", "LB", "CDM", "CM", "CM", "CAM", "ST", "ST"],
  "4-2-2-2": ["GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "CAM", "CAM", "ST", "ST"],
  "3-5-2": ["GK", "CB", "CB", "CB", "CDM", "CDM", "RM", "LM", "CAM", "ST", "ST"],
  "3-4-3": ["GK", "CB", "CB", "CB", "RM", "CM", "CM", "LM", "RW", "ST", "LW"],
  "5-2-1-2": ["GK", "RWB", "CB", "CB", "CB", "LWB", "CM", "CM", "CAM", "ST", "ST"],
  "5-3-2": ["GK", "RWB", "CB", "CB", "CB", "LWB", "CM", "CM", "CM", "ST", "ST"],
};
