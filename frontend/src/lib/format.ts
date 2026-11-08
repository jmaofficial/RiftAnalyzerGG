export const number = (value: number | null | undefined, digits = 0) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(
        value,
      );

export const percent = (value: number | null | undefined, digits = 0) =>
  value == null ? "—" : `${number(value * 100, digits)}%`;

export const championName = (name: string) =>
  ({
    MonkeyKing: "Wukong",
    AurelionSol: "Aurelion Sol",
    Renata: "Renata Glasc",
  })[name] || name;

export const laneName = (name: string) =>
  ({
    TOP: "Top",
    JUNGLE: "Jungle",
    MIDDLE: "Mid",
    BOTTOM: "Bot",
    UTILITY: "Support",
  })[name] || name;
