export type OperationRect = {x: number; y: number; w: number; h: number};
export type OperationPanel = {variant: 'A' | 'B'; rect: OperationRect};

/** Two full-width detail views retain readable native cargo on the shared clock. */
export function operationPanels(region: OperationRect, narrow: boolean): OperationPanel[] {
  const top = Math.min(narrow ? 84 : 76, region.h * .2);
  const bottom = Math.min(narrow ? 142 : 100, region.h * .25);
  const gap = Math.min(12, region.h * .03);
  const height = Math.floor((region.h - top - bottom - gap) / 2);
  return [
    {variant: 'A', rect: {x: region.x, y: region.y + top, w: region.w, h: height}},
    {variant: 'B', rect: {
      x: region.x, y: region.y + top + height + gap, w: region.w, h: height,
    }},
  ];
}
