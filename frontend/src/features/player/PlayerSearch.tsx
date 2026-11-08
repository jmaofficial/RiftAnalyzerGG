import { ArrowRight, Hash, LoaderCircle, Search } from "lucide-react";
import { useState } from "react";
import type { PlayerIdentity } from "../analysis/types";

export function PlayerSearch({
  onSearch,
  searching,
  disabled,
}: {
  onSearch: (identity: PlayerIdentity) => Promise<void>;
  searching: boolean;
  disabled: boolean;
}) {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  return (
    <form
      className="search-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (gameName.trim() && tagLine.trim())
          void onSearch({
            gameName: gameName.trim(),
            tagLine: tagLine.trim().replace(/^#/, ""),
          });
      }}
    >
      <div className="search-field">
        <label htmlFor="game-name">GAME NAME</label>
        <div>
          <Search size={18} />
          <input
            id="game-name"
            name="gameName"
            placeholder="Your game name"
            value={gameName}
            onChange={(event) => setGameName(event.target.value)}
            required
            maxLength={100}
            disabled={disabled}
            autoComplete="off"
          />
        </div>
      </div>
      <div className="search-field tag-field">
        <label htmlFor="tag-line">TAGLINE</label>
        <div>
          <Hash size={17} />
          <input
            id="tag-line"
            name="tagLine"
            placeholder="EUW"
            value={tagLine}
            onChange={(event) => setTagLine(event.target.value)}
            required
            maxLength={10}
            disabled={disabled}
            autoComplete="off"
          />
        </div>
      </div>
      <button
        className="button button-primary search-button"
        type="submit"
        disabled={
          disabled ||
          searching ||
          !gameName.trim() ||
          !tagLine.trim().replace(/^#/, "")
        }
      >
        {searching ? <LoaderCircle className="spin" size={17} /> : null}
        {searching ? "Finding player…" : "View report"}
        {!searching && <ArrowRight size={17} />}
      </button>
    </form>
  );
}
