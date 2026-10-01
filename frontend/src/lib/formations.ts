// Pitch coordinates computed from a formation's slot positions (served by /api/formations,
// slot order: GK, then each line right to left). [x, y] in percent of the pitch; y = 0 is
// the opponent's goal line, so the squad attacks upwards like the squad screen in the game.
export type XY = [number, number];

const ROW_Y: Record<string, number> = {
  GK: 90, CB: 69, RB: 66, LB: 66, RWB: 58, LWB: 58,
  CDM: 55, CM: 45, RM: 41, LM: 41, CAM: 32, CF: 22, RW: 19, LW: 19, ST: 12,
};
const WIDE_X: Record<string, number> = { RB: 86, LB: 14, RWB: 89, LWB: 11, RM: 86, LM: 14, RW: 80, LW: 20 };
const SPREAD: Record<number, number[]> = { 1: [50], 2: [64, 36], 3: [72, 50, 28], 4: [78, 59, 41, 22] };

export function layoutFor(positions: string[]): XY[] {
  const seen: Record<string, number> = {};
  const count: Record<string, number> = {};
  for (const p of positions) count[p] = (count[p] ?? 0) + 1;
  return positions.map((p) => {
    const i = (seen[p] = (seen[p] ?? -1) + 1);
    const x = WIDE_X[p] ?? (SPREAD[count[p]] ?? SPREAD[4])[Math.min(i, 3)];
    return [x, ROW_Y[p] ?? 45];
  });
}

/** Group formations the way the game lists them: by number of defenders. */
export function groupFormations(names: string[]): [string, string[]][] {
  const groups: Record<string, string[]> = {};
  for (const n of names) (groups[`${n[0]} i backlinjen`] ??= []).push(n);
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
}
