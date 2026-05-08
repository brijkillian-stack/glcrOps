/* GLCR Shift HUD — Hi-fi v1 (built from Variant C direction)
 * - Timeline clock with plotted events
 * - Deployment as hero with full data density
 * - Read-only HUD; capture lives in thumb cluster (FAB)
 * - Subtle phase awareness via timeline highlight
 */

const T2 = {
  bg:      "#0B0C0E",
  panel:   "#131518",
  panel2:  "#191B1F",
  panel3:  "#202327",
  line:    "#26292E",
  line2:   "#33373D",
  ink:     "#F5F2E9",
  ink2:    "#BFBBAE",
  ink3:    "#82807A",
  mute:    "#4A4944",
  blue:    "#5CC0FF",
  blueDim: "rgba(92,192,255,0.12)",
  blueDk:  "rgba(92,192,255,0.04)",
  gold:    "#E0CBB6",
  goldDim: "rgba(224,203,182,0.10)",
  green:   "#5BD68B",
  greenDim:"rgba(91,214,139,0.10)",
  red:     "#F47373",
  redDim:  "rgba(244,115,115,0.12)",
  amber:   "#F2B23A",
  amberDim:"rgba(242,178,58,0.12)",
  font:    "'Barlow', system-ui, sans-serif",
  serif:   "'PT Serif', Georgia, serif",
  mono:    "ui-monospace, 'SF Mono', Menlo, monospace",
};

const Eb = ({ children, c = T2.ink3, style }) => (
  <div style={{
    fontSize: 10, fontWeight: 700, letterSpacing: "0.14em",
    textTransform: "uppercase", color: c, ...style,
  }}>{children}</div>
);

const Pill2 = ({ children, color = T2.ink2, bg = T2.panel2, border = T2.line, style }) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: 5,
    fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
    padding: "3px 9px", borderRadius: 999, color, background: bg,
    border: `1px solid ${border}`, lineHeight: 1.4, ...style,
  }}>{children}</span>
);

const Dot2 = ({ c = T2.ink3, size = 6, style }) => (
  <span style={{
    display: "inline-block", width: size, height: size, borderRadius: 999,
    background: c, ...style,
  }} />
);

const SectionHead = ({ title, count, action, accent = T2.gold }) => (
  <div style={{ marginBottom: 10 }}>
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <Eb c={T2.ink2}>{title}</Eb>
        {count != null && (
          <span style={{ fontSize: 11, color: T2.ink3, fontFamily: T2.mono }}>{count}</span>
        )}
      </div>
      {action}
    </div>
    <div style={{ height: 2, width: 22, background: accent, marginTop: 5 }} />
  </div>
);

// ── ZONE CARD ─────────────────────────────────────────────────────────────
function ZoneCard({ z, name, status, wave, time, position }) {
  const palette = {
    ok:   { bd: T2.line2, bg: T2.panel2, accent: T2.ink3 },
    lock: { bd: T2.gold,  bg: T2.goldDim, accent: T2.gold },
    warn: { bd: T2.amber, bg: T2.amberDim, accent: T2.amber },
    open: { bd: T2.red,   bg: T2.redDim, accent: T2.red },
  }[status];

  return (
    <div style={{
      background: palette.bg, border: `1px solid ${palette.bd}`, borderRadius: 8,
      padding: "10px 12px", minHeight: 84, display: "flex", flexDirection: "column",
      position: "relative",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 10, color: T2.ink3, letterSpacing: "0.1em", fontWeight: 600 }}>
          {z}
        </div>
        {status === "lock" && <span style={{ fontSize: 10, color: palette.accent }}>⌶ LOCK</span>}
        {status === "warn" && <span style={{ fontSize: 9, color: palette.accent, letterSpacing: "0.06em", fontWeight: 700 }}>⚠ WARN</span>}
        {status === "open" && <span style={{ fontSize: 9, color: palette.accent, letterSpacing: "0.06em", fontWeight: 700 }}>● OPEN</span>}
      </div>
      <div style={{
        fontSize: 14, fontWeight: 600, marginTop: 4, letterSpacing: "-0.005em",
        color: name === "—" ? T2.mute : T2.ink,
      }}>
        {name}
      </div>
      <div style={{ fontSize: 11, color: T2.ink3, marginTop: 1 }}>{position}</div>
      <div style={{ flex: 1 }} />
      <div style={{
        marginTop: 6, paddingTop: 6, borderTop: `1px solid ${T2.line}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        fontSize: 10, color: T2.ink3,
      }}>
        <span>W{wave}</span>
        <span style={{ fontFamily: T2.mono }}>{time}</span>
      </div>
    </div>
  );
}

// ── TIMELINE ──────────────────────────────────────────────────────────────
function ShiftTimeline() {
  const NOW = 21;
  const phases = [
    { label: "Open",    start: 0,   end: 8,   wave: false },
    { label: "Wave 1",  start: 8,   end: 17,  wave: true },
    { label: "Mid",     start: 17,  end: 38,  wave: false },
    { label: "Wave 2",  start: 38,  end: 50,  wave: true },
    { label: "Late",    start: 50,  end: 75,  wave: false },
    { label: "Wave 3",  start: 75,  end: 88,  wave: true },
    { label: "Close",   start: 88,  end: 100, wave: false },
  ];
  const events = [
    { at: 4,  c: T2.amber, label: "Ramos call-off",  side: "below" },
    { at: 13, c: T2.green, label: "W1 done",         side: "above" },
    { at: 18, c: T2.gold,  label: "Joy → Z9 SR",     side: "above" },
    { at: 20, c: T2.gold,  label: "Locked Z4",       side: "below" },
  ];

  return (
    <div style={{ paddingTop: 16, paddingBottom: 14 }}>
      <div style={{ position: "relative", height: 60 }}>
        {/* Above-line event flags */}
        {events.filter(e => e.side === "above").map((e, i) => (
          <div key={i} style={{
            position: "absolute", left: `${e.at}%`, top: 0, transform: "translateX(-50%)",
            display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
          }}>
            <div style={{
              fontSize: 9, color: e.c, letterSpacing: "0.04em", fontWeight: 600,
              whiteSpace: "nowrap", padding: "1px 6px", border: `1px solid ${e.c}`,
              borderRadius: 3, background: T2.bg,
            }}>{e.label}</div>
            <div style={{ width: 1, height: 6, background: e.c }} />
          </div>
        ))}
        {/* Track */}
        <div style={{
          position: "absolute", left: 0, right: 0, top: 28, height: 8,
          background: T2.panel2, border: `1px solid ${T2.line}`, borderRadius: 999,
          overflow: "hidden",
        }}>
          {/* Phase blocks (flat) */}
          {phases.map((p, i) => p.wave && (
            <div key={i} style={{
              position: "absolute", left: `${p.start}%`, width: `${p.end - p.start}%`,
              top: 0, bottom: 0, background: T2.blueDim,
            }} />
          ))}
          {/* Progress fill */}
          <div style={{
            position: "absolute", left: 0, top: 0, bottom: 0, width: `${NOW}%`,
            background: `linear-gradient(90deg, rgba(224,203,182,0.6), ${T2.gold})`,
          }} />
        </div>

        {/* Phase labels above */}
        <div style={{ position: "absolute", left: 0, right: 0, top: 16, height: 10 }}>
          {phases.map((p, i) => {
            const isCurrent = NOW >= p.start && NOW < p.end;
            return (
              <div key={i} style={{
                position: "absolute", left: `${p.start}%`, width: `${p.end - p.start}%`,
                top: 0, paddingLeft: 4,
                fontSize: 8, fontWeight: 700, letterSpacing: "0.1em",
                color: isCurrent ? T2.gold : p.wave ? T2.blue : T2.ink3,
                textTransform: "uppercase", borderLeft: i > 0 ? `1px solid ${T2.line2}` : "none",
              }}>
                {p.label}
              </div>
            );
          })}
        </div>

        {/* NOW marker */}
        <div style={{
          position: "absolute", left: `${NOW}%`, top: 12, bottom: 0,
          width: 2, background: T2.gold, transform: "translateX(-1px)",
          boxShadow: `0 0 12px ${T2.gold}`,
        }} />
        <div style={{
          position: "absolute", left: `${NOW}%`, top: 8,
          transform: "translateX(-50%)",
          fontFamily: T2.mono, fontSize: 9, color: T2.gold,
          background: T2.bg, padding: "1px 5px", border: `1px solid ${T2.gold}`,
          borderRadius: 3, fontWeight: 600,
        }}>
          NOW · 01:42
        </div>

        {/* Below-line event flags */}
        {events.filter(e => e.side === "below").map((e, i) => (
          <div key={i} style={{
            position: "absolute", left: `${e.at}%`, top: 38, transform: "translateX(-50%)",
            display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
          }}>
            <div style={{ width: 1, height: 6, background: e.c }} />
            <div style={{
              fontSize: 9, color: e.c, letterSpacing: "0.04em", fontWeight: 600,
              whiteSpace: "nowrap", padding: "1px 6px", border: `1px solid ${e.c}`,
              borderRadius: 3, background: T2.bg,
            }}>{e.label}</div>
          </div>
        ))}
      </div>

      {/* Tick row */}
      <div style={{
        display: "flex", justifyContent: "space-between", marginTop: 8,
        fontFamily: T2.mono, fontSize: 9, color: T2.ink3, letterSpacing: "0.04em",
      }}>
        {["11P","12A","1A","2A","3A","4A","5A","6A","7A"].map(t => (
          <span key={t}>{t}</span>
        ))}
      </div>
    </div>
  );
}

// ── ROSTER CHIPS ──────────────────────────────────────────────────────────
function RosterChips() {
  const roster = [
    ["Marquez","g","Z1"],["Patel","g","Z2"],["Kim","g","Z4"],["Joy","g","Z5"],
    ["Reyes","g","Z6"],["Nguyen","g","Z8"],["Tran","g","Z9"],["Foster","g","Z10"],
    ["Lopez","g","RR1"],["Brooks","g","Dock"],
    ["Diaz","p","RR4"],["Singh","p","RR5"],
    ["Cole","a","Lobby"],["Park","a","Valet"],
    ["Ortega","x","—"],["Ramos","x","—"],
  ];
  const colors = {
    g: T2.green, p: T2.amber, a: T2.blue, x: T2.red,
  };
  const dims = {
    g: T2.greenDim, p: T2.amberDim, a: T2.blueDim, x: T2.redDim,
  };
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
      {roster.map(([n, k, z]) => (
        <span key={n} style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          fontSize: 11, padding: "3px 4px 3px 8px", borderRadius: 4,
          background: dims[k], color: colors[k],
          border: `1px solid ${colors[k]}`,
          textDecoration: k === "x" ? "line-through" : "none",
          opacity: k === "x" ? 0.6 : 1,
        }}>
          <span style={{ fontWeight: 600 }}>{n}</span>
          <span style={{
            fontSize: 9, padding: "1px 4px", borderRadius: 2,
            background: "rgba(0,0,0,0.3)", color: colors[k],
            fontFamily: T2.mono,
          }}>{z}</span>
        </span>
      ))}
    </div>
  );
}

// ── MAIN HUD ──────────────────────────────────────────────────────────────
function ShiftHUD_HiFi() {
  const zones = [
    { z: "Z1",  name: "Marquez", status: "ok",   wave: 1, time: "01:00", position: "Outdoor Smoking · Elevators" },
    { z: "Z2",  name: "Patel",   status: "ok",   wave: 2, time: "02:30", position: "Lobby Trash · Lobby RR" },
    { z: "Z3",  name: "—",       status: "open", wave: 3, time: "04:00", position: "—" },
    { z: "Z4",  name: "Kim",     status: "lock", wave: 1, time: "01:00", position: "Poker Drink Trays" },
    { z: "Z5",  name: "Joy",     status: "warn", wave: 2, time: "02:30", position: "High Limit Tables · TM Smoke" },
    { z: "Z6",  name: "Reyes",   status: "ok",   wave: 3, time: "04:00", position: "Outdoor Smoking" },
    { z: "Z7",  name: "—",       status: "open", wave: 1, time: "01:00", position: "Smoking · Pit 1&2 · S. Door" },
    { z: "Z8",  name: "Nguyen",  status: "ok",   wave: 2, time: "02:30", position: "Restrooms · Pit 3" },
    { z: "Z9",  name: "Tran",    status: "lock", wave: 3, time: "04:00", position: "Smoking Asst · Social Bar" },
    { z: "Z10", name: "Foster",  status: "ok",   wave: 1, time: "01:00", position: "High Limit Slots · Pit 4" },
  ];

  return (
    <div style={{
      width: 1180, height: 820, background: T2.bg, color: T2.ink, fontFamily: T2.font,
      display: "grid", gridTemplateColumns: "60px 1fr", overflow: "hidden",
      position: "relative",
    }}>
      {/* Rail */}
      <div style={{
        background: T2.panel, borderRight: `1px solid ${T2.line}`,
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "16px 0", gap: 4,
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 7,
          background: `linear-gradient(135deg, ${T2.blue}, #2A89C9)`,
          display: "grid", placeItems: "center", color: "#0B1A2A", fontWeight: 700, fontSize: 14,
        }}>G</div>
        <div style={{ height: 16, width: 24, marginTop: 6, marginBottom: 6, background: T2.line }} />
        {[
          { g: "⊙", l: "Shift",  active: true },
          { g: "▦", l: "ZDS" },
          { g: "⌕", l: "Search" },
          { g: "◍", l: "People" },
          { g: "☐", l: "Tasks" },
          { g: "✦", l: "Patterns" },
        ].map((x, i) => (
          <div key={i} style={{
            width: 40, height: 40, borderRadius: 8, display: "grid", placeItems: "center",
            color: x.active ? T2.blue : T2.ink3,
            background: x.active ? T2.blueDim : "transparent",
            fontSize: 16, position: "relative",
          }}>
            {x.g}
            {x.active && (
              <div style={{
                position: "absolute", left: -1, top: 8, bottom: 8, width: 2,
                background: T2.blue, borderRadius: 999,
              }} />
            )}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{
          width: 32, height: 32, borderRadius: 999, background: T2.panel2,
          border: `1px solid ${T2.line2}`, display: "grid", placeItems: "center",
          color: T2.ink2, fontSize: 11, fontWeight: 600,
        }}>BK</div>
      </div>

      {/* Main */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{
          padding: "16px 28px 0", borderBottom: `1px solid ${T2.line}`,
          background: `linear-gradient(180deg, ${T2.panel} 0%, ${T2.bg} 100%)`,
        }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16 }}>
            <div>
              <Eb c={T2.gold}>Wed · May 6 · Grave shift</Eb>
              <div style={{
                fontFamily: T2.serif, fontSize: 26, fontWeight: 400, fontStyle: "italic",
                letterSpacing: "-0.015em", marginTop: 4, color: T2.ink,
              }}>
                Good evening, Brian.
              </div>
            </div>
            <div style={{ flex: 1 }} />
            <Pill2 color={T2.amber} bg={T2.amberDim} border={T2.amber}>
              ⚑ 2 carried over
            </Pill2>
            <Pill2 color={T2.green} bg={T2.greenDim} border={T2.green}>
              <Dot2 c={T2.green} /> live · 01:42 in
            </Pill2>
          </div>
          <ShiftTimeline />
        </div>

        {/* Body */}
        <div style={{
          flex: 1, display: "grid", gridTemplateColumns: "1.55fr 1fr",
          gap: 1, background: T2.line, overflow: "hidden",
        }}>
          {/* HERO — Deployment */}
          <div style={{
            background: T2.bg, padding: "18px 24px", overflow: "auto",
            display: "flex", flexDirection: "column", gap: 16,
          }}>
            {/* Headline */}
            <div>
              <SectionHead
                title="Tonight's deployment"
                action={
                  <a style={{
                    fontSize: 11, color: T2.blue, fontWeight: 600, letterSpacing: "0.02em",
                  }}>Open in ZDS →</a>
                }
              />
              <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 10 }}>
                <div style={{
                  fontSize: 34, fontWeight: 700, fontVariantNumeric: "tabular-nums",
                  letterSpacing: "-0.02em",
                }}>
                  18<span style={{ color: T2.ink3, fontWeight: 400, fontSize: 22 }}> / 22</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    height: 5, background: T2.panel2, borderRadius: 999, overflow: "hidden",
                    border: `1px solid ${T2.line}`,
                  }}>
                    <div style={{
                      width: "82%", height: "100%",
                      background: `linear-gradient(90deg, ${T2.gold}, ${T2.green})`,
                    }} />
                  </div>
                  <div style={{
                    display: "flex", justifyContent: "space-between", marginTop: 6,
                    fontSize: 10, color: T2.ink3, letterSpacing: "0.06em",
                  }}>
                    <span style={{ color: T2.gold }}>● 6 LOCKED</span>
                    <span style={{ color: T2.amber }}>● 2 WARN</span>
                    <span style={{ color: T2.red }}>● 4 OPEN</span>
                    <span>● 10 OK</span>
                  </div>
                </div>
              </div>

              {/* Zone grid 5×2 */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6 }}>
                {zones.map(c => <ZoneCard key={c.z} {...c} />)}
              </div>
            </div>

            {/* RR + Aux side by side */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <SectionHead
                  title="Restrooms"
                  count="4 / 5"
                  action={<span style={{ fontSize: 10, color: T2.red, fontWeight: 600 }}>RR3 OPEN</span>}
                />
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4 }}>
                  {[
                    ["RR 1+2","Lopez","ok"],["RR 6","Brooks","ok"],["RR 7","—","open"],
                    ["RR 8","Diaz","ok"],["RR 10","Singh","ok"],
                  ].map(([r,n,s]) => (
                    <div key={r} style={{
                      background: s === "open" ? T2.redDim : T2.panel2,
                      border: `1px solid ${s === "open" ? T2.red : T2.line2}`,
                      borderRadius: 5, padding: "7px 8px",
                    }}>
                      <div style={{ fontSize: 9, color: T2.ink3, letterSpacing: "0.06em" }}>{r}</div>
                      <div style={{
                        fontSize: 11, fontWeight: 600, marginTop: 2,
                        color: n === "—" ? T2.mute : T2.ink,
                        display: "flex", flexDirection: "column", gap: 1,
                      }}>
                        <span style={{ fontSize: 9, color: T2.ink3, letterSpacing: "0.04em" }}>M</span>
                        <span>{n}</span>
                        <span style={{ fontSize: 9, color: T2.ink3, letterSpacing: "0.04em", marginTop: 2 }}>W</span>
                        <span>{n === "—" ? "—" : n + " ·"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <SectionHead title="Auxiliary" count="5 / 7" />
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 4 }}>
                  {[
                    ["Z9 SR","Cole","ok"],["Admin","—","open"],["Trash 1","Park","ok"],["Trash 2","—","open"],
                    ["Support 1","Brooks","ok"],["Support 2","Lopez","ok"],["Support 3","—","open"],
                  ].map(([a,n,s]) => (
                    <div key={a} style={{
                      background: s === "open" ? T2.redDim : T2.panel2,
                      border: `1px solid ${s === "open" ? T2.red : T2.line}`,
                      borderRadius: 5, padding: "6px 8px",
                    }}>
                      <div style={{ fontSize: 9, color: T2.ink3, letterSpacing: "0.06em" }}>{a}</div>
                      <div style={{
                        fontSize: 11, fontWeight: 600, marginTop: 2,
                        color: n === "—" ? T2.mute : T2.ink,
                      }}>{n}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Wave strip */}
            <div>
              <SectionHead title="Break waves" action={
                <span style={{ fontSize: 10, color: T2.blue, fontWeight: 600 }}>● W2 ACTIVE</span>
              }/>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {[
                  { n: 1, t: "01:00 – 01:30", s: "done",   on: "5 / 5", c: T2.green,
                    names: ["Marquez","Kim","Foster","Lopez","Cole"] },
                  { n: 2, t: "02:30 – 03:00", s: "active", on: "3 / 9", c: T2.blue,
                    names: ["Patel","Joy","Nguyen","Diaz"] },
                  { n: 3, t: "04:00 – 04:30", s: "queue",  on: "0 / 4", c: T2.ink3,
                    names: ["Reyes","Tran","Singh","Park"] },
                ].map(w => (
                  <div key={w.n} style={{
                    border: `1px solid ${w.c}`, borderRadius: 6, padding: "8px 12px",
                    background: w.s === "active" ? T2.blueDim : "transparent",
                    display: "flex", flexDirection: "column", gap: 6,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{
                        fontSize: 18, fontWeight: 700, color: w.c, fontVariantNumeric: "tabular-nums",
                        width: 26,
                      }}>W{w.n}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontFamily: T2.mono, fontSize: 11, color: T2.ink2 }}>{w.t}</div>
                        <div style={{
                          fontSize: 9, color: w.c, letterSpacing: "0.1em",
                          textTransform: "uppercase", fontWeight: 700, marginTop: 1,
                        }}>{w.s}</div>
                      </div>
                      <div style={{
                        fontFamily: T2.mono, fontSize: 12, color: T2.ink3,
                      }}>{w.on}</div>
                    </div>
                    <div style={{
                      display: "flex", flexWrap: "wrap", gap: 3,
                      paddingTop: 6, borderTop: `1px solid ${w.s === "active" ? "rgba(92,192,255,0.2)" : T2.line}`,
                    }}>
                      {w.names.map(nm => (
                        <span key={nm} style={{
                          fontSize: 10, padding: "2px 6px", borderRadius: 3,
                          background: w.s === "active" ? "rgba(0,0,0,0.25)" : T2.panel2,
                          color: w.s === "done" ? T2.ink3 : w.c,
                          textDecoration: w.s === "done" ? "line-through" : "none",
                          opacity: w.s === "done" ? 0.7 : 1,
                          fontWeight: 500,
                        }}>{nm}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT — Roster + Inherited + Tasks + Activity */}
          <div style={{
            background: T2.bg, padding: "18px 22px", overflow: "auto",
            display: "flex", flexDirection: "column", gap: 18,
          }}>
            {/* Roster */}
            <div>
              <SectionHead
                title="Roster"
                count="14 on floor · 2 off"
              />
              <RosterChips />
              <div style={{
                display: "flex", gap: 12, marginTop: 10,
                fontSize: 10, color: T2.ink3, letterSpacing: "0.06em",
              }}>
                <span><Dot2 c={T2.green}/> 10 GRAVE</span>
                <span><Dot2 c={T2.amber}/> 2 PM OL</span>
                <span><Dot2 c={T2.blue}/> 2 AM OL</span>
                <span><Dot2 c={T2.red}/> 2 OFF</span>
              </div>
            </div>

            {/* Inherited */}
            <div style={{
              background: T2.amberDim, border: `1px solid ${T2.amber}`,
              borderRadius: 8, padding: "12px 14px",
            }}>
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                marginBottom: 8,
              }}>
                <Eb c={T2.amber}>⚑ Carried over from Tue</Eb>
                <span style={{ fontSize: 10, color: T2.amber, fontWeight: 600 }}>2</span>
              </div>
              {[
                { t: "Z9 SR — repeat issue, walk early", from: "Lopez · 6:42A" },
                { t: "BEO 4127 still open from Mon",     from: "Brian · 11:14P" },
              ].map((it, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: 8, padding: "6px 0",
                  borderTop: i > 0 ? `1px solid rgba(242,178,58,0.2)` : "none",
                }}>
                  <Dot2 c={T2.amber} size={6} style={{ marginTop: 6 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: T2.ink, lineHeight: 1.35 }}>{it.t}</div>
                    <div style={{ fontSize: 10, color: T2.ink3, marginTop: 1 }}>{it.from}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Tonight tasks */}
            <div>
              <SectionHead
                title="Tonight"
                count="4 open"
                action={<a style={{ fontSize: 11, color: T2.blue, fontWeight: 600 }}>All →</a>}
              />
              {[
                { t: "BEO 4127 — set in Pavilion", time: "by 03:00", tag: "BEO" },
                { t: "Restock EVS cart 2",         time: "anytime",  tag: "TASK" },
                { t: "Walk south corridor",        time: "02:30",    tag: "WALK" },
                { t: "PM walk debrief w/ Diaz",    time: "06:45",    tag: "MEET" },
              ].map((it, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 0",
                  borderBottom: i < 3 ? `1px solid ${T2.line}` : "none",
                }}>
                  <Dot2 c={T2.blue} size={6} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: T2.ink, fontWeight: 500 }}>{it.t}</div>
                    <div style={{
                      display: "flex", gap: 8, marginTop: 2,
                      fontSize: 10, color: T2.ink3, letterSpacing: "0.04em",
                    }}>
                      <span style={{ fontFamily: T2.mono }}>{it.time}</span>
                      <span>·</span>
                      <span>{it.tag}</span>
                    </div>
                  </div>
                  <span style={{
                    width: 22, height: 22, borderRadius: 999,
                    border: `1px solid ${T2.line2}`,
                    display: "grid", placeItems: "center",
                    fontSize: 11, color: T2.ink3,
                  }}>✓</span>
                </div>
              ))}
            </div>

            {/* Activity */}
            <div>
              <SectionHead title="Activity" />
              {[
                ["01:42", "Joy",     "→ Z9 SR walk",        T2.gold],
                ["01:38", "Brian",   "Locked Z4 (Kim)",     T2.ink2],
                ["01:21", "System",  "W1 break complete",   T2.green],
                ["01:08", "Brian",   "Ramos call-off",      T2.red],
                ["00:52", "Brian",   "Ortega no-call",      T2.red],
                ["00:00", "System",  "Shift opened",        T2.ink3],
              ].map(([t, who, what, c], i) => (
                <div key={i} style={{
                  display: "flex", gap: 10, padding: "5px 0", fontSize: 11,
                }}>
                  <span style={{
                    color: T2.ink3, fontFamily: T2.mono, width: 38, fontSize: 10,
                  }}>{t}</span>
                  <span style={{ color: T2.ink3, width: 44 }}>{who}</span>
                  <span style={{ color: c, flex: 1 }}>{what}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Thumb cluster — bottom right */}
      <div style={{
        position: "absolute", bottom: 24, right: 24,
        display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8,
      }}>
        {[
          { i: "⚑", l: "Call-out", c: T2.red },
          { i: "★", l: "Kudos",    c: T2.gold },
          { i: "⊟", l: "BEO",      c: T2.blue },
        ].map(b => (
          <button key={b.l} style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "8px 14px 8px 12px", borderRadius: 999,
            background: T2.panel, border: `1px solid ${b.c}`, color: b.c,
            fontSize: 11, fontWeight: 600, letterSpacing: "0.04em",
            textTransform: "uppercase",
            boxShadow: `0 6px 20px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.4)`,
            cursor: "pointer", fontFamily: T2.font,
          }}>
            <span style={{ fontSize: 13 }}>{b.i}</span>{b.l}
          </button>
        ))}
        <button style={{
          width: 64, height: 64, borderRadius: 999, marginTop: 4,
          background: `radial-gradient(circle at 35% 30%, #8AD3FF, ${T2.blue} 60%, #2A89C9)`,
          color: "#0B1A2A", fontSize: 32, fontWeight: 300,
          boxShadow: `0 12px 32px rgba(92,192,255,0.5), 0 0 0 1px rgba(92,192,255,0.3)`,
          border: "none", cursor: "pointer",
          display: "grid", placeItems: "center",
        }}>+</button>
      </div>
    </div>
  );
}

window.ShiftHUD_HiFi = ShiftHUD_HiFi;
