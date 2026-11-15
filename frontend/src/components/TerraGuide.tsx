import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../services/api";
import { canListen, canSpeak, listen, matchChoice, speak, stopSpeaking } from "../services/voice";
import GuideBot, { type BotMood } from "./GuideBot";
import type { AreaGroup, Place, Selection } from "../types";
import type { GoTarget } from "../pages/Landing";

/**
 * TerraGuide: an onboarding assistant. It asks who the visitor is, what they want to find, where and (when it matters) which month,
 * then takes them to the right page with the right area, view and month already set, and says what to look at there.
 * It runs entirely in the browser from a fixed set of questions: no AI service, no data leaves the page.
 */

export interface GuideAction {
  tab: GoTarget | "start";
  steady?: boolean;
  area?: string; // a name from the Area menu
  place?: Place; // a town or village found by search
  month?: Selection;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: AreaGroup[] | null;
  currentArea: string;
  latest: Selection | null; // the latest complete month in the data
  onAction: (action: GuideAction) => void;
}

type RoleId = "responder" | "manager" | "scientist" | "firefighter" | "explorer";
type GoalId = "now" | "season" | "unusual" | "map" | "trend" | "download" | "sensors" | "method" | "tour";

const ROLES: { id: RoleId; label: string }[] = [
  { id: "responder", label: "Early warning or emergency response" },
  { id: "manager", label: "Land, farm or forest management" },
  { id: "firefighter", label: "Firefighting or fire planning" },
  { id: "scientist", label: "Science or research" },
  { id: "explorer", label: "Just exploring" },
];

interface Goal {
  id: GoalId;
  label: string;
  tab: GoTarget | "start";
  steady?: boolean;
  needsArea: boolean;
  needsMonth: boolean;
  keywords: string[];
  look: string[]; // what to look at once there
}

const GOALS: Record<GoalId, Goal> = {
  now: {
    id: "now", label: "Is burning right now higher or lower than usual?", tab: "overview", needsArea: true, needsMonth: false,
    keywords: ["now", "current", "currently", "today", "this week", "this month", "recent", "lately", "latest", "right now", "normal"],
    look: [
      "Find the box “Right now, compared with earlier years”.",
      "Pick 14, 30 or 60 days, or the month so far. It ranks this period against the same dates in every year since 2002.",
      "The comparison uses the same three satellites in every year, so a newer satellite cannot make this year look busier.",
    ],
  },
  season: {
    id: "season", label: "When does burning usually start and peak?", tab: "historical", needsArea: true, needsMonth: false,
    keywords: ["season", "when", "usually", "peak", "start", "typical", "calendar", "timing", "which months"],
    look: [
      "The burning-season summary shows when burning usually starts, peaks and ends here.",
      "The monthly pattern chart shows the typical amount for each calendar month, with the spread across years.",
      "For the month-by-month grid of every year, open the Burning calendar.",
    ],
  },
  unusual: {
    id: "unusual", label: "Which months were unusual, and why?", tab: "anomalies", needsArea: true, needsMonth: false,
    keywords: ["unusual", "anomal", "abnormal", "strange", "odd", "extreme", "record", "flag", "outlier", "spike", "drop"],
    look: [
      "Each flagged month comes with a plain-language reason: how far it was from the same month in other years.",
      "Click a month to open it on the Burning calendar and see where the activity was.",
      "About 1 month in 100 would be flagged by chance alone, so a flag means “worth a look”, not proof of a problem.",
    ],
  },
  map: {
    id: "map", label: "Where were the hotspots in a particular month?", tab: "calendar", needsArea: true, needsMonth: true,
    keywords: ["where", "map", "hotspot", "location", "place", "show me", "which areas", "district", "village"],
    look: [
      "The month you chose is highlighted in the calendar. Click any other square to change month.",
      "The map below shows which grid squares were active. Brighter squares had activity on more days.",
      "The month detail explains how this month compares with the same month in other years.",
      "You can draw a box on the map to study just that area.",
    ],
  },
  trend: {
    id: "trend", label: "Is burning increasing or decreasing over the years?", tab: "historical", steady: true, needsArea: true, needsMonth: false,
    keywords: ["trend", "increas", "decreas", "over the years", "years", "long term", "change", "compare years", "growing", "rising", "falling"],
    look: [
      "I switched the Sensor view to the steady set (Terra, Aqua, Suomi-NPP), the fair way to compare years.",
      "With all satellites, newer satellites (2018 and 2023) add detections and would make recent years look busier than they were.",
      "The yearly chart shows the busiest and quietest years. Years before 2012 are estimates from MODIS, with a range.",
    ],
  },
  download: {
    id: "download", label: "Download data or a printable report", tab: "data", needsArea: true, needsMonth: false,
    keywords: ["download", "csv", "export", "data", "report", "pdf", "file", "excel", "spreadsheet"],
    look: [
      "Download the monthly calendar CSV or a printable summary report for your area.",
      "Individual hotspots and cell-level files are on the Burning calendar: choose a month, then use the download buttons under the map.",
      "Every file records its source (NASA FIRMS), the method, the area and the sensor view.",
    ],
  },
  sensors: {
    id: "sensors", label: "How do MODIS and VIIRS compare?", tab: "sensors", needsArea: false, needsMonth: false,
    keywords: ["modis", "viirs", "sensor", "satellite", "harmoni", "agree", "terra", "aqua", "noaa", "suomi"],
    look: [
      "See how closely the two sensor families agree month by month, and how much more VIIRS sees.",
      "The accuracy check shows how well the 2002–2011 estimates matched real VIIRS years when tested.",
      "The sensitivity analysis shows which results hold when the choices are changed.",
    ],
  },
  method: {
    id: "method", label: "How are the numbers calculated?", tab: "method", needsArea: false, needsMonth: false,
    keywords: ["how", "method", "calculat", "formula", "statistic", "score", "math", "model", "isolation", "methodology"],
    look: [
      "Every formula, constant and decision, in order, with the reason for each.",
      "Use the worked example to recompute an unusual-month score yourself.",
    ],
  },
  tour: {
    id: "tour", label: "I'm not sure: show me around", tab: "start", needsArea: false, needsMonth: false,
    keywords: ["help", "not sure", "tour", "start", "begin", "what can", "explain", "show me around"],
    look: [
      "“Start here” explains what TerraGuard can and cannot tell you, with a short path for each kind of user.",
      "When you know what you want, open me again and pick a question.",
    ],
  },
};

// Goals offered first for each kind of user; the others follow.
const ORDER: Record<RoleId, GoalId[]> = {
  responder: ["now", "unusual", "map", "season", "trend", "download", "sensors", "method"],
  manager: ["season", "now", "map", "trend", "unusual", "download", "sensors", "method"],
  firefighter: ["season", "map", "now", "unusual", "download", "trend", "sensors", "method"],
  scientist: ["method", "sensors", "download", "trend", "unusual", "season", "map", "now"],
  explorer: ["tour", "map", "season", "now", "unusual", "trend", "download", "sensors", "method"],
};

const ADVICE: Record<RoleId, string> = {
  responder: "TerraGuard is a history, not a live alert. For fires burning now, use NASA's FIRMS fire map and your local authorities.",
  manager: "Detections show heat, not the cause: TerraGuard cannot tell a farm burn from a wildfire, and does not measure the area burned.",
  firefighter: "Use it for planning (which months and places usually burn), not for an incident: it does not track fires or forecast spread.",
  scientist: "Detections are not unique fires. Compare years with the steady satellite set, and see Sensor harmonization for the tests and their limits.",
  explorer: "Each coloured square counts detections by satellite, not confirmed fires, and TerraGuard does not make predictions.",
};

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const SHORT = MONTHS.map((m) => m.slice(0, 3).toLowerCase());
const FIRST_YEAR = 2001;

type Step = "role" | "goal" | "area" | "area-list" | "town" | "month" | "month-pick" | "done";
interface Line { from: "guide" | "you"; text: string }

/** Read a goal, a month and a year from free text, such as "where did it burn in Tamale in December 2025". */
export function readRequest(text: string): { goal: GoalId | null; month: number | null; year: number | null; rest: string } {
  const lower = ` ${text.toLowerCase()} `;
  let goal: GoalId | null = null;
  let best = 0;
  for (const g of Object.values(GOALS)) {
    const hits = g.keywords.filter((k) => lower.includes(k)).reduce((n, k) => n + k.length, 0);
    if (hits > best) { best = hits; goal = g.id; }
  }
  const yearMatch = /\b(20[0-2]\d)\b/.exec(lower);
  const year = yearMatch ? Number(yearMatch[1]) : null;
  let month: number | null = null;
  MONTHS.forEach((name, i) => {
    const short = SHORT[i];
    const re = new RegExp(`\\b(${name.toLowerCase()}|${short}${short === "sep" ? "t?" : ""})\\b`);
    if (month === null && re.test(lower) && !(short === "may" && /\bmay (be|i|you|we)\b/.test(lower))) month = i + 1;
  });
  // Words left over may name a place: drop the matched keywords, months, years and common words.
  const stop = new Set(["the", "in", "at", "for", "of", "a", "an", "i", "is", "was", "were", "it", "did", "do", "does", "my", "me", "show", "near",
    "around", "and", "to", "what", "where", "when", "how", "which", "burn", "burning", "burned", "fire", "fires", "want", "see", "find", "there", "this",
    "that", "last", "year", "month", "region", "area", "please", "can", "you", "tell", "about", "much", "many", "been", "has", "have", "with", "on",
    "take", "go", "goto", "locate", "zoom", "fly", "into", "let", "lets", "let's", "look", "could", "would", "like", "us", "display", "open", "bring",
    "up", "some", "any", "town", "city", "is", "are", "hey", "hi", "hello", "terraguide", "ok", "okay", "then", "happened", "happen"]);
  const keywordWords = new Set(Object.values(GOALS).flatMap((g) => g.keywords.flatMap((k) => k.split(" "))));
  const rest = text
    .replace(/[^\p{L}\s'-]/gu, " ")
    .split(/\s+/)
    .filter((w) => w && !stop.has(w.toLowerCase()) && !keywordWords.has(w.toLowerCase())
      && !MONTHS.some((m, i) => [m.toLowerCase(), SHORT[i], "sept"].includes(w.toLowerCase())))
    .join(" ");
  return { goal, month, year, rest };
}

type Where = { area?: string; place?: Place; label: string };
interface Pending { goal: GoalId | null; month: Selection | null }
interface Point { x: number; y: number }

const BOT_W = 78;
const BOT_H = 91;
const PAGE_NAME: Record<GuideAction["tab"], string> = {
  start: "Start here", overview: "Overview", calendar: "Burning calendar", historical: "Historical analysis", sensors: "Sensor harmonization",
  anomalies: "Unusual activity", data: "Data & downloads", method: "Methodology",
};
// Where the robot flies to point after opening a page.
const TARGET: Record<GuideAction["tab"], string[]> = {
  calendar: [".leaflet-container"],
  overview: [".current", "main h2"],
  historical: ["main .chart-frame", "main h2"],
  anomalies: ["main table", "main h2"],
  data: ["main .button", "main h2"],
  sensors: ["main h2"],
  method: ["main h2"],
  start: [".land-hero"],
};
const TIPS = [
  "Psst! Tell me a town and I'll fly you there on the map.",
  "Click me to chat, or drag me around!",
  "Try asking: “Was January unusual in Nigeria?”",
  "I can talk. Press the microphone and speak!",
  "Ghana has the full detail: 1, 2 and 5 km grids.",
  "Remember: detections are heat signals, not confirmed fires.",
  "Say “Tamale in March 2024” and watch the map.",
];
const POKES = ["Hehe, that tickles!", "Beep boop! How can I help?", "Whoa, careful! I'm full of satellite data.", "Hi again! Click me to chat.", "I'm fired up and ready!"];

const reducedMotion = () => typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const randomIn = (lo: number, hi: number) => lo + Math.random() * Math.max(0, hi - lo);

export default function TerraGuide({ open, onOpenChange, groups, currentArea, latest, onAction }: Props) {
  // ---------- conversation ----------
  const [step, setStep] = useState<Step>("role");
  const [role, setRole] = useState<RoleId | null>(null);
  const [goal, setGoal] = useState<GoalId | null>(null);
  const [areaList, setAreaList] = useState<"ghana" | "countries">("ghana");
  const [chosen, setChosen] = useState<Where | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [text, setText] = useState("");
  const [found, setFound] = useState<Place[] | null>(null);
  const [alternatives, setAlternatives] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const [pickYear, setPickYear] = useState<number>(latest?.year ?? 2025);
  const [pickMonth, setPickMonth] = useState<number>(latest?.month ?? 12);
  const [last, setLast] = useState<{ goal: GoalId; where: Where | null; action: GuideAction } | null>(null);
  const [mini, setMini] = useState(false);
  const [headline, setHeadline] = useState<string | null>(null); // the main answer, shown when the chat is small
  const pending = useRef<Pending>({ goal: null, month: null });
  const advised = useRef(false); // the role's caveat is said once per conversation
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const choicesBox = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);

  // ---------- voice ----------
  const [voiceOn, setVoiceOn] = useState(() => {
    try { return localStorage.getItem("terraguide-voice") !== "off"; } catch { return true; }
  });
  const [listening, setListening] = useState(false);
  const [talking, setTalking] = useState(0);
  const spoken = useRef(0);
  const stopListening = useRef<(() => void) | null>(null);

  // ---------- the robot ----------
  const [pos, setPos] = useState<Point>(() => ({ x: (typeof window !== "undefined" ? window.innerWidth : 1200) + 40, y: (typeof window !== "undefined" ? window.innerHeight : 800) - 220 }));
  const posRef = useRef(pos);
  const [flight, setFlight] = useState(1.2); // seconds for the current move
  const [moving, setMoving] = useState(false);
  const [lean, setLean] = useState(0); // tilt while flying, by direction
  const [trick, setTrick] = useState<"" | "spin" | "flip" | "dizzy" | "bounce">("");
  const [bubble, setBubble] = useState<string | null>(null);
  const [hover, setHover] = useState(false);
  const [happy, setHappy] = useState(false);
  const [pointing, setPointing] = useState(false);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ x: number; y: number; dx: number; dy: number; moved: boolean; t: number; fast: number } | null>(null);
  const timers = useRef<number[]>([]);
  const later = (fn: () => void, ms: number) => { const id = window.setTimeout(fn, ms); timers.current.push(id); return id; };
  useEffect(() => () => timers.current.forEach((id) => window.clearTimeout(id)), []);

  const mood: BotMood = listening ? "listening" : searching ? "thinking" : talking > 0 ? "speaking" : (happy || hover || dragging) ? "happy" : "idle";

  const say = (...next: Line[]) => setLines((l) => [...l, ...next]);
  const guide = (t: string): Line => ({ from: "guide", text: t });
  const you = (t: string): Line => ({ from: "you", text: t });

  const showBubble = (t: string, ms = 4500) => {
    setBubble(t);
    later(() => setBubble((b) => (b === t ? null : b)), ms);
  };

  const doTrick = (t: "spin" | "flip" | "dizzy" | "bounce", ms = 1100) => {
    setTrick(t);
    later(() => setTrick(""), ms);
  };

  /** Fly the robot to a point on the screen (top-left of the robot), at a speed that suits the distance. */
  const flyTo = (to: Point, speed = 520) => {
    const w = window.innerWidth, h = window.innerHeight;
    const next = { x: clamp(to.x, 6, w - BOT_W - 6), y: clamp(to.y, 6, h - BOT_H - 6) };
    const from = posRef.current;
    const dist = Math.hypot(next.x - from.x, next.y - from.y);
    if (dist < 2) return;
    const seconds = reducedMotion() ? 0 : clamp(dist / speed, 0.45, 2.4);
    setFlight(seconds);
    setLean(clamp((next.x - from.x) / 30, -14, 14));
    setMoving(true);
    posRef.current = next;
    setPos(next);
    later(() => { setMoving(false); setLean(0); }, seconds * 1000 + 50);
  };

  // Entrance: fly in from the right edge and say hello.
  useEffect(() => {
    let first = false;
    try { first = !localStorage.getItem("terraguide-seen"); } catch { /* ignore */ }
    later(() => {
      flyTo({ x: window.innerWidth - BOT_W - 28, y: window.innerHeight - BOT_H - 70 }, 700);
      later(() => {
        doTrick("bounce", 900);
        showBubble(first ? "Hi! I'm TerraGuide. Click me, or just talk to me: I'll find any place for you." : "Hi again! Click me if you need a hand.", first ? 7000 : 4000);
      }, 1400);
    }, 900);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Wander around the screen while the chat is closed, with the odd trick and tip.
  useEffect(() => {
    if (open || dragging || pointing || reducedMotion()) return;
    let n = 0;
    let id = 0;
    const wander = () => {
      n += 1;
      const w = window.innerWidth, h = window.innerHeight;
      const narrow = w < 700;
      const roll = Math.random();
      if (roll < 0.2) doTrick(Math.random() < 0.5 ? "spin" : "flip");
      else {
        flyTo({
          x: narrow ? randomIn(w - BOT_W - 140, w - BOT_W - 10) : randomIn(w * 0.55, w - BOT_W - 16),
          y: randomIn(Math.max(110, h * 0.32), h - BOT_H - 20),
        }, 260);
      }
      if (n % 3 === 0) later(() => showBubble(TIPS[Math.floor(Math.random() * TIPS.length)]), 1800);
      id = window.setTimeout(wander, randomIn(5200, 9500));
    };
    id = window.setTimeout(wander, 6500);
    return () => window.clearTimeout(id);
  }, [open, dragging, pointing]); // eslint-disable-line react-hooks/exhaustive-deps

  // Dock beside the chat panel while it is open.
  const dock = () => {
    const box = panel.current?.getBoundingClientRect();
    if (!box) return;
    if (box.left > BOT_W + 16) flyTo({ x: box.left - BOT_W - 4, y: box.top + 4 }, 900);
    else flyTo({ x: box.left + 10, y: box.top - BOT_H + 10 }, 900); // narrow screens: sit on top of the panel
  };
  useLayoutEffect(() => {
    if (!open || pointing || dragging) return;
    const id = window.setTimeout(dock, 420); // after the panel's opening animation, so its position is final
    window.addEventListener("resize", dock);
    return () => { window.clearTimeout(id); window.removeEventListener("resize", dock); };
  }, [open, mini, pointing, dragging]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the robot on screen when the window changes size.
  useEffect(() => {
    const keep = () => {
      const p = posRef.current;
      const x = clamp(p.x, 6, window.innerWidth - BOT_W - 6), y = clamp(p.y, 6, window.innerHeight - BOT_H - 6);
      if (x !== p.x || y !== p.y) { posRef.current = { x, y }; setFlight(0); setPos({ x, y }); }
    };
    window.addEventListener("resize", keep);
    return () => window.removeEventListener("resize", keep);
  }, []);

  /** After opening a page: scroll to the part that answers the question, fly there and point at it. */
  const pointAt = (selectors: string[], message: string, centre: boolean) => {
    let tries = 0;
    const find = () => {
      const el = selectors.map((s) => document.querySelector<HTMLElement>(s)).find(Boolean);
      if (!el) {
        tries += 1;
        if (tries < 12) later(find, 250);
        return;
      }
      el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: centre ? "center" : "start" });
      setPointing(true);
      later(() => {
        const r = el.getBoundingClientRect();
        const target = centre
          ? { x: r.left + r.width / 2 - BOT_W - 26, y: r.top + r.height / 2 - BOT_H * 0.75 } // beside the place, which the map has centred
          : { x: r.left + Math.min(r.width * 0.55, 420), y: r.top - BOT_H * 0.35 };
        flyTo(target, 650);
        later(() => { doTrick("bounce", 900); showBubble(message, 6500); }, 900);
        later(() => setPointing(false), 7500);
      }, 700);
    };
    later(find, 350);
  };

  // ---------- conversation effects ----------
  useEffect(() => {
    if (open && lines.length === 0) {
      setLines([guide("Hi, I'm TerraGuide! Tell me a place, ask a question, or pick an option. What brings you to TerraGuard?")]);
    }
  }, [open, lines.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [lines, step, found, mini]);
  useEffect(() => {
    if (latest) { setPickYear(latest.year); setPickMonth(latest.month); }
  }, [latest]);
  useEffect(() => {
    if (!open) return;
    try { localStorage.setItem("terraguide-seen", "1"); } catch { /* ignore */ }
    setBubble(null);
    const close = (e: KeyboardEvent) => e.key === "Escape" && onOpenChange(false);
    window.addEventListener("keydown", close);
    later(() => input.current?.focus({ preventScroll: true }), 200);
    return () => window.removeEventListener("keydown", close);
  }, [open, onOpenChange]); // eslint-disable-line react-hooks/exhaustive-deps

  // Read new guide lines aloud.
  useEffect(() => {
    if (lines.length < spoken.current) spoken.current = 0;
    const fresh = lines.slice(spoken.current);
    spoken.current = lines.length;
    if (!open || !voiceOn || !canSpeak) return;
    fresh.filter((l) => l.from === "guide").forEach((l) =>
      speak(l.text, () => setTalking((k) => k + 1), () => setTalking((k) => Math.max(0, k - 1))));
  }, [lines, open, voiceOn]);
  useEffect(() => {
    if (open) return;
    stopSpeaking();
    stopListening.current?.();
    setTalking(0);
    setMini(false);
  }, [open]);

  const toggleVoice = (on = !voiceOn) => {
    setVoiceOn(on);
    if (!on) { stopSpeaking(); setTalking(0); }
    try { localStorage.setItem("terraguide-voice", on ? "on" : "off"); } catch { /* ignore */ }
  };

  const celebrate = () => {
    setHappy(true);
    later(() => setHappy(false), 1800);
  };

  const restart = () => {
    advised.current = false;
    pending.current = { goal: null, month: null };
    setStep("role"); setRole(null); setGoal(null); setChosen(null); setFound(null); setAlternatives([]); setText(""); setLast(null); setMini(false);
    setLines([guide("Let's start again! Tell me a place or a question, or pick who you are.")]);
  };

  const latestYearFor = (month: number) => (!latest ? 2025 : month <= latest.month ? latest.year : latest.year - 1);
  const monthFrom = (req: { month: number | null; year: number | null }): Selection | null => {
    if (!req.month) return null;
    const m = { month: req.month, year: req.year ?? latestYearFor(req.month) };
    if (latest && m.year * 12 + m.month > latest.year * 12 + latest.month) return latest;
    return m;
  };
  const isGhana = (name: string) => name === "Ghana" || (groups?.find((x) => x.label === "Ghana regions")?.areas.some((a) => a.name === name) ?? false);
  const matchArea = (words: string): string | null => {
    const all = groups?.flatMap((x) => x.areas.map((a) => a.name)) ?? [];
    const lower = words.toLowerCase().trim();
    const plain = (a: string) => a.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    return all.find((a) => lower === plain(a) || lower === a.toLowerCase())
      ?? all.find((a) => a.length > 3 && (` ${lower} `).includes(` ${plain(a)} `))
      ?? null;
  };
  const whereFor = (p: Place): Where => (p.kind === "country"
    ? { area: matchArea(p.name) ?? p.name, label: p.name }
    : p.kind === "region" && p.country_code === "GH"
      ? { area: p.region ?? p.name.replace(/ Region$/, ""), label: p.name }
      : { place: p, label: `${p.name}, ${p.country}` });

  const lookUp = async (q: string): Promise<Place[]> => {
    setSearching(true);
    try {
      return (await api.searchPlaces(q, 6)).data;
    } catch {
      return [];
    } finally {
      setSearching(false);
    }
  };

  // ---------- steps ----------
  const chooseRole = (r: RoleId, echo = true) => {
    setRole(r);
    if (echo) say(you(ROLES.find((x) => x.id === r)!.label));
    say(guide("What are you trying to find? Pick a question, say a place, or type your own."));
    setStep("goal");
  };

  const askArea = (g: GoalId) => {
    say(guide(g === "map" ? "Which area should I show you?" : `Which area are you interested in? You are looking at ${currentArea} now.`));
    setStep("area");
  };

  const chooseGoal = (g: GoalId, echo = true) => {
    setGoal(g);
    pending.current = { goal: g, month: pending.current.month };
    if (echo) say(you(GOALS[g].label));
    if (GOALS[g].needsArea) askArea(g);
    else finish(g, null, null);
  };

  /** Everything known: the question, the place and (maybe) the month. askMonth: ask instead of assuming the latest month. */
  const complete = (g: GoalId, where: Where, month: Selection | null, askMonth: boolean) => {
    setGoal(g);
    setChosen(where);
    setFound(null);
    if (GOALS[g].needsMonth && !month) {
      if (askMonth || !latest) {
        say(guide(`${where.label}: which month?`));
        setStep("month");
        return;
      }
      return finish(g, where, latest, true);
    }
    finish(g, where, month);
  };

  const pickArea = (name: string, echo = true) => {
    if (echo) say(you(name));
    const g = goal ?? pending.current.goal ?? "map";
    const month = pending.current.month;
    pending.current = { goal: null, month: null };
    complete(g, { area: name, label: name }, month, true);
  };

  const pickPlace = (p: Place, echo = true) => {
    if (echo) say(you(`${p.name}, ${p.country}`));
    if (!p.covered) {
      say(guide(`${p.country} is outside the area TerraGuard covers (Ghana and the 15 other West African countries). Try another place.`));
      return;
    }
    const g = pending.current.goal ?? goal ?? "map";
    const month = pending.current.month;
    pending.current = { goal: null, month: null };
    setAlternatives([]);
    complete(g, whereFor(p), month, false);
  };

  const chooseMonth = (m: Selection, echo = true) => {
    if (echo) say(you(`${MONTHS[m.month - 1]} ${m.year}`));
    finish(goal ?? "map", chosen, m);
  };

  const finish = (g: GoalId, where: Where | null, month: Selection | null, assumedMonth = false) => {
    const spec = GOALS[g];
    const action: GuideAction = { tab: spec.tab, steady: spec.steady, area: where?.area, place: where?.place, month: month ?? undefined };
    onAction(action);
    setLast({ goal: g, where, action });
    const page = PAGE_NAME[spec.tab];
    const out: Line[] = [];
    if (spec.tab === "calendar" && where) {
      out.push(guide(`Found it! I flew the map to ${where.label}${month ? ` and opened ${MONTHS[month.month - 1]} ${month.year}` : ""}.`));
      if (assumedMonth) out.push(guide("That's the latest full month. Say or type another month, like “March 2024”, to change it."));
    } else {
      out.push(guide(`Done: I opened ${page}${where ? ` for ${where.label}` : ""}${month ? `, ${MONTHS[month.month - 1]} ${month.year}` : ""}. What to look at:`));
    }
    spec.look.forEach((t) => out.push(guide(`• ${t}`)));
    if (where?.place) out.push(guide(`• The area is a box of about 25 km around ${where.place.name}. Change its size in the bar above the page.`));
    else if (where?.area && !isGhana(where.area) && where.area !== "West Africa") out.push(guide("• Outside Ghana the data is country-level on a 5 km grid. Ghana has the full detail."));
    if (!advised.current) { out.push(guide(`Good to know: ${ADVICE[role ?? "explorer"]}`)); advised.current = true; }
    setHeadline(out[0].text);
    say(...out);
    setStep("done");
    celebrate();
    const locating = spec.tab === "calendar" && Boolean(where);
    if (locating) setMini(true); // get out of the way of the map
    pointAt(TARGET[spec.tab], locating ? `Here's ${where!.label}!` : `Here's ${page}!`, locating);
  };

  // ---------- understanding what was typed or said ----------
  const roleFrom = (lower: string): RoleId | null => {
    const roleWords: [RoleId, RegExp][] = [
      ["responder", /emergenc|early warning|responder|disaster|nadmo|rescue/],
      ["firefighter", /fire ?fight|fireman|firemen|fire service|fire planning|gnfs/],
      ["manager", /farmer|forest|land manag|ranger|agricult|plantation|park manag/],
      ["scientist", /scien|research|student|lecturer|professor|academic|analyst/],
      ["explorer", /^(just )?explor|curious|just looking|browsing|journalist|citizen/],
    ];
    return roleWords.find(([, re]) => re.test(lower))?.[0] ?? null;
  };

  /** A request in the visitor's own words: a question, a place, a month, or any mix. */
  const freeRequest = async (value: string) => {
    const req = readRequest(value);
    // A new place after an answer keeps the month being looked at, unless another is named.
    const named = monthFrom(req);
    const month = named ?? (step === "done" && !req.goal ? last?.action.month ?? null : null);
    let g = req.goal;
    if (!role) setRole("explorer");
    // Only a month, after something was shown: show the same place in that month.
    if (!g && !req.rest && named && last) {
      return complete(last.goal === "map" || GOALS[last.goal].needsMonth ? last.goal : "map", last.where ?? { area: currentArea, label: currentArea }, named, false);
    }
    if (!g && !req.rest) {
      say(guide("Hmm, I'm not sure what you mean. Name a place (like “Tamale”), ask a question (like “is burning unusual now?”), or pick one below."));
      setStep("goal");
      return;
    }
    if (g && !GOALS[g].needsArea) return finish(g, null, null);
    if (req.rest) {
      const area = matchArea(req.rest);
      if (area) return complete(g ?? "map", { area, label: area }, month, false);
      say(guide(`Let me find “${req.rest}”…`));
      const places = await lookUp(req.rest);
      const covered = places.filter((p) => p.covered);
      if (!places.length) {
        say(guide(`I couldn't find “${req.rest}” in West Africa. Try another spelling, a nearby town, or pick an area.`));
        pending.current = { goal: g ?? "map", month };
        setGoal(g ?? "map");
        setStep("area");
        return;
      }
      const target = req.rest.toLowerCase();
      const best = covered.find((p) => p.name.toLowerCase() === target) ?? (covered.length === 1 ? covered[0] : null)
        ?? (covered[0] && covered[0].name.toLowerCase().startsWith(target) ? covered[0] : null);
      if (best) {
        setAlternatives(places.filter((p) => p !== best && p.covered).slice(0, 3));
        return complete(g ?? "map", whereFor(best), month, false);
      }
      pending.current = { goal: g ?? "map", month };
      setGoal(g ?? "map");
      setFound(places);
      say(guide("I found a few. Which one do you mean?"));
      setStep("town");
      return;
    }
    g = g!;
    pending.current = { goal: g, month };
    setGoal(g);
    say(guide(`Got it: ${GOALS[g].label}`));
    askArea(g);
  };

  /** One place for everything the visitor types or says, so both work at every step. */
  const handleInput = (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    setText("");
    const lower = value.toLowerCase();
    if (/^(close|goodbye|bye|hide|that is all|that's all)\b/.test(lower)) { say(you(value)); onOpenChange(false); return; }
    if (/\b(restart|start again|start over)\b/.test(lower)) { restart(); return; }
    if (/\b(mute|be quiet|stop talking|silence)\b/.test(lower)) { say(you(value), guide("Okay, I'll stay quiet. Press the speaker to hear me again.")); toggleVoice(false); return; }
    if (/\b(unmute|voice on|talk to me|speak up)\b/.test(lower)) { toggleVoice(true); say(you(value), guide("I'm back! I'll read my answers aloud.")); return; }
    if (/\b(spin|dance|do a trick|flip)\b/.test(lower)) { say(you(value), guide("Wheee! Now, where shall we go?")); doTrick(/flip/.test(lower) ? "flip" : "spin", 1200); return; }

    // The buttons on screen first ("firefighter", "Northern", "all of Ghana"), except after an answer.
    if (step !== "done" && step !== "town") {
      if (step === "role") {
        const r = roleFrom(lower);
        if (r) { say(you(value)); return chooseRole(r, false); }
      }
      if (step === "month" || step === "month-pick") {
        const m = monthFrom(readRequest(value));
        if (m) { say(you(value)); return chooseMonth(m, false); }
      }
      const buttons = [...(choicesBox.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
      const pick = matchChoice(value, buttons.map((b) => b.textContent ?? ""));
      if (pick !== null) { buttons[pick].click(); return; }
    }
    say(you(value));
    if (step === "month" || step === "month-pick") {
      say(guide("Say or type a month and a year, for example “March 2024”, or tap one below."));
      return;
    }
    if (step === "area" || step === "area-list" || step === "town") {
      const area = matchArea(value);
      if (area) return pickArea(area, false);
      const req = readRequest(value);
      if (!req.goal || !req.rest) {
        // A place name on its own: look it up for the question already asked.
        void (async () => {
          const places = await lookUp(req.rest || value);
          const covered = places.filter((p) => p.covered);
          const exact = covered.find((p) => p.name.toLowerCase() === (req.rest || value).toLowerCase()) ?? (covered.length === 1 ? covered[0] : null);
          if (exact) { setAlternatives(places.filter((p) => p !== exact && p.covered).slice(0, 3)); return pickPlace(exact, false); }
          setFound(places);
          setStep("town");
          say(guide(places.length ? "Which one do you mean?" : `I couldn't find “${value}”. Try another spelling or a nearby town.`));
        })();
        return;
      }
    }
    void freeRequest(value);
  };
  const handleRef = useRef(handleInput);
  handleRef.current = handleInput;

  const toggleMic = () => {
    if (listening) { stopListening.current?.(); return; }
    setListening(true);
    setText("");
    stopListening.current = listen({
      onInterim: (t) => setText(t),
      onFinal: (t) => handleRef.current(t),
      onError: (m) => say(guide(m)),
      onEnd: () => { setListening(false); stopListening.current = null; },
    });
  };

  // ---------- touching the robot ----------
  const onBotDown = (e: React.PointerEvent) => {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, dx: e.clientX - posRef.current.x, dy: e.clientY - posRef.current.y, moved: false, t: performance.now(), fast: 0 };
  };
  const onBotMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    if (!d.moved && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 6) return;
    if (!d.moved) { d.moved = true; setDragging(true); setFlight(0); }
    const now = performance.now();
    const speed = Math.hypot(e.movementX, e.movementY) / Math.max(1, now - d.t);
    d.t = now;
    if (speed > 2.2) d.fast += 1;
    setLean(clamp(e.movementX * 1.5, -25, 25));
    const next = { x: clamp(e.clientX - d.dx, 0, window.innerWidth - BOT_W), y: clamp(e.clientY - d.dy, 0, window.innerHeight - BOT_H) };
    posRef.current = next;
    setPos(next);
  };
  const onBotUp = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.moved) {
      setDragging(false);
      setLean(0);
      if (d.fast > 6) { doTrick("dizzy", 1800); showBubble("Whoa… so dizzy! 😵"); }
      else showBubble(open ? "Wheee! I'll pop back beside the chat." : "Wheee! Thanks for the ride.");
      if (open) later(dock, 1800);
      return;
    }
    // A click: open the chat, or expand it, or have a little fun.
    if (!open) { onOpenChange(true); doTrick("bounce", 800); }
    else if (mini) setMini(false);
    else { doTrick(Math.random() < 0.5 ? "spin" : "flip"); showBubble(POKES[Math.floor(Math.random() * POKES.length)], 2500); }
  };

  // ---------- drawing ----------
  const goals = role ? ORDER[role] : (Object.keys(GOALS) as GoalId[]);
  const ghanaRegions = groups?.find((x) => x.label === "Ghana regions")?.areas.map((a) => a.name) ?? [];
  const countries = groups?.filter((x) => x.label !== "Ghana" && x.label !== "Ghana regions" && x.label !== "West Africa").flatMap((x) => x.areas.map((a) => a.name)) ?? [];
  const years = latest ? Array.from({ length: latest.year - FIRST_YEAR + 1 }, (_, i) => latest.year - i) : [];
  const lastGuide = [...lines].reverse().find((l) => l.from === "guide")?.text ?? "";
  const status = { idle: "Ready to help", listening: "Listening… speak now", thinking: "Looking that up…", speaking: "Speaking…", happy: "Here you go!" }[mood];
  const bubbleLeft = pos.x > window.innerWidth / 2;

  return (
    <>
      <div
        className={`companion${moving ? " moving" : ""}${dragging ? " dragging" : ""}${pointing ? " pointing" : ""}`}
        style={{ transform: `translate3d(${pos.x}px, ${pos.y}px, 0)`, transitionDuration: `${flight}s` }}
      >
        {bubble && !dragging && (!open || pointing || mini) && (
          <div className={`bot-bubble ${bubbleLeft ? "left" : "right"}`} role="status">
            {bubble}
          </div>
        )}
        <button
          type="button"
          className={`companion-body${trick ? ` trick-${trick}` : ""}`}
          style={{ ["--lean" as string]: `${lean}deg` }}
          onPointerDown={onBotDown}
          onPointerMove={onBotMove}
          onPointerUp={onBotUp}
          onPointerCancel={() => { drag.current = null; setDragging(false); }}
          onPointerEnter={() => setHover(true)}
          onPointerLeave={() => setHover(false)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!open) onOpenChange(true); else setMini(false); } }}
          aria-label={open ? "TerraGuide (drag me, or click to show the chat)" : "Open TerraGuide, the talking guide (you can also drag me)"}
        >
          <GuideBot size={BOT_W} mood={mood} waving={hover || happy || trick === "bounce"} />
        </button>
      </div>

      {open && (
        <section ref={panel} className={`guide-panel${mini ? " mini" : ""}`} role="dialog" aria-label="TerraGuide">
          <header>
            <div className="guide-title">
              <b>TerraGuide</b>
              <small className={`guide-status s-${mood}`}><span className="dot" />{status}</small>
            </div>
            {canSpeak && (
              <button type="button" className={`tool guide-voice${voiceOn ? " on" : ""}`} onClick={() => toggleVoice()} aria-pressed={voiceOn}
                aria-label={voiceOn ? "Mute TerraGuide's voice" : "Turn on TerraGuide's voice"} title={voiceOn ? "Voice on: click to mute" : "Voice off: click to hear answers"}>
                {voiceOn ? "🔊" : "🔇"}
              </button>
            )}
            <button type="button" className="tool" onClick={restart} title="Start again" aria-label="Start again">↺</button>
            <button type="button" className="tool" onClick={() => setMini((m) => !m)} aria-label={mini ? "Show the conversation" : "Make the chat small"} title={mini ? "Expand" : "Minimise"}>
              {mini ? "▴" : "▾"}
            </button>
            <button type="button" className="chip-x" onClick={() => onOpenChange(false)} aria-label="Close TerraGuide">✕</button>
          </header>

          {mini ? (
            <button type="button" className="guide-ticker" onClick={() => setMini(false)} title="Show the conversation">
              {(step === "done" && headline ? headline : lastGuide).replace(/^•\s*/, "")} <span className="muted">· tap to expand</span>
            </button>
          ) : (
            <div className="guide-log" ref={log} aria-live="polite">
              {lines.map((l, i) => <p key={i} className={`guide-line ${l.from}`}>{l.text}</p>)}
              {searching && <p className="guide-line guide typing" aria-label="TerraGuide is looking"><span /><span /><span /></p>}

              <div className="guide-choices" ref={choicesBox}>
                {step === "role" && ROLES.map((r) => <button key={r.id} type="button" onClick={() => chooseRole(r.id)}>{r.label}</button>)}

                {step === "goal" && goals.map((g) => <button key={g} type="button" onClick={() => chooseGoal(g)}>{GOALS[g].label}</button>)}

                {step === "area" && (
                  <>
                    <button type="button" onClick={() => pickArea("Ghana")}>All of Ghana</button>
                    <button type="button" onClick={() => { setAreaList("ghana"); say(you("A region of Ghana"), guide("Which region?")); setStep("area-list"); }}>A region of Ghana</button>
                    <button type="button" onClick={() => { setAreaList("countries"); say(you("Another West African country"), guide("Which country?")); setStep("area-list"); }}>Another West African country</button>
                    <button type="button" onClick={() => pickArea("West Africa")}>All of West Africa</button>
                    <button type="button" onClick={() => { say(you("A town or village"), guide("Type or say the name of the town or village.")); setStep("town"); later(() => input.current?.focus(), 0); }}>A town or village</button>
                    {currentArea !== "Ghana" && <button type="button" onClick={() => pickArea(currentArea)}>Keep {currentArea}</button>}
                  </>
                )}

                {step === "area-list" && (areaList === "ghana" ? ghanaRegions : countries).map((a) => (
                  <button key={a} type="button" className="small" onClick={() => pickArea(a)}>{a}</button>
                ))}

                {step === "town" && found?.map((p) => (
                  <button key={`${p.id}-${p.name}-${p.lat}`} type="button" onClick={() => pickPlace(p)}>
                    📍 {p.name} <small>{[p.admin1, p.country].filter(Boolean).join(", ")}{p.covered ? "" : " (not covered)"}</small>
                  </button>
                ))}

                {step === "month" && (
                  <>
                    {latest && <button type="button" onClick={() => chooseMonth(latest)}>Latest full month ({MONTHS[latest.month - 1]} {latest.year})</button>}
                    <button type="button" onClick={() => chooseMonth({ year: latestYearFor(1), month: 1 })}>January {latestYearFor(1)} (Ghana's peak month)</button>
                    <button type="button" onClick={() => chooseMonth({ year: 2025, month: 12 })}>December 2025 (unusually quiet in Ghana)</button>
                    <button type="button" onClick={() => { say(you("Another month")); setStep("month-pick"); }}>Another month…</button>
                  </>
                )}
                {step === "month-pick" && (
                  <div className="guide-pick">
                    <select value={pickMonth} onChange={(e) => setPickMonth(Number(e.target.value))} aria-label="Month">
                      {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
                    </select>
                    <select value={pickYear} onChange={(e) => setPickYear(Number(e.target.value))} aria-label="Year">
                      {years.map((y) => <option key={y}>{y}</option>)}
                    </select>
                    <button type="button" className="primary" onClick={() => chooseMonth({ year: pickYear, month: pickMonth })}>Show</button>
                  </div>
                )}

                {step === "done" && (
                  <>
                    {last && <button type="button" onClick={() => { onAction(last.action); const t = last.action.tab; pointAt(TARGET[t], last.where ? `Here's ${last.where.label}!` : `Here's ${PAGE_NAME[t]}!`, t === "calendar" && Boolean(last.where)); }}>🎯 Show me again</button>}
                    {last?.where && <button type="button" onClick={() => { setGoal("map"); say(you("Another month"), guide(`${last.where!.label}: which month?`)); setChosen(last.where); setStep("month"); }}>📅 Another month</button>}
                    {alternatives.map((p) => (
                      <button key={`alt-${p.id}-${p.lat}`} type="button" onClick={() => { say(you(`${p.name}, ${p.country}`)); setAlternatives((a) => a.filter((x) => x !== p)); complete(last?.goal ?? "map", whereFor(p), last?.action.month ?? null, false); }}>
                        Not it? {p.name} <small>{[p.admin1, p.country].filter(Boolean).join(", ")}</small>
                      </button>
                    ))}
                    <button type="button" onClick={() => { say(guide("What else would you like to find? Say a place or a question.")); setStep("goal"); }}>✨ Find something else</button>
                  </>
                )}
              </div>
            </div>
          )}

          <form className="guide-input" onSubmit={(e) => { e.preventDefault(); handleInput(text); }}>
            {canListen && (
              <button type="button" className={`guide-mic${listening ? " live" : ""}`} onClick={toggleMic} aria-pressed={listening}
                aria-label={listening ? "Stop listening" : "Speak to TerraGuide"}
                title="Speak to TerraGuide. Your browser's speech service turns your voice into text (Chrome sends it to Google, Edge to Microsoft).">
                <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V22h2v-3.08A7 7 0 0 0 19 12h-2Z" /></svg>
                {listening && <span className="mic-wave" aria-hidden="true"><i /><i /><i /><i /></span>}
              </button>
            )}
            <input
              ref={input}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={listening ? "Listening… speak now" : step === "town" ? "Town or village, e.g. Tamale" : "Type a place or a question, e.g. “Tamale in March 2024”"}
              aria-label="Type a place or a question"
              readOnly={listening}
            />
            <button type="submit" className="primary" disabled={!text.trim()} aria-label="Send">➤</button>
          </form>
        </section>
      )}
    </>
  );
}
