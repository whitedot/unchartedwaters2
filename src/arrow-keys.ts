export function arrowKeypadCode(held: Set<string>) {
  const x = Number(held.has("ArrowRight")) - Number(held.has("ArrowLeft"));
  const y = Number(held.has("ArrowUp")) - Number(held.has("ArrowDown"));
  return x || y ? 101 + x + 3 * y : null;
}
