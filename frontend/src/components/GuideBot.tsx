import { useEffect, useRef } from "react";

/** What the robot is doing; each mood has its own animation (see the .bot rules in styles.css). */
export type BotMood = "idle" | "listening" | "thinking" | "speaking" | "happy";

interface Props {
  mood?: BotMood;
  size?: number;
  waving?: boolean;
  label?: string;
}

/**
 * TerraGuide's robot, drawn in SVG and animated with CSS: it floats on a small thruster flame, blinks, follows the pointer with its eyes,
 * moves its mouth while speaking, shows sound rings while listening and thought dots while thinking. Motion stops when the visitor
 * has asked their system for reduced motion.
 */
export default function GuideBot({ mood = "idle", size = 72, waving = false, label }: Props) {
  const eyes = useRef<SVGGElement>(null);

  // The eyes follow the pointer (at most 2.2 units), once per frame.
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const move = (e: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const g = eyes.current;
        if (!g) return;
        const box = g.getBoundingClientRect();
        const dx = e.clientX - (box.left + box.width / 2);
        const dy = e.clientY - (box.top + box.height / 2);
        const len = Math.hypot(dx, dy) || 1;
        const reach = Math.min(1, len / 300) * 2.2;
        g.style.transform = `translate(${(dx / len) * reach}px, ${(dy / len) * reach}px)`;
      });
    };
    window.addEventListener("pointermove", move);
    return () => {
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <svg
      className={`bot bot-${mood}${waving ? " bot-wave" : ""}`}
      viewBox="0 0 120 140"
      width={size}
      height={(size * 140) / 120}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <radialGradient id="bot-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffd27a" />
          <stop offset="60%" stopColor="#ea7a2b" />
          <stop offset="100%" stopColor="#ea7a2b" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="bot-shell" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#24405f" />
          <stop offset="100%" stopColor="#132339" />
        </linearGradient>
        <linearGradient id="bot-flame" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffe08a" />
          <stop offset="55%" stopColor="#ea7a2b" />
          <stop offset="100%" stopColor="#d1566b" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* shadow on the ground, shrinking as the robot rises */}
      <ellipse className="bot-shadow" cx="60" cy="134" rx="26" ry="4" fill="#000" opacity=".35" />

      <g className="bot-float">
        {/* sound rings while listening */}
        <g className="bot-rings" fill="none" stroke="#4cc0b3" strokeWidth="2">
          <circle cx="60" cy="52" r="40" />
          <circle cx="60" cy="52" r="40" />
        </g>

        {/* thruster flame */}
        <path className="bot-flame" d="M52 112 Q60 136 68 112 Z" fill="url(#bot-flame)" />

        {/* arms */}
        <g className="bot-arm bot-arm-left">
          <rect x="18" y="80" width="10" height="24" rx="5" fill="url(#bot-shell)" stroke="#f2b84b" strokeWidth="2" />
        </g>
        <g className="bot-arm bot-arm-right">
          <rect x="92" y="80" width="10" height="24" rx="5" fill="url(#bot-shell)" stroke="#f2b84b" strokeWidth="2" />
        </g>

        {/* body with a glowing ember */}
        <rect x="32" y="74" width="56" height="40" rx="10" fill="url(#bot-shell)" stroke="#f2b84b" strokeWidth="2.5" />
        <circle className="bot-ember-glow" cx="60" cy="94" r="12" fill="url(#bot-glow)" />
        <path className="bot-ember" d="M60 86 C66 92 65 100 60 102 C55 100 54 93 58 90 C58 94 60 95 61 93 C62 91 61 88 60 86 Z" fill="#ffd27a" />

        {/* neck */}
        <rect x="52" y="66" width="16" height="10" fill="#132339" stroke="#f2b84b" strokeWidth="2" />

        {/* head */}
        <g className="bot-head">
          <line x1="60" y1="18" x2="60" y2="8" stroke="#f2b84b" strokeWidth="2.5" />
          <circle className="bot-antenna" cx="60" cy="7" r="5" fill="#ea7a2b" />
          <rect x="22" y="18" width="76" height="52" rx="16" fill="url(#bot-shell)" stroke="#f2b84b" strokeWidth="2.5" />
          <rect x="14" y="36" width="8" height="16" rx="3" fill="#f2b84b" />
          <rect x="98" y="36" width="8" height="16" rx="3" fill="#f2b84b" />
          {/* visor */}
          <rect x="30" y="27" width="60" height="34" rx="11" fill="#06101b" stroke="#2f4a6b" strokeWidth="1.5" />
          <g ref={eyes} className="bot-eyes">
            <g className="bot-eye">
              <ellipse cx="47" cy="41" rx="6" ry="7" fill="#4cc0b3" />
              <circle cx="49" cy="38.5" r="1.8" fill="#e8fffb" />
            </g>
            <g className="bot-eye">
              <ellipse cx="73" cy="41" rx="6" ry="7" fill="#4cc0b3" />
              <circle cx="75" cy="38.5" r="1.8" fill="#e8fffb" />
            </g>
          </g>
          <rect className="bot-mouth" x="52" y="52" width="16" height="3.5" rx="1.75" fill="#f2b84b" />
          <circle className="bot-cheek" cx="38" cy="53" r="3" fill="#d1566b" opacity=".45" />
          <circle className="bot-cheek" cx="82" cy="53" r="3" fill="#d1566b" opacity=".45" />
        </g>

        {/* thought dots */}
        <g className="bot-dots" fill="#f2b84b">
          <circle cx="98" cy="14" r="3" />
          <circle cx="107" cy="9" r="3" />
          <circle cx="116" cy="4" r="3" />
        </g>
      </g>
    </svg>
  );
}
