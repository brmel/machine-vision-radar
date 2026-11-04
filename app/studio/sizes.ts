export const SIZES = [
  { name: "link", width: 1200, height: 627, rows: 4 },
  { name: "portrait", width: 1080, height: 1350, rows: 12 },
] as const;

export const CLIP_SIZES = [
  { name: "portrait", width: 1080, height: 1350, footage: ["1080x1350"] },
  { name: "square", width: 1080, height: 1080, footage: ["1080x1350"] },
  { name: "landscape", width: 1920, height: 1080, footage: ["1920x1080", "1200x627"] },
] as const;
