/* GLCR Ops — Wireframes
 * Dark ops HUD direction. iPad-first (1180×820 portrait-ish landscape).
 * Wireframe fidelity: structure + hierarchy, not final pixel polish.
 */

const { useState, useEffect } = React;

// ── Tokens ────────────────────────────────────────────────────────────────
const T = {
  bg:      "#0E0F11",
  panel:   "#16181B",
  panel2:  "#1C1F23",
  line:    "#26292E",
  line2:   "#33373D",
  ink:     "#F2EFE7",
  ink2:    "#B8B4A8",
  ink3:    "#7A7770",
  mute:    "#4D4B45",
  blue:    "#5CC0FF",
  blueDim: "rgba(92,192,255,0.12)",
  gold:    "#E0CBB6",
  goldDim: "rgba(224,203,182,0.10)",
  green:   "#4ADE80",
  greenDim:"rgba(74,222,128,0.12)",
  red:     "#F87171",
  redDim:  "rgba(248,113,113,0.12)",
  amber:   "#FBBF24",
  amberDim:"rgba(251,191,36,0.12)",
  font:    "'Barlow', system-ui, sans-serif",
  serif:   "'PT Serif', Georgia, serif",
  mono:    "ui-monospace, 'SF Mono', Menlo, monospace",
};

// ── Atoms ─────────────────────────────────────────────────────────────────
const Eyebrow = ({ children, color = T.ink3, style }) => (
  <div style={{
    fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
    textTransform: "uppercase", color, ...style,
  }}>{children}</div>
);

const Rule = ({ color = T.line, style }) => (
  <div style={{ height: 1, background: color, ...style }} />
);

const GoldRule = () => (
  <div style={{
    height: 2, width: 28, background: T.gold, marginTop: 4, marginBottom: 10,
  }} />
);

const Pill = ({ children, color = T.ink2, bg = T.panel2, border = T.line, style }) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: 4,
    fontSize: 10, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase",
    padding: "3px 8px", borderRadius: 999, color, background: bg,
    border: `1px solid ${border}`, ...style,
  }}>{children}</span>
);

const Dot = ({ c = T.ink3, size = 6, style }) => (
  <span style={{
    display: "inline-block", width: size, height: size, borderRadius: 999,
    background: c, ...style,
  }} />
);

const Section = ({ title, right, children, style }) => (
  <div style={style}>
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
      <Eyebrow color={T.ink2}>{title}</Eyebrow>
      {right}
    </div>
    <GoldRule />
    {children}
  </div>
);

// ── Shift HUD — Variant A: Command Grid ───────────────────────────────────
function ShiftHUD_A() {
  return (
    <div style={{
      width: 1180, height: 820, background: T.bg, color: T.ink, fontFamily: T.font,
      display: "grid", gridTemplateColumns: "60px 1fr", overflow: "hidden",
    }}>
      {/* Rail */}
      <div style={{
        background: T.panel, borderRight: `1px solid ${T.line}`,
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "16px 0", gap: 8,
      }}>
        <div style={{ width: 28, height: 28, borderRadius: 6, background: T.blue }} />
        <div style={{ height: 12 }} />
        {["◎","⊙","▦","⌕","◍","☐","✦","♥"].map((g,i) => (
          <div key={i} style={{
            width: 36, height: 36, borderRadius: 8, display: "grid", placeItems: "center",
            color: i === 1 ? T.blue : T.ink3, background: i === 1 ? T.blueDim : "transparent",
            fontSize: 14,
          }}>{g}</div>
        ))}
      </div>

      {/* Main */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Top bar */}
        <div style={{
          display: "flex", alignItems: "center", gap: 16, padding: "14px 24px",
          borderBottom: `1px solid ${T.line}`, background: T.panel,
        }}>
          <div>
            <Eyebrow>Wed · May 6 · Grave</Eyebrow>
            <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", marginTop: 2 }}>
              Good evening, Brian.
            </div>
          </div>
          <div style={{ flex: 1 }} />
          {/* Shift countdown */}
          <div style={{
            display: "flex", alignItems: "center", gap: 10, padding: "6px 14px",
            border: `1px solid ${T.line2}`, borderRadius: 8, background: T.panel2,
          }}>
            <Dot c={T.green} />
            <div>
              <div style={{ fontSize: 9, color: T.ink3, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                Shift
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 14, color: T.ink }}>
                01:42 elapsed · 06:18 left
              </div>
            </div>
          </div>
          <Pill color={T.gold} bg={T.goldDim} border={T.gold}>● Live</Pill>
        </div>

        {/* HUD scoreboard strip */}
        <div style={{
          display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr 1fr", gap: 1,
          background: T.line, borderBottom: `1px solid ${T.line}`,
        }}>
          {/* Deployment fill */}
          <div style={{ background: T.panel, padding: "14px 20px" }}>
            <Eyebrow>Tonight's deployment</Eyebrow>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 6 }}>
              <div style={{ fontSize: 32, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>18</div>
              <div style={{ color: T.ink3, fontSize: 14 }}>/ 22 filled</div>
              <div style={{ marginLeft: "auto", color: T.gold, fontSize: 12, fontWeight: 600 }}>82%</div>
            </div>
            <div style={{ height: 4, background: T.panel2, borderRadius: 999, marginTop: 6, overflow: "hidden" }}>
              <div style={{ width: "82%", height: "100%", background: T.gold }} />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 8, fontSize: 11, color: T.ink3 }}>
              <span><Dot c={T.red} /> 4 open</span>
              <span><Dot c={T.amber} /> 2 warn</span>
              <span><Dot c={T.gold} /> 6 locked</span>
            </div>
          </div>
          {/* Roster */}
          <div style={{ background: T.panel, padding: "14px 20px" }}>
            <Eyebrow>On floor</Eyebrow>
            <div style={{ fontSize: 32, fontWeight: 700, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>14</div>
            <div style={{ fontSize: 11, color: T.ink3, marginTop: 2 }}>
              <span style={{ color: T.red }}>2 called off</span> · 1 late
            </div>
          </div>
          {/* Break wave */}
          <div style={{ background: T.panel, padding: "14px 20px" }}>
            <Eyebrow>Active wave</Eyebrow>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 6 }}>
              <div style={{ fontSize: 32, fontWeight: 700, color: T.blue }}>2</div>
              <div style={{ color: T.ink3, fontSize: 12 }}>02:30 – 03:00</div>
            </div>
            <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
              {[1,2,3].map(w => (
                <div key={w} style={{
                  flex: 1, height: 4, borderRadius: 2,
                  background: w === 2 ? T.blue : w === 1 ? T.line2 : T.panel2,
                  opacity: w === 1 ? 0.5 : 1,
                }} />
              ))}
            </div>
            <div style={{ fontSize: 11, color: T.ink3, marginTop: 6 }}>
              W1 done · <strong style={{ color: T.ink }}>W2 active</strong> · W3 12:30
            </div>
          </div>
          {/* Open tasks */}
          <div style={{ background: T.panel, padding: "14px 20px" }}>
            <Eyebrow>Open tonight</Eyebrow>
            <div style={{ fontSize: 32, fontWeight: 700, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>7</div>
            <div style={{ fontSize: 11, color: T.amber, marginTop: 2 }}>2 overdue</div>
          </div>
        </div>

        {/* Body grid */}
        <div style={{
          flex: 1, display: "grid", gridTemplateColumns: "1.3fr 1fr 0.9fr",
          gap: 1, background: T.line, overflow: "hidden",
        }}>
          {/* Col 1 — Deployment mini-map */}
          <div style={{ background: T.bg, padding: 20, overflow: "hidden" }}>
            <Section
              title="Deployment · Tonight"
              right={<a style={{ fontSize: 11, color: T.blue }}>Open in ZDS →</a>}
            >
              {/* 5×2 zone grid (mini) */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6 }}>
                {[
                  {z:"Z1", n:"Marquez",   s:"ok"},
                  {z:"Z2", n:"Patel",     s:"ok"},
                  {z:"Z3", n:"—",         s:"open"},
                  {z:"Z4", n:"Kim",       s:"lock"},
                  {z:"Z5", n:"Joy",       s:"warn"},
                  {z:"Z6", n:"Reyes",     s:"ok"},
                  {z:"Z7", n:"—",         s:"open"},
                  {z:"Z8", n:"Nguyen",    s:"ok"},
                  {z:"Z9", n:"Tran",      s:"lock"},
                  {z:"Z10",n:"Foster",    s:"ok"},
                ].map((c,i) => {
                  const bd = c.s === "open" ? T.red : c.s === "warn" ? T.amber : c.s === "lock" ? T.gold : T.line2;
                  const bg = c.s === "open" ? T.redDim : c.s === "warn" ? T.amberDim : T.panel2;
                  return (
                    <div key={i} style={{
                      background: bg, border: `1px solid ${bd}`, borderRadius: 6,
                      padding: "8px 10px", minHeight: 56,
                    }}>
                      <div style={{ fontSize: 9, letterSpacing: "0.08em", color: T.ink3 }}>{c.z}</div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: c.n === "—" ? T.mute : T.ink, marginTop: 2 }}>
                        {c.n}
                      </div>
                    </div>
                  );
                })}
              </div>
              {/* RR strip */}
              <div style={{ marginTop: 14 }}>
                <Eyebrow style={{ marginBottom: 6 }}>Restrooms</Eyebrow>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6 }}>
                  {["RR1","RR2","RR3","RR4","RR5"].map((r,i) => (
                    <div key={r} style={{
                      background: T.panel2, border: `1px solid ${T.line2}`, borderRadius: 6,
                      padding: "6px 8px", fontSize: 11, color: T.ink2,
                    }}>
                      <div style={{ fontSize: 9, color: T.ink3 }}>{r}</div>
                      <div>{i === 2 ? "—" : ["Lopez","Brooks","","Diaz","Singh"][i]}</div>
                    </div>
                  ))}
                </div>
              </div>
              {/* Aux strip */}
              <div style={{ marginTop: 12 }}>
                <Eyebrow style={{ marginBottom: 6 }}>Auxiliary</Eyebrow>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4 }}>
                  {["Lobby","Valet","BOH","Cage","Buf","Dock","Float"].map((a,i) => (
                    <div key={a} style={{
                      background: T.panel2, border: `1px solid ${T.line}`, borderRadius: 4,
                      padding: "4px 6px", fontSize: 10, textAlign: "center", color: T.ink2,
                    }}>{a}</div>
                  ))}
                </div>
              </div>
            </Section>
          </div>

          {/* Col 2 — Roster + tasks */}
          <div style={{ background: T.bg, padding: 20, overflow: "hidden", display: "flex", flexDirection: "column", gap: 18 }}>
            <Section title="Tonight's roster">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {[
                  ["Marquez","g"],["Patel","g"],["Kim","g"],["Joy","g"],["Reyes","g"],
                  ["Nguyen","g"],["Tran","g"],["Foster","g"],["Lopez","g"],["Brooks","g"],
                  ["Diaz","p"],["Singh","p"],["Cole","a"],["Park","a"],
                  ["Ortega","x"],["Ramos","x"],
                ].map(([n,k]) => (
                  <span key={n} style={{
                    fontSize: 11, padding: "3px 8px", borderRadius: 999,
                    background: k === "x" ? T.redDim : k === "a" ? "rgba(30,58,138,0.3)" : k === "p" ? T.amberDim : T.greenDim,
                    color: k === "x" ? T.red : k === "a" ? T.blue : k === "p" ? T.amber : T.green,
                    border: `1px solid ${k === "x" ? T.red : k === "a" ? T.blue : k === "p" ? T.amber : T.green}`,
                    textDecoration: k === "x" ? "line-through" : "none",
                    opacity: k === "x" ? 0.7 : 1,
                  }}>{n}</span>
                ))}
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 10, fontSize: 10, color: T.ink3 }}>
                <span><Dot c={T.green} /> Grave 14</span>
                <span><Dot c={T.amber} /> PM OL 2</span>
                <span><Dot c={T.blue} /> AM OL 2</span>
                <span><Dot c={T.red} /> Off 2</span>
              </div>
            </Section>

            <Section title="Tonight" right={<a style={{ fontSize: 11, color: T.blue }}>All tasks →</a>}>
              {[
                {t:"Z9 SR — flag from last shift", c:"flag", o:true},
                {t:"BEO 4127 set in Pavilion by 03:00", c:"BEO", o:false},
                {t:"Restock EVS cart 2", c:"task", o:false},
                {t:"Walk south corridor 02:30", c:"walk", o:false},
              ].map((it,i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 0",
                  borderBottom: `1px solid ${T.line}`,
                }}>
                  <Dot c={it.o ? T.red : T.blue} size={8} />
                  <div style={{ flex: 1, fontSize: 12, color: T.ink }}>{it.t}</div>
                  <Pill color={it.o ? T.red : T.ink3} bg={it.o ? T.redDim : T.panel2} border={it.o ? T.red : T.line}>
                    {it.o ? "overdue" : it.c}
                  </Pill>
                  <button style={{
                    width: 22, height: 22, borderRadius: 999, border: `1px solid ${T.line2}`,
                    background: T.panel, color: T.ink3, fontSize: 11,
                  }}>✓</button>
                </div>
              ))}
            </Section>
          </div>

          {/* Col 3 — Capture + activity */}
          <div style={{ background: T.bg, padding: 20, overflow: "hidden", display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Capture */}
            <div style={{
              background: T.panel, border: `1px solid ${T.line2}`, borderRadius: 10,
              padding: "12px 14px",
            }}>
              <div style={{ fontSize: 11, color: T.ink3 }}>Capture · ⌘N</div>
              <div style={{ marginTop: 6, fontSize: 13, color: T.mute, fontStyle: "italic" }}>
                Joy nailed Z9 SR tonight…
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 10 }}>
                {[
                  ["⚑","Call-out", T.red],
                  ["⏰","Late", T.amber],
                  ["⊟","BEO", T.blue],
                  ["★","Kudos", T.gold],
                  ["⚠","Incident", T.red],
                ].map(([i,l,c]) => (
                  <button key={l} style={{
                    fontSize: 11, padding: "4px 9px", borderRadius: 999,
                    border: `1px solid ${c}`, color: c, background: "transparent",
                  }}>{i} {l}</button>
                ))}
              </div>
            </div>

            <Section title="Activity">
              {[
                ["11:42","Brian","Joy → Z9 SR"],
                ["11:38","Brian","Locked Z4 (Kim)"],
                ["11:21","System","Wave 1 complete"],
                ["11:08","Brian","Ramos call-off"],
                ["11:00","System","Shift opened"],
              ].map(([t,who,what],i) => (
                <div key={i} style={{
                  display: "flex", gap: 10, padding: "7px 0",
                  borderBottom: i < 4 ? `1px solid ${T.line}` : "none",
                  fontSize: 11,
                }}>
                  <span style={{ color: T.ink3, fontFamily: T.mono, width: 36 }}>{t}</span>
                  <span style={{ color: T.ink2 }}><strong style={{ color: T.ink }}>{who}</strong> {what}</span>
                </div>
              ))}
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Shift HUD — Variant C: Hero Deployment + Timeline Clock ───────────────
function ShiftHUD_C() {
  // Phase markers along the shift timeline
  const phases = [
    { label: "Open",    start: 0,   end: 8 },
    { label: "Wave 1",  start: 8,   end: 17 },
    { label: "Mid",     start: 17,  end: 38 },
    { label: "Wave 2",  start: 38,  end: 50 },
    { label: "Late",    start: 50,  end: 75 },
    { label: "Wave 3",  start: 75,  end: 88 },
    { label: "Close",   start: 88,  end: 100 },
  ];
  const NOW = 21; // ~01:42 of an 8-hour shift

  return (
    <div style={{
      width: 1180, height: 820, background: T.bg, color: T.ink, fontFamily: T.font,
      display: "grid", gridTemplateColumns: "60px 1fr", overflow: "hidden",
      position: "relative",
    }}>
      {/* Rail */}
      <div style={{
        background: T.panel, borderRight: `1px solid ${T.line}`,
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "16px 0", gap: 8,
      }}>
        <div style={{ width: 28, height: 28, borderRadius: 6, background: T.blue }} />
        <div style={{ height: 12 }} />
        {["⊙","▦","⌕","◍","☐","✦","♥"].map((g,i) => (
          <div key={i} style={{
            width: 36, height: 36, borderRadius: 8, display: "grid", placeItems: "center",
            color: i === 0 ? T.blue : T.ink3, background: i === 0 ? T.blueDim : "transparent",
            fontSize: 14,
          }}>{g}</div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header + horizontal shift timeline */}
        <div style={{
          padding: "14px 24px 0", borderBottom: `1px solid ${T.line}`, background: T.panel,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div>
              <Eyebrow>Wed · May 6 · Grave</Eyebrow>
              <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", marginTop: 2 }}>
                Good evening, Brian.
              </div>
            </div>
            <div style={{ flex: 1 }} />
            <Pill color={T.amber} bg={T.amberDim} border={T.amber}>⚑ 2 Inherited from Tue</Pill>
            <Pill color={T.gold} bg={T.goldDim} border={T.gold}>● Live · 01:42 in</Pill>
          </div>

          {/* Timeline */}
          <div style={{ paddingTop: 14, paddingBottom: 12 }}>
            <div style={{ position: "relative", height: 32 }}>
              {/* Track */}
              <div style={{
                position: "absolute", left: 0, right: 0, top: 12, height: 8,
                background: T.panel2, border: `1px solid ${T.line}`, borderRadius: 999,
                overflow: "hidden",
              }}>
                {/* Progress fill */}
                <div style={{
                  position: "absolute", left: 0, top: 0, bottom: 0, width: `${NOW}%`,
                  background: `linear-gradient(90deg, ${T.gold}, ${T.green})`,
                  opacity: 0.7,
                }} />
              </div>
              {/* Phase segments */}
              {phases.map((p,i) => {
                const isCurrent = NOW >= p.start && NOW < p.end;
                const isWave = p.label.startsWith("Wave");
                return (
                  <div key={i} style={{
                    position: "absolute", left: `${p.start}%`, width: `${p.end - p.start}%`,
                    top: 0, height: 32, borderLeft: i > 0 ? `1px solid ${T.line2}` : "none",
                    paddingLeft: 6, paddingTop: 0,
                  }}>
                    <div style={{
                      fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
                      color: isCurrent ? (isWave ? T.blue : T.gold) : isWave ? T.ink2 : T.ink3,
                      textTransform: "uppercase",
                    }}>
                      {p.label}
                    </div>
                  </div>
                );
              })}
              {/* NOW marker */}
              <div style={{
                position: "absolute", left: `${NOW}%`, top: -2, bottom: -2,
                width: 2, background: T.gold, transform: "translateX(-1px)",
              }} />
              <div style={{
                position: "absolute", left: `${NOW}%`, top: 26, transform: "translateX(-50%)",
                fontFamily: T.mono, fontSize: 10, color: T.gold, whiteSpace: "nowrap",
              }}>
                01:42 ▾
              </div>
            </div>
            {/* Tick row */}
            <div style={{
              display: "flex", justifyContent: "space-between", marginTop: 14,
              fontFamily: T.mono, fontSize: 10, color: T.ink3,
            }}>
              {["11P","12A","1A","2A","3A","4A","5A","6A","7A"].map(t => (
                <span key={t}>{t}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Body */}
        <div style={{
          flex: 1, display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 1,
          background: T.line, overflow: "hidden",
        }}>
          {/* HERO — Deployment */}
          <div style={{ background: T.bg, padding: "16px 20px", overflow: "auto" }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
              <div>
                <Eyebrow color={T.ink2}>Deployment</Eyebrow>
                <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 4 }}>
                  <div style={{ fontSize: 32, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>18<span style={{ color: T.ink3, fontSize: 18, fontWeight: 400 }}> / 22</span></div>
                  <Pill color={T.gold} bg={T.goldDim} border={T.gold}>82% set</Pill>
                  <span style={{ fontSize: 11, color: T.red }}><Dot c={T.red}/> 4 open</span>
                  <span style={{ fontSize: 11, color: T.amber }}><Dot c={T.amber}/> 2 warn</span>
                </div>
              </div>
              <a style={{ fontSize: 11, color: T.blue }}>Open in ZDS →</a>
            </div>
            <GoldRule />

            {/* Big zone grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
              {[
                {z:"Z1",n:"Marquez",s:"ok"},{z:"Z2",n:"Patel",s:"ok"},{z:"Z3",n:"—",s:"open"},
                {z:"Z4",n:"Kim",s:"lock"},{z:"Z5",n:"Joy",s:"warn"},
                {z:"Z6",n:"Reyes",s:"ok"},{z:"Z7",n:"—",s:"open"},{z:"Z8",n:"Nguyen",s:"ok"},
                {z:"Z9",n:"Tran",s:"lock"},{z:"Z10",n:"Foster",s:"ok"},
              ].map((c,i) => {
                const bd = c.s === "open" ? T.red : c.s === "warn" ? T.amber : c.s === "lock" ? T.gold : T.line2;
                const bg = c.s === "open" ? T.redDim : c.s === "warn" ? T.amberDim : T.panel2;
                return (
                  <div key={i} style={{
                    background: bg, border: `1px solid ${bd}`, borderRadius: 8,
                    padding: "12px 12px", minHeight: 72, position: "relative",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ fontSize: 10, color: T.ink3, letterSpacing: "0.08em" }}>{c.z}</div>
                      {c.s === "lock" && <span style={{ fontSize: 10, color: T.gold }}>⌶</span>}
                      {c.s === "warn" && <span style={{ fontSize: 10, color: T.amber }}>⚠</span>}
                      {c.s === "open" && <span style={{ fontSize: 10, color: T.red, fontWeight: 700 }}>OPEN</span>}
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, marginTop: 6, color: c.n === "—" ? T.mute : T.ink }}>
                      {c.n}
                    </div>
                    <div style={{ fontSize: 10, color: T.ink3, marginTop: 2 }}>
                      W{(i % 3) + 1} · {["01:00","02:30","04:00"][i%3]}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* RR row */}
            <div style={{ marginTop: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <Eyebrow>Restrooms · 4 / 5</Eyebrow>
                <span style={{ fontSize: 10, color: T.red }}>RR3 open</span>
              </div>
              <GoldRule />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6 }}>
                {[["RR1","Lopez","ok"],["RR2","Brooks","ok"],["RR3","—","open"],["RR4","Diaz","ok"],["RR5","Singh","ok"]].map(([r,n,s]) => {
                  const bd = s === "open" ? T.red : T.line2;
                  const bg = s === "open" ? T.redDim : T.panel2;
                  return (
                    <div key={r} style={{
                      background: bg, border: `1px solid ${bd}`, borderRadius: 6,
                      padding: "8px 10px", fontSize: 12,
                    }}>
                      <div style={{ fontSize: 9, color: T.ink3 }}>{r}</div>
                      <div style={{ color: n === "—" ? T.mute : T.ink, fontWeight: 600 }}>{n}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Aux row */}
            <div style={{ marginTop: 12 }}>
              <Eyebrow>Auxiliary</Eyebrow>
              <GoldRule />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4 }}>
                {[["Lobby","Cole"],["Valet","Park"],["BOH","—"],["Cage","Lopez"],["Buf","—"],["Dock","Brooks"],["Float","—"]].map(([a,n]) => (
                  <div key={a} style={{
                    background: T.panel2, border: `1px solid ${T.line}`, borderRadius: 4,
                    padding: "5px 6px", fontSize: 10, textAlign: "center",
                  }}>
                    <div style={{ color: T.ink3, fontSize: 9 }}>{a}</div>
                    <div style={{ color: n === "—" ? T.mute : T.ink2 }}>{n}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Wave strip */}
            <div style={{ marginTop: 14 }}>
              <Eyebrow>Break waves · W2 active</Eyebrow>
              <GoldRule />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {[
                  {n:1,t:"01:00–01:30",s:"done", c:T.green},
                  {n:2,t:"02:30–03:00",s:"active",c:T.blue},
                  {n:3,t:"04:00–04:30",s:"queue", c:T.ink3},
                ].map(w => (
                  <div key={w.n} style={{
                    border: `1px solid ${w.c}`, borderRadius: 6, padding: "6px 10px",
                    background: w.s === "active" ? T.blueDim : "transparent",
                    display: "flex", alignItems: "center", gap: 8,
                  }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: w.c }}>W{w.n}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontFamily: T.mono, fontSize: 10, color: T.ink2 }}>{w.t}</div>
                      <div style={{ fontSize: 9, color: w.c, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                        {w.s}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT — Roster + Tasks + Activity */}
          <div style={{ background: T.bg, padding: "16px 20px", overflow: "auto",
                        display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <Eyebrow color={T.ink2}>Roster · 14 on floor</Eyebrow>
                <span style={{ fontSize: 10, color: T.red }}>2 off</span>
              </div>
              <GoldRule />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {[
                  ["Marquez","g"],["Patel","g"],["Kim","g"],["Joy","g"],["Reyes","g"],
                  ["Nguyen","g"],["Tran","g"],["Foster","g"],["Lopez","g"],["Brooks","g"],
                  ["Diaz","p"],["Singh","p"],["Cole","a"],["Park","a"],
                  ["Ortega","x"],["Ramos","x"],
                ].map(([n,k]) => (
                  <span key={n} style={{
                    fontSize: 11, padding: "3px 7px", borderRadius: 999,
                    background: k === "x" ? T.redDim : k === "a" ? "rgba(30,58,138,0.3)" : k === "p" ? T.amberDim : T.greenDim,
                    color: k === "x" ? T.red : k === "a" ? T.blue : k === "p" ? T.amber : T.green,
                    border: `1px solid ${k === "x" ? T.red : k === "a" ? T.blue : k === "p" ? T.amber : T.green}`,
                    textDecoration: k === "x" ? "line-through" : "none",
                    opacity: k === "x" ? 0.7 : 1,
                  }}>{n}</span>
                ))}
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 8, fontSize: 10, color: T.ink3 }}>
                <span><Dot c={T.green}/> 10 grave</span>
                <span><Dot c={T.amber}/> 2 PM OL</span>
                <span><Dot c={T.blue}/> 2 AM OL</span>
              </div>
            </div>

            {/* Inherited flags */}
            <div>
              <Eyebrow color={T.amber}>⚑ Inherited from Tuesday</Eyebrow>
              <GoldRule />
              {[
                "Z9 SR — repeat issue, walk early",
                "BEO 4127 still open from Mon",
              ].map((t,i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "6px 0",
                  borderBottom: i === 0 ? `1px solid ${T.line}` : "none",
                  fontSize: 12,
                }}>
                  <Dot c={T.amber} size={6} />
                  <span style={{ flex: 1, color: T.ink2 }}>{t}</span>
                </div>
              ))}
            </div>

            {/* Tonight tasks */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <Eyebrow>Tonight · 7 open</Eyebrow>
                <a style={{ fontSize: 11, color: T.blue }}>All →</a>
              </div>
              <GoldRule />
              {[
                {t:"BEO 4127 set in Pavilion by 03:00", o:false},
                {t:"Restock EVS cart 2", o:false},
                {t:"Walk south corridor 02:30", o:false},
                {t:"PM walk debrief w/ Diaz", o:false},
              ].map((it,i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "6px 0",
                  borderBottom: i < 3 ? `1px solid ${T.line}` : "none", fontSize: 12,
                }}>
                  <Dot c={T.blue} size={6} />
                  <span style={{ flex: 1, color: T.ink }}>{it.t}</span>
                  <span style={{
                    width: 18, height: 18, borderRadius: 999, border: `1px solid ${T.line2}`,
                    display: "grid", placeItems: "center", fontSize: 10, color: T.ink3,
                  }}>✓</span>
                </div>
              ))}
            </div>

            {/* Activity (compact) */}
            <div>
              <Eyebrow>Activity</Eyebrow>
              <GoldRule />
              {[["01:42","Joy → Z9 SR"],["01:38","Locked Z4"],["01:21","W1 complete"],["01:08","Ramos call-off"]].map(([t,w],i) => (
                <div key={i} style={{ display: "flex", gap: 10, padding: "4px 0", fontSize: 11 }}>
                  <span style={{ color: T.ink3, fontFamily: T.mono, width: 38 }}>{t}</span>
                  <span style={{ color: T.ink2 }}>{w}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Thumb cluster — bottom right */}
      <div style={{
        position: "absolute", bottom: 20, right: 20,
        display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10,
      }}>
        {[
          {i:"⚑", l:"Call-out", c:T.red},
          {i:"★", l:"Kudos",    c:T.gold},
          {i:"⊟", l:"BEO",      c:T.blue},
        ].map(b => (
          <button key={b.l} style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "8px 14px 8px 12px", borderRadius: 999,
            background: T.panel, border: `1px solid ${b.c}`, color: b.c,
            fontSize: 12, fontWeight: 600,
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
          }}>
            <span style={{ fontSize: 14 }}>{b.i}</span>{b.l}
          </button>
        ))}
        <button style={{
          width: 60, height: 60, borderRadius: 999,
          background: T.blue, color: "#0a1726", fontSize: 28, fontWeight: 300,
          boxShadow: `0 8px 24px rgba(92,192,255,0.4)`, border: "none",
        }}>+</button>
      </div>
    </div>
  );
}

// ── Shift HUD — Variant B: Vertical Strips ────────────────────────────────
function ShiftHUD_B() {
  return (
    <div style={{
      width: 1180, height: 820, background: T.bg, color: T.ink, fontFamily: T.font,
      display: "grid", gridTemplateColumns: "60px 320px 1fr 320px", overflow: "hidden",
    }}>
      {/* Rail */}
      <div style={{
        background: T.panel, borderRight: `1px solid ${T.line}`,
        display: "flex", flexDirection: "column", alignItems: "center", padding: "16px 0", gap: 8,
      }}>
        <div style={{ width: 28, height: 28, borderRadius: 6, background: T.blue }} />
        <div style={{ height: 12 }} />
        {["◎","⊙","▦","⌕","◍","☐"].map((g,i) => (
          <div key={i} style={{
            width: 36, height: 36, borderRadius: 8, display: "grid", placeItems: "center",
            color: i === 1 ? T.blue : T.ink3, background: i === 1 ? T.blueDim : "transparent",
          }}>{g}</div>
        ))}
      </div>

      {/* Left strip — Roster */}
      <div style={{
        background: T.panel, borderRight: `1px solid ${T.line}`,
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.line}` }}>
          <Eyebrow>Roster · 14 on floor</Eyebrow>
          <GoldRule />
          <div style={{ fontSize: 18, fontWeight: 600 }}>Wed · May 6</div>
          <div style={{ fontSize: 11, color: T.ink3 }}>11PM – 7AM · Grave</div>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: "12px 16px" }}>
          {/* Pool sections */}
          {[
            {label:"GRAVE", time:"11P–7A", c:T.green, names:["Marquez","Patel","Kim","Joy","Reyes","Nguyen","Tran","Foster","Lopez","Brooks"]},
            {label:"PM OL", time:"11P–1A", c:T.amber, names:["Diaz","Singh"]},
            {label:"AM OL", time:"5A–7A",  c:T.blue,  names:["Cole","Park"]},
            {label:"OFF",   time:"called", c:T.red,   names:["Ortega","Ramos"]},
          ].map(p => (
            <div key={p.label} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <Eyebrow color={p.c}>{p.label}</Eyebrow>
                <span style={{ fontSize: 10, color: T.ink3 }}>{p.time}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 6 }}>
                {p.names.map(n => (
                  <div key={n} style={{
                    display: "flex", alignItems: "center", gap: 8, padding: "5px 8px",
                    borderRadius: 4, background: p.label === "OFF" ? T.redDim : T.panel2,
                    fontSize: 12,
                    textDecoration: p.label === "OFF" ? "line-through" : "none",
                    color: p.label === "OFF" ? T.ink3 : T.ink,
                  }}>
                    <Dot c={p.c} />
                    <span style={{ flex: 1 }}>{n}</span>
                    {p.label !== "OFF" && (
                      <span style={{ fontSize: 9, color: T.ink3, fontFamily: T.mono }}>
                        {["Z1","Z2","Z4","Z5","Z6","Z8","Z9","Z10","RR1","RR2","RR4","RR5","Lobby","BOH"][["Marquez","Patel","Kim","Joy","Reyes","Nguyen","Tran","Foster","Lopez","Brooks","Diaz","Singh","Cole","Park"].indexOf(n)] || "—"}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Center — Stage */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header bar */}
        <div style={{
          padding: "14px 24px", borderBottom: `1px solid ${T.line}`,
          background: `linear-gradient(180deg, ${T.panel} 0%, ${T.bg} 100%)`,
          display: "flex", alignItems: "center", gap: 16,
        }}>
          <div>
            <Eyebrow color={T.gold}>Grave Shift · Active</Eyebrow>
            <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.01em" }}>
              Good evening, Brian.
            </div>
            <div style={{ fontSize: 12, color: T.ink3, marginTop: 2 }}>
              82% deployed · wave 2 in 18m · 2 called off
            </div>
          </div>
          <div style={{ flex: 1 }} />
          {/* Big shift clock */}
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: T.mono, fontSize: 24, color: T.gold, letterSpacing: "0.02em" }}>
              06:18:23
            </div>
            <div style={{ fontSize: 10, color: T.ink3, letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Time remaining
            </div>
          </div>
        </div>

        {/* Wave progress strip */}
        <div style={{ padding: "14px 24px", borderBottom: `1px solid ${T.line}` }}>
          <Eyebrow color={T.ink2}>Break waves</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 10 }}>
            {[
              {n:1, t:"01:00 – 01:30", state:"done",   filled: "5/5"},
              {n:2, t:"02:30 – 03:00", state:"active", filled: "3/9"},
              {n:3, t:"04:00 – 04:30", state:"queue",  filled: "0/4"},
            ].map(w => {
              const c = w.state === "done" ? T.green : w.state === "active" ? T.blue : T.ink3;
              const bg = w.state === "active" ? T.blueDim : "transparent";
              return (
                <div key={w.n} style={{
                  border: `1px solid ${c}`, borderRadius: 8, padding: "10px 14px",
                  background: bg,
                }}>
                  <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: c }}>W{w.n}</div>
                    <div style={{ fontSize: 11, color: T.ink3 }}>{w.filled} on break</div>
                  </div>
                  <div style={{ fontFamily: T.mono, fontSize: 11, color: T.ink2, marginTop: 4 }}>{w.t}</div>
                  <div style={{ fontSize: 10, color: c, marginTop: 4, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                    {w.state}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Deployment block */}
        <div style={{ flex: 1, padding: "16px 24px", overflow: "auto" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <Eyebrow color={T.ink2}>Deployment · 18 / 22</Eyebrow>
            <a style={{ fontSize: 11, color: T.blue }}>Open in ZDS →</a>
          </div>
          <GoldRule />
          {/* Fill bar */}
          <div style={{ height: 6, background: T.panel2, borderRadius: 999, overflow: "hidden", marginBottom: 12 }}>
            <div style={{ width: "82%", height: "100%", background: `linear-gradient(90deg, ${T.gold}, ${T.green})` }} />
          </div>
          {/* Zones */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6, marginBottom: 10 }}>
            {[
              ["Z1","Marquez","ok"],["Z2","Patel","ok"],["Z3","—","open"],["Z4","Kim","lock"],["Z5","Joy","warn"],
              ["Z6","Reyes","ok"],["Z7","—","open"],["Z8","Nguyen","ok"],["Z9","Tran","lock"],["Z10","Foster","ok"],
            ].map(([z,n,s]) => {
              const bd = s === "open" ? T.red : s === "warn" ? T.amber : s === "lock" ? T.gold : T.line2;
              const bg = s === "open" ? T.redDim : s === "warn" ? T.amberDim : T.panel2;
              return (
                <div key={z} style={{
                  background: bg, border: `1px solid ${bd}`, borderRadius: 6, padding: "10px 12px",
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ fontSize: 10, color: T.ink3, letterSpacing: "0.08em" }}>{z}</div>
                    {s === "lock" && <span style={{ fontSize: 10, color: T.gold }}>⌶</span>}
                    {s === "open" && <Dot c={T.red} />}
                    {s === "warn" && <span style={{ fontSize: 10, color: T.amber }}>⚠</span>}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4, color: n === "—" ? T.mute : T.ink }}>
                    {n}
                  </div>
                </div>
              );
            })}
          </div>
          {/* RR / Aux compact */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 10 }}>
            <div>
              <Eyebrow style={{ marginBottom: 6 }}>Restrooms</Eyebrow>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4 }}>
                {[["RR1","Lopez"],["RR2","Brooks"],["RR3","—"],["RR4","Diaz"],["RR5","Singh"]].map(([r,n]) => (
                  <div key={r} style={{
                    background: T.panel2, border: `1px solid ${T.line}`, borderRadius: 4,
                    padding: "5px 6px", fontSize: 10, color: n === "—" ? T.mute : T.ink2, textAlign: "center",
                  }}>
                    <div style={{ fontSize: 9, color: T.ink3 }}>{r}</div>
                    <div>{n}</div>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <Eyebrow style={{ marginBottom: 6 }}>Auxiliary</Eyebrow>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 3 }}>
                {["Lobby","Valet","BOH","Cage","Buf","Dock","Float"].map(a => (
                  <div key={a} style={{
                    background: T.panel2, border: `1px solid ${T.line}`, borderRadius: 3,
                    padding: "4px 2px", fontSize: 9, textAlign: "center", color: T.ink2,
                  }}>{a}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right strip — Tasks + capture */}
      <div style={{
        background: T.panel, borderLeft: `1px solid ${T.line}`,
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.line}` }}>
          <Eyebrow>Capture</Eyebrow>
          <GoldRule />
          <div style={{
            border: `1px dashed ${T.line2}`, borderRadius: 8, padding: "10px 12px",
            color: T.mute, fontSize: 13, fontStyle: "italic",
          }}>
            Capture a note — Joy nailed Z9 SR tonight…
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
            {[["⚑","Call-out"],["⏰","Late"],["⊟","BEO"],["★","Kudos"]].map(([i,l]) => (
              <button key={l} style={{
                fontSize: 10, padding: "4px 9px", borderRadius: 999,
                border: `1px solid ${T.line2}`, color: T.ink2, background: T.bg,
              }}>{i} {l}</button>
            ))}
          </div>
        </div>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${T.line}`, flex: 1, overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <Eyebrow>Tonight</Eyebrow>
            <a style={{ fontSize: 11, color: T.blue }}>All →</a>
          </div>
          <GoldRule />
          {[
            {t:"Z9 SR — flag from last shift", o:true},
            {t:"BEO 4127 Pavilion by 03:00", o:false},
            {t:"Restock EVS cart 2", o:false},
            {t:"Walk south corridor 02:30", o:false},
            {t:"PM walk debrief w/ Diaz", o:false},
          ].map((it,i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 8, padding: "8px 0",
              borderBottom: `1px solid ${T.line}`,
            }}>
              <Dot c={it.o ? T.red : T.blue} size={6} />
              <span style={{ flex: 1, fontSize: 12, color: T.ink }}>{it.t}</span>
              <span style={{
                width: 18, height: 18, borderRadius: 999, border: `1px solid ${T.line2}`,
                display: "grid", placeItems: "center", fontSize: 10, color: T.ink3,
              }}>✓</span>
            </div>
          ))}
        </div>
        <div style={{ padding: "14px 20px" }}>
          <Eyebrow>Activity</Eyebrow>
          <GoldRule />
          {[
            ["11:42","Joy → Z9 SR"],
            ["11:38","Locked Z4"],
            ["11:21","Wave 1 complete"],
            ["11:08","Ramos call-off"],
          ].map(([t,w],i) => (
            <div key={i} style={{ display: "flex", gap: 10, padding: "5px 0", fontSize: 11 }}>
              <span style={{ color: T.ink3, fontFamily: T.mono, width: 36 }}>{t}</span>
              <span style={{ color: T.ink2 }}>{w}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Home / Launchpad ──────────────────────────────────────────────────────
function HomeLaunchpad() {
  return (
    <div style={{
      width: 1180, height: 820, background: T.bg, color: T.ink, fontFamily: T.font,
      display: "flex", flexDirection: "column", overflow: "hidden",
      backgroundImage: `radial-gradient(circle at 20% 0%, rgba(224,203,182,0.06), transparent 50%),
                        radial-gradient(circle at 100% 100%, rgba(92,192,255,0.05), transparent 60%)`,
    }}>
      {/* Top bar */}
      <div style={{
        display: "flex", alignItems: "center", padding: "20px 32px",
        borderBottom: `1px solid ${T.line}`,
      }}>
        <div style={{ width: 28, height: 28, borderRadius: 6, background: T.blue }} />
        <div style={{ marginLeft: 12, fontSize: 14, fontWeight: 600 }}>Graves Ops</div>
        <div style={{ flex: 1 }} />
        <Pill color={T.ink3} bg={T.panel2} border={T.line}>
          <Dot c={T.green} /> Backend OK · 24ms
        </Pill>
        <span style={{ marginLeft: 12, fontSize: 12, color: T.ink3 }}>brian@glcr.ops · Editor</span>
      </div>

      {/* Hero */}
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", justifyContent: "center",
        padding: "0 80px",
      }}>
        <Eyebrow color={T.gold}>Wed · May 6 · 11:42 PM</Eyebrow>
        <div style={{
          fontFamily: T.serif, fontSize: 52, fontWeight: 400,
          letterSpacing: "-0.02em", color: T.ink, marginTop: 8, fontStyle: "italic",
        }}>
          Pick a surface to enter.
        </div>
        <div style={{ fontSize: 14, color: T.ink3, marginTop: 12, maxWidth: 520 }}>
          Grave shift starts in 18 minutes. 14 on the floor tonight, 2 called off.
          The deployment book is published.
        </div>

        {/* 3 cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginTop: 40 }}>
          {[
            {
              n: "Memory", g: "◎", c: T.gold, tag: "Search · people · threads · patterns",
              meta: "12 captures today",
            },
            {
              n: "Shift", g: "⊙", c: T.blue, tag: "Tonight's command center",
              meta: "82% deployed · 7 open tasks", featured: true,
            },
            {
              n: "ZDS", g: "▦", c: T.green, tag: "Zone Deployment · weekly schedules",
              meta: "Week of May 7 · published",
            },
          ].map(card => (
            <div key={card.n} style={{
              background: card.featured ? T.panel : T.panel2,
              border: `1px solid ${card.featured ? card.c : T.line}`,
              borderRadius: 14, padding: 24, position: "relative",
              boxShadow: card.featured ? `0 0 0 3px ${T.blueDim}` : "none",
            }}>
              {card.featured && (
                <div style={{
                  position: "absolute", top: 12, right: 12,
                  fontSize: 9, color: T.blue, letterSpacing: "0.1em", fontWeight: 700,
                }}>
                  ● LIVE
                </div>
              )}
              <div style={{
                width: 44, height: 44, borderRadius: 10, background: T.bg,
                border: `1px solid ${card.c}`, display: "grid", placeItems: "center",
                color: card.c, fontSize: 20, marginBottom: 16,
              }}>{card.g}</div>
              <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>{card.n}</div>
              <div style={{ fontSize: 12, color: T.ink3, marginTop: 4, lineHeight: 1.5 }}>{card.tag}</div>
              <div style={{
                marginTop: 20, paddingTop: 12, borderTop: `1px solid ${T.line}`,
                fontSize: 11, color: card.c, fontWeight: 600, letterSpacing: "0.04em",
              }}>
                {card.meta}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        padding: "16px 32px", borderTop: `1px solid ${T.line}`,
        display: "flex", justifyContent: "space-between",
        fontSize: 11, color: T.ink3, letterSpacing: "0.06em",
      }}>
        <span>GLCR OPS · INTERNAL · GRAVE SHIFT</span>
        <span style={{ fontFamily: T.mono }}>v0.9 · main</span>
      </div>
    </div>
  );
}

// ── Unlock / PIN gate ─────────────────────────────────────────────────────
function UnlockPIN() {
  const [pin, setPin] = useState("••••");
  return (
    <div style={{
      width: 1180, height: 820, background: T.bg, color: T.ink, fontFamily: T.font,
      display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden",
    }}>
      {/* Left — brand panel */}
      <div style={{
        background: `linear-gradient(165deg, ${T.panel} 0%, ${T.bg} 100%)`,
        borderRight: `1px solid ${T.line}`,
        padding: "60px 64px", display: "flex", flexDirection: "column", justifyContent: "space-between",
        position: "relative", overflow: "hidden",
      }}>
        {/* gold accent */}
        <div style={{
          position: "absolute", top: 0, left: 0, width: 4, height: "60%",
          background: `linear-gradient(180deg, ${T.gold}, transparent)`,
        }} />
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 8, background: T.blue }} />
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Graves Ops</div>
              <div style={{ fontSize: 10, color: T.ink3, letterSpacing: "0.12em", textTransform: "uppercase" }}>
                Gun Lake · Internal
              </div>
            </div>
          </div>
        </div>

        <div>
          <Eyebrow color={T.gold}>Wednesday · May 6 · 2026</Eyebrow>
          <div style={{
            fontFamily: T.serif, fontSize: 54, fontWeight: 400, fontStyle: "italic",
            letterSpacing: "-0.02em", lineHeight: 1.05, marginTop: 12,
          }}>
            Eleven<br />forty-two PM.
          </div>
          <div style={{ fontSize: 14, color: T.ink2, marginTop: 16, maxWidth: 380, lineHeight: 1.6 }}>
            Grave shift opens in 18 minutes. Tonight: 14 on the floor,
            2 called off, deployment 82% set.
          </div>
        </div>

        <div style={{ display: "flex", gap: 24, fontSize: 11, color: T.ink3 }}>
          <div>
            <div style={{ fontFamily: T.mono, fontSize: 18, color: T.ink, fontVariantNumeric: "tabular-nums" }}>
              14
            </div>
            <div style={{ letterSpacing: "0.08em", textTransform: "uppercase" }}>On floor</div>
          </div>
          <div style={{ width: 1, background: T.line }} />
          <div>
            <div style={{ fontFamily: T.mono, fontSize: 18, color: T.ink, fontVariantNumeric: "tabular-nums" }}>
              82%
            </div>
            <div style={{ letterSpacing: "0.08em", textTransform: "uppercase" }}>Deployed</div>
          </div>
          <div style={{ width: 1, background: T.line }} />
          <div>
            <div style={{ fontFamily: T.mono, fontSize: 18, color: T.amber, fontVariantNumeric: "tabular-nums" }}>
              2
            </div>
            <div style={{ letterSpacing: "0.08em", textTransform: "uppercase" }}>Called off</div>
          </div>
        </div>
      </div>

      {/* Right — PIN entry */}
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        padding: 60, gap: 28,
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 64, height: 64, borderRadius: 999, border: `1px solid ${T.gold}`,
            display: "grid", placeItems: "center", margin: "0 auto 20px",
            background: T.goldDim, color: T.gold, fontSize: 24,
          }}>⌶</div>
          <Eyebrow color={T.gold}>Locked</Eyebrow>
          <div style={{ fontSize: 26, fontWeight: 600, marginTop: 6, letterSpacing: "-0.01em" }}>
            Enter PIN
          </div>
          <div style={{ fontSize: 13, color: T.ink3, marginTop: 6 }}>
            Tap to unlock viewer mode · Editor sign-in below
          </div>
        </div>

        {/* PIN dots */}
        <div style={{ display: "flex", gap: 14 }}>
          {[0,1,2,3].map(i => (
            <div key={i} style={{
              width: 18, height: 18, borderRadius: 999,
              border: `1.5px solid ${i < 3 ? T.gold : T.line2}`,
              background: i < 3 ? T.gold : "transparent",
            }} />
          ))}
        </div>

        {/* Keypad */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(3, 72px)", gap: 12,
        }}>
          {[1,2,3,4,5,6,7,8,9,"clear",0,"⌫"].map(k => (
            <button key={k} style={{
              width: 72, height: 72, borderRadius: 14,
              background: T.panel, border: `1px solid ${T.line2}`,
              fontSize: typeof k === "number" ? 24 : 11,
              fontWeight: typeof k === "number" ? 500 : 600,
              color: typeof k === "number" ? T.ink : T.ink3,
              letterSpacing: typeof k === "number" ? "0" : "0.06em",
              textTransform: typeof k === "string" ? "uppercase" : "none",
            }}>{k}</button>
          ))}
        </div>

        {/* Footer */}
        <div style={{
          marginTop: 8, paddingTop: 20, borderTop: `1px solid ${T.line}`,
          width: 280, textAlign: "center",
        }}>
          <a style={{ color: T.blue, fontSize: 12 }}>✎ Sign in as editor →</a>
        </div>
      </div>
    </div>
  );
}

// ── Mount via Design Canvas ───────────────────────────────────────────────
function App() {
  return (
    <DesignCanvas storageKey="gshift-wireframes-v2">
      <DCSection id="shift-hifi" title="Shift Page · hi-fi (going deeper on C)">
        <DCArtboard id="shift-hifi-1" label="Hi-fi v1 — Hero Deployment + Plotted Timeline" width={1180} height={820}>
          <ShiftHUD_HiFi />
        </DCArtboard>
      </DCSection>
      <DCSection id="entry" title="Entry surface">
        <DCArtboard id="unlock" label="Unlock / PIN gate · /unlock" width={1180} height={820}>
          <UnlockPIN />
        </DCArtboard>
      </DCSection>
      <DCSection id="archive" title="Earlier wireframe explorations">
        <DCArtboard id="shift-c" label="Variant C — wireframe (source for hi-fi)" width={1180} height={820}>
          <ShiftHUD_C />
        </DCArtboard>
        <DCArtboard id="shift-a" label="Variant A — Command Grid" width={1180} height={820}>
          <ShiftHUD_A />
        </DCArtboard>
        <DCArtboard id="shift-b" label="Variant B — Vertical Strips" width={1180} height={820}>
          <ShiftHUD_B />
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
