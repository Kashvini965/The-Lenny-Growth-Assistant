import {
  ArrowRight,
  BarChart3,
  FileText,
  Images,
  MessageCircle,
  Pencil,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface FeatureCard {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  /** Populates the composer when the workspace is ready. */
  prompt?: string;
  /** Opens an existing generation flow instead of prefilling the composer. */
  action?: "essay" | "skill";
  /** Desktop placement around the central robot. */
  position: "left" | "above" | "upper-right" | "lower-left" | "lower-right";
}

export const FEATURE_CARDS: FeatureCard[] = [
  {
    id: "ask",
    title: "Ask Questions",
    description: "Ask questions about uploaded documents and retrieve relevant answers.",
    icon: MessageCircle,
    prompt: "Summarize the key ideas in the indexed transcripts and cite the sources you use.",
    position: "left",
  },
  {
    id: "summarize",
    title: "Summarize Transcripts",
    description: "Summarize transcripts and extract important information.",
    icon: FileText,
    prompt: "Summarize the most important lessons from these transcripts, with citations.",
    position: "above",
  },
  {
    id: "create",
    title: "Create Content",
    description: "Generate essays, reports, and structured written content.",
    icon: Pencil,
    action: "essay",
    position: "upper-right",
  },
  {
    id: "insights",
    title: "Get Insights",
    description: "Identify key findings, themes, and useful insights.",
    icon: BarChart3,
    prompt: "Identify the key findings and recurring themes across these sources.",
    position: "lower-left",
  },
  {
    id: "artifacts",
    title: "Generate Artifacts",
    description: "Create useful outputs and display generated artifacts in a dedicated viewer.",
    icon: Images,
    action: "skill",
    position: "lower-right",
  },
];

function AssistantIllustration() {
  return (
    <div className="assistant-hub" aria-hidden="true">
      <div className="assistant-glow" />
      <div className="assistant-ring ring-1" />
      <div className="assistant-ring ring-2" />
      <div className="assistant-ring ring-3" />
      <span className="assistant-node node-1" />
      <span className="assistant-node node-2" />
      <span className="assistant-node node-3" />
      <span className="assistant-node node-4" />
      <div className="assistant-tile">
        <svg viewBox="0 0 64 64" className="robot-icon" role="presentation" focusable="false">
          <rect x="10" y="16" width="44" height="34" rx="12" fill="none" stroke="currentColor" strokeWidth="4" />
          <circle cx="24" cy="33" r="3.6" fill="currentColor" />
          <circle cx="40" cy="33" r="3.6" fill="currentColor" />
          <path d="M26 42c4 3 8 3 12 0" fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" />
          <path d="M32 16V9" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
          <circle cx="32" cy="7" r="3.4" fill="currentColor" />
          <path d="M10 30H6M54 30h4" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}

interface HeroSectionProps {
  onStart: () => void;
  onFeature: (card: FeatureCard) => void;
  startLabel: string;
}

export default function HeroSection({ onStart, onFeature, startLabel }: HeroSectionProps) {
  return (
    <div className="hero">
      <div className="hero-copy">
        <p className="hero-tagline">
          Better Insights.
          <br />
          Smarter Growth.
        </p>
        <h1 className="hero-heading">The Lenny Growth Assistant, your transcript-grounded growth assistant</h1>
        <p className="hero-description">
          This assistant analyzes source documents, answers questions from your transcripts, summarizes
          conversations, generates essays and content, and presents insights as artifacts you can review.
        </p>
        <div className="hero-actions">
          <button className="hero-cta" onClick={onStart}>
            <Sparkles size={16} />
            <span>{startLabel}</span>
            <ArrowRight size={15} />
          </button>
        </div>
        <p className="hero-note">Source-grounded answers with citations when <strong>Use sources</strong> is on.</p>
      </div>

      <div className="hero-visual">
        <AssistantIllustration />
        <div className="feature-orbit">
          {FEATURE_CARDS.map((card) => (
            <button
              key={card.id}
              type="button"
              className={`feature-card feature-${card.position}`}
              onClick={() => onFeature(card)}
              aria-label={`${card.title}: ${card.description}`}
            >
              <span className="feature-icon" aria-hidden="true">
                <card.icon size={18} />
              </span>
              <span className="feature-text">
                <strong>{card.title}</strong>
                <small>{card.description}</small>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
