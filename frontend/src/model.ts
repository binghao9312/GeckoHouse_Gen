export type Role = 'wall' | 'roof_shoulder' | 'roof_top';
export type SurfaceMode = 'smooth' | 'ledge';
export interface ContourLevel { z: number; points: number[][]; surface_mode: SurfaceMode; manually_modified: boolean; role: Role; z_locked: boolean; shape_locked: boolean; }
export interface Appearance { relief_enabled: boolean; relief_seed: number; relief_depth: number; relief_gap: number; relief_scale: number; }
export interface Design { version: 3; height: number; wall_thickness: number; roof_thickness: number; base_thickness: number; summit: number[]; levels: ContourLevel[]; entrance: { width: number; height: number; offset: number; profile: number[][] }; ring_clearance: number; max_local_slope_deg: number; max_overhang_xy: number; max_overhang_ratio: number; min_level_spacing: number; appearance: Appearance; }

export const clone = (design: Design): Design => structuredClone(design);
export const bounds = (points: number[][], axis: number): [number, number] => {
  const values = points.map((point) => point[axis]);
  return [Math.min(...values), Math.max(...values)];
};
export const levelCenter = (level: ContourLevel, axis: number) => {
  const [lower, upper] = bounds(level.points, axis); return (lower + upper) / 2;
};
export const remapBounds = (design: Design, index: number, axis: number, lower: number, upper: number) => {
  const level = design.levels[index];
  const [oldLower, oldUpper] = bounds(level.points, axis);
  if (level.shape_locked || upper - lower < 1 || oldUpper - oldLower < 1e-6) return;
  level.points.forEach((point) => { point[axis] = lower + (point[axis] - oldLower) / (oldUpper - oldLower) * (upper - lower); });
  level.manually_modified = true;
};
export const translateLevel = (design: Design, index: number, axis: number, center: number) => {
  const level = design.levels[index];
  if (level.shape_locked) return;
  const delta = center - levelCenter(level, axis);
  level.points.forEach((point) => { point[axis] += delta; });
  level.manually_modified = true;
};
export const moveLevelZ = (design: Design, index: number, z: number) => {
  const level = design.levels[index];
  if (level.z_locked || index === 0 || index === design.levels.length - 1) return;
  const lower = design.levels[index - 1].z + design.min_level_spacing;
  const upper = design.levels[index + 1].z - design.min_level_spacing;
  level.z = Math.max(lower, Math.min(upper, z));
  level.manually_modified = true;
};
export const snap = (value: number, increment: number) => increment ? Math.round(value / increment) * increment : value;
