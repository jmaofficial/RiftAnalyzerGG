import {
  BarChart3,
  BookOpen,
  ChevronRight,
  Compass,
  ExternalLink,
  Layers3,
  Zap,
} from "lucide-react";
import type { ReactNode } from "react";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="RiftAnalyzerGG home">
          <span className="brand-mark">
            <Zap size={23} />
          </span>
          <span>
            RIFT<span className="brand-light">ANALYZER</span>
            <small>LEAGUE OF LEGENDS INSIGHTS</small>
          </span>
        </a>
        <div className="nav-caption">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          <a href="#overview">
            <Compass size={19} /> Overview <ChevronRight size={14} />
          </a>
          <a href="#phases">
            <Layers3 size={19} /> Match phases
          </a>
          <a href="#patterns">
            <BarChart3 size={19} /> Patterns
          </a>
          <a href="#methodology">
            <BookOpen size={19} /> How it works
          </a>
        </nav>
        <div className="sidebar-bottom">
          <span className="region-dot" /> Europe · Solo / Duo
          <p>
            Better questions.
            <br />A clearer game plan.
          </p>
          <a
            href="https://developer.riotgames.com/"
            target="_blank"
            rel="noreferrer"
          >
            Powered by Riot data <ExternalLink size={12} />
          </a>
        </div>
      </aside>
      <main id="top" className="main-content">
        <div className="topbar">
          <span>PLAYER INTELLIGENCE</span>
          <span className="topbar-meta">
            RiftAnalyzer<span>GG</span>{" "}
            <span className="version-badge">EARLY ACCESS</span>
          </span>
        </div>
        {children}
        <footer>
          RiftAnalyzerGG is not endorsed by Riot Games. League of Legends and
          Riot Games are trademarks of Riot Games, Inc.
        </footer>
      </main>
    </div>
  );
}
