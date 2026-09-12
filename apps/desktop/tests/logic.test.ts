import { describe, expect, it } from "vitest";
import { bandLabel } from "../src/components/TreePanel";
import { liveResize } from "../src/components/Canvas";
import { COMPONENT_TYPES } from "../src/types";

describe("confidence bands (directive §64: UNKNOWN never becomes a fact)", () => {
  it("manual edits are FACT", () => {
    expect(bandLabel(0.2, true)).toBe("F");
  });
  it("bands map correctly", () => {
    expect(bandLabel(0.9, false)).toBe("H");
    expect(bandLabel(0.7, false)).toBe("M");
    expect(bandLabel(0.3, false)).toBe("L");
    expect(bandLabel(0, false)).toBe("?");
  });
});

describe("resize math", () => {
  const box = { x: 100, y: 100, width: 100, height: 50 };
  it("east handle grows width only", () => {
    const r = liveResize(box, "e", 20, 30);
    expect(r.width).toBe(120);
    expect(r.height).toBe(50);
    expect(r.x).toBe(100);
  });
  it("north-west handle moves origin and keeps the opposite corner fixed", () => {
    const r = liveResize(box, "nw", -10, -10);
    expect(r.x).toBe(90);
    expect(r.y).toBe(90);
    expect(r.width).toBe(110);
    expect(r.height).toBe(60);
  });
  it("never collapses below 4px", () => {
    const r = liveResize(box, "e", -1000, 0);
    expect(r.width).toBe(4);
  });
});

describe("UI schema surface (mirror of backend v1)", () => {
  it("has the 21 canonical component types", () => {
    expect(COMPONENT_TYPES.length).toBe(21);
    expect(COMPONENT_TYPES).toContain("button");
    expect(COMPONENT_TYPES).toContain("custom");
  });
});
