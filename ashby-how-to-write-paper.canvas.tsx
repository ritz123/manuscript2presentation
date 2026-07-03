import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H3,
  Pill,
  Row,
  Spacer,
  Stack,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

// ── design tokens shorthand ────────────────────────────────────────────────

/** Bullet row — small dot + text */
function Bullet({ children, accent }: { children: string; accent?: boolean }) {
  const { text, stroke, accent: ac } = useHostTheme();
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
      <div
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: accent ? ac.primary : stroke.secondary,
          marginTop: 8,
          flexShrink: 0,
        }}
      />
      <Text style={{ color: text.primary, lineHeight: 1.6 }}>{children}</Text>
    </div>
  );
}

/** Subtle section label */
function SectionTag({ label }: { label: string }) {
  const { fill, accent } = useHostTheme();
  return (
    <div
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 4,
        background: fill.secondary,
        marginBottom: 8,
      }}
    >
      <Text
        style={{
          color: accent.primary,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </Text>
    </div>
  );
}

/** Italic left-bordered quotation */
function Quote({ children, attribution }: { children: string; attribution?: string }) {
  const { accent, text } = useHostTheme();
  return (
    <div
      style={{ borderLeft: `3px solid ${accent.primary}`, paddingLeft: 16, paddingTop: 4, paddingBottom: 4 }}
    >
      <Text style={{ color: text.primary, fontStyle: "italic", lineHeight: 1.6 }}>
        "{children}"
      </Text>
      {attribution && (
        <Text style={{ color: text.secondary, fontSize: 12, marginTop: 6 }}>— {attribution}</Text>
      )}
    </div>
  );
}

/** Two-column poor vs better comparison */
function Compare({ poor, better }: { poor: string; better: string }) {
  const { stroke, bg, accent, fill, text } = useHostTheme();
  return (
    <Grid columns={2} style={{ gap: 10 }}>
      <div style={{ padding: 12, borderRadius: 6, border: `1px solid ${stroke.tertiary}`, background: bg.elevated }}>
        <Text style={{ color: text.secondary, fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>
          Poor
        </Text>
        <Text style={{ color: text.primary, fontStyle: "italic", lineHeight: 1.5 }}>{poor}</Text>
      </div>
      <div style={{ padding: 12, borderRadius: 6, border: `1px solid ${accent.primary}`, background: fill.tertiary }}>
        <Text style={{ color: accent.primary, fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>
          Better
        </Text>
        <Text style={{ color: text.primary, fontStyle: "italic", lineHeight: 1.5 }}>{better}</Text>
      </div>
    </Grid>
  );
}

/** Slide progress dots */
function SlideProgress({ current, total }: { current: number; total: number }) {
  const { accent, stroke } = useHostTheme();
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          style={{
            width: i === current ? 20 : 6,
            height: 6,
            borderRadius: 3,
            background: i === current ? accent.primary : stroke.tertiary,
            transition: "all 0.2s",
          }}
        />
      ))}
    </div>
  );
}

// ── slides ─────────────────────────────────────────────────────────────────

function TitleSlide() {
  const { text, stroke, accent } = useHostTheme();
  return (
    <Stack style={{ gap: 32, alignItems: "center", paddingTop: 24 }}>
      <div style={{ width: 64, height: 4, borderRadius: 2, background: accent.primary }} />
      <Text style={{ color: text.secondary, textAlign: "center", maxWidth: 540, lineHeight: 1.7 }}>
        A prescriptive guide to designing, drafting, and refining research papers — covering
        structure, grammar, punctuation, and style.
      </Text>
      <Grid columns={4} style={{ gap: 12, width: "100%", maxWidth: 560 }}>
        {["Design", "Structure", "Grammar", "Style"].map((t) => (
          <div
            key={t}
            style={{ padding: "10px 0", borderRadius: 6, border: `1px solid ${stroke.tertiary}`, textAlign: "center" }}
          >
            <Text style={{ color: text.primary, fontWeight: 600, fontSize: 13 }}>{t}</Text>
          </div>
        ))}
      </Grid>
      <Text style={{ color: text.secondary, fontSize: 12 }}>
        9 sections · Appendix with examples · Checklist
      </Text>
    </Stack>
  );
}

function DesignProcessSlide() {
  const { text, accent } = useHostTheme();
  const steps: [string, string][] = [
    ["Market Need", "Who will read it? How will they use it?"],
    ["Concept", "Plan with a concept-sheet before drafting."],
    ["Embodiment", "First draft — get facts down without worrying about style."],
    ["Detail", "Crafting: clarity, balance, readability — style."],
    ["End-Product", "Appearance matters: good layout, clear headings, well-designed figures."],
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Section 1" />
      <Quote attribution="Ashby">
        Well-written papers are read, remembered, cited. Poorly written papers are not.
      </Quote>
      <Text style={{ color: text.secondary, lineHeight: 1.6 }}>
        Writing a paper is like engineering design — it follows five essential steps:
      </Text>
      <Stack style={{ gap: 10 }}>
        {steps.map(([step, desc], i) => (
          <div key={step} style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
            <div
              style={{
                minWidth: 26, height: 26, borderRadius: "50%", background: accent.primary,
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}
            >
              <Text style={{ color: "#fff", fontWeight: 700, fontSize: 12 }}>{i + 1}</Text>
            </div>
            <Stack style={{ gap: 2 }}>
              <Text style={{ color: text.primary, fontWeight: 600 }}>{step}</Text>
              <Text style={{ color: text.secondary, fontSize: 13 }}>{desc}</Text>
            </Stack>
          </div>
        ))}
      </Stack>
    </Stack>
  );
}

function ReadersSlide() {
  const { text } = useHostTheme();
  const audiences: { label: string; desc: string }[] = [
    { label: "Thesis examiners", desc: "Want all relevant parts of your research — why, background, thinking, what you did, conclusions. Not irrelevant standard procedures." },
    { label: "Journal referees & readers", desc: "Scientifically informed. Expect rigour, novelty, and concision. Peer-review is the gate." },
    { label: "Research proposal panel", desc: "Funding agency looks for alignment with priorities. Referees judge quality, promise, and relevance." },
    { label: "Popular audience", desc: "Intelligent but non-specialist. Style must be fine-tuned — the most demanding writing of all." },
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Section 2 — The Market" />
      <Text style={{ color: text.secondary, lineHeight: 1.6 }}>
        Every audience expects different things. Put yourself in their shoes.
      </Text>
      <Grid columns={2} style={{ gap: 12 }}>
        {audiences.map(({ label, desc }) => (
          <div key={label}>
            <Card>
              <CardHeader>{label}</CardHeader>
              <CardBody>
                <Text style={{ color: text.secondary, fontSize: 13, lineHeight: 1.5 }}>{desc}</Text>
              </CardBody>
            </Card>
          </div>
        ))}
      </Grid>
      <Callout tone="info">
        Write poorly and you'll bore, exasperate, and ultimately lose your readers. Write well,
        and they'll respond in the way you plan.
      </Callout>
    </Stack>
  );
}

function ConceptSheetSlide() {
  const { text } = useHostTheme();
  const howTo = [
    "Use an A3 sheet in landscape orientation.",
    "Write a tentative title at the top.",
    "Add section headings in boxes.",
    "Sketch paragraph ideas, figures, references in bubbles.",
    "Draw arrows to show order and links.",
    "Add to it at any time — it is your road-map.",
  ];
  const why = [
    "Frees your thinking to range over the entire paper.",
    "Lets you explore how pieces fit together.",
    "Captures ideas before they escape.",
    "Breaks writer's block.",
    "Keeps you focused on the whole, not just the current section.",
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Section 3 — Concept" />
      <Text style={{ color: text.primary, lineHeight: 1.6 }}>
        When you can't write, it's because you don't know what you want to say. The concept-sheet
        structures your thinking before you write a word.
      </Text>
      <Grid columns={2} style={{ gap: 16 }}>
        <Stack style={{ gap: 10 }}>
          <H3>How to make one</H3>
          <Stack style={{ gap: 8 }}>
            {howTo.map((item, i) => (
              <div key={i}><Bullet accent={i === 0}>{item}</Bullet></div>
            ))}
          </Stack>
        </Stack>
        <Stack style={{ gap: 10 }}>
          <H3>Why it works</H3>
          <Stack style={{ gap: 8 }}>
            {why.map((item, i) => (
              <div key={i}><Bullet>{item}</Bullet></div>
            ))}
          </Stack>
          <Callout tone="warning">
            This can be the most satisfying step. Later steps can feel like squeezing water from
            stone — but not this one.
          </Callout>
        </Stack>
      </Grid>
    </Stack>
  );
}

function PaperStructureSlide() {
  const { text, stroke } = useHostTheme();
  const sections: { num: string; name: string; note: string }[] = [
    { num: "4.1", name: "Title", note: "Meaningful and brief" },
    { num: "4.2", name: "Attribution", note: "Names, institute, date" },
    { num: "4.3", name: "Abstract", note: "≤100 words; motive, method, results, conclusions" },
    { num: "4.4", name: "Introduction", note: "Problem, literature, novel contribution" },
    { num: "4.5", name: "Method", note: "Sufficient detail to reproduce" },
    { num: "4.6", name: "Results", note: "Output only — no interpretation" },
    { num: "4.7", name: "Discussion", note: "Principles, models, comparison" },
    { num: "4.8", name: "Conclusion", note: "Advances in knowledge; bullet-pointed is fine" },
    { num: "4.9", name: "Acknowledgements", note: "Simple, full names, no sentimentality" },
    { num: "4.10", name: "References", note: "Complete: name, year, journal, pages" },
    { num: "4.11", name: "Figures", note: "Self-contained; title + caption + labelled axes" },
    { num: "4.12", name: "Appendices", note: "Essential material that interrupts flow" },
  ];
  return (
    <Stack style={{ gap: 16 }}>
      <SectionTag label="Section 4 — Embodiment" />
      <Text style={{ color: text.secondary, lineHeight: 1.6 }}>
        Papers are not drafted sequentially. Draft sections in any order, assembling pieces in whatever form they come.
      </Text>
      <Grid columns={3} style={{ gap: 10 }}>
        {sections.map(({ num, name, note }) => (
          <div key={num} style={{ padding: 10, borderRadius: 6, border: `1px solid ${stroke.tertiary}` }}>
            <Text style={{ color: text.secondary, fontSize: 11, display: "block", marginBottom: 2 }}>{num}</Text>
            <Text style={{ color: text.primary, fontWeight: 600, fontSize: 13, display: "block" }}>{name}</Text>
            <Text style={{ color: text.secondary, fontSize: 12, lineHeight: 1.4 }}>{note}</Text>
          </div>
        ))}
      </Grid>
    </Stack>
  );
}

function AbstractIntroSlide() {
  const { text, accent } = useHostTheme();
  const abstractItems = [
    "One sentence each on: motive, method, key results, conclusions.",
    "Never exceed 3 sentences on any one aspect.",
    "Target ≤100 words.",
    "No waffle, no spurious detail.",
    "Imagine you're paying 10p per word.",
  ];
  const introItems = [
    "What is the problem and why is it interesting?",
    "Who are the main contributors and what did they do?",
    "What novel thing will you reveal?",
    "Review the literature briefly.",
    "State clearly: new data? new model? new interpretation?",
    "Start with a good first sentence — not a platitude.",
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Sections 4.3 & 4.4" />
      <Grid columns={2} style={{ gap: 16 }}>
        <Stack style={{ gap: 10 }}>
          <H3 style={{ color: accent.primary }}>Abstract</H3>
          <Stack style={{ gap: 8 }}>
            {abstractItems.map((item, i) => (
              <div key={i}><Bullet accent={i === 0}>{item}</Bullet></div>
            ))}
          </Stack>
          <Divider />
          <Text style={{ color: text.secondary, fontSize: 12, fontWeight: 600 }}>
            Example structure (94 words):
          </Text>
          <Quote attribution="Ashby's model abstract">
            Metal foams, when compressed, deform by shear banding; the bands broaden as deformation progresses. We have studied the nucleation and broadening of shear bands by laser-speckle strain-mapping… The results indicate that processing to minimise density fluctuations could increase compressive yield strength by a factor of 1.5.
          </Quote>
        </Stack>
        <Stack style={{ gap: 10 }}>
          <H3 style={{ color: accent.primary }}>Introduction</H3>
          <Stack style={{ gap: 8 }}>
            {introItems.map((item, i) => (
              <div key={i}><Bullet>{item}</Bullet></div>
            ))}
          </Stack>
          <Callout tone="info">Keep it as brief as you can whilst still doing all this.</Callout>
        </Stack>
      </Grid>
    </Stack>
  );
}

function ResultsDiscussionSlide() {
  const { accent } = useHostTheme();
  const resultsItems = [
    "Report without opinion or interpretation.",
    "Define all symbols and units.",
    "Give error-bars or confidence limits.",
    "Present data others can use.",
    "Aim for concise, economical style.",
  ];
  const discussionItems = [
    "Extract principles, relationships, generalisations.",
    "Present analysis, model, or theory.",
    "Lead reader through comparison of model with data.",
    "Bring out the most significant conclusions first.",
    "Be clear and concise — not a licence to waffle.",
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Sections 4.6 & 4.7" />
      <Grid columns={2} style={{ gap: 16 }}>
        <Stack style={{ gap: 10 }}>
          <H3 style={{ color: accent.primary }}>Results</H3>
          <Stack style={{ gap: 8 }}>
            {resultsItems.map((item, i) => (
              <div key={i}><Bullet>{item}</Bullet></div>
            ))}
          </Stack>
          <Compare
            poor="It is clearly shown in Figure 3 that the shear loading had caused the cell-walls to suffer ductile fracture or possibly brittle failure."
            better="Shear loading fractures cell-walls (Figure 3)."
          />
        </Stack>
        <Stack style={{ gap: 10 }}>
          <H3 style={{ color: accent.primary }}>Discussion</H3>
          <Stack style={{ gap: 8 }}>
            {discussionItems.map((item, i) => (
              <div key={i}><Bullet>{item}</Bullet></div>
            ))}
          </Stack>
          <Callout tone="warning">
            Do not mix Results with Discussion. Keep them strictly separate.
          </Callout>
        </Stack>
      </Grid>
    </Stack>
  );
}

function GrammarSlide() {
  const { text } = useHostTheme();
  const parts: [string, string][] = [
    ["Nouns", "Names of things: Instron, metal, foam"],
    ["Pronouns", "Stand for nouns: he, she, it, they"],
    ["Adjectives", "Qualify nouns: small Instron, digital computer"],
    ["Verbs", "Being or action: is, deforms, interprets"],
    ["Adverbs", "Qualify verbs: interpreted differently"],
    ["Conjunctions", "Link clauses: and, but, because"],
    ["Prepositions", "Place or time: on the table, after this"],
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Section 5" />
      <Text style={{ color: text.secondary, lineHeight: 1.6 }}>
        Mess up the grammar and you confuse the reader. These are the simplest essentials.
      </Text>
      <Grid columns={2} style={{ gap: 16 }}>
        <Stack style={{ gap: 10 }}>
          <H3>Parts of Speech</H3>
          <Stack style={{ gap: 6 }}>
            {parts.map(([part, def]) => (
              <div key={part} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <Pill size="sm">{part}</Pill>
                <Text style={{ color: text.secondary, fontSize: 13 }}>{def}</Text>
              </div>
            ))}
          </Stack>
        </Stack>
        <Stack style={{ gap: 10 }}>
          <H3>Key Rules</H3>
          <Card>
            <CardHeader>{'\'that\' vs \'which\''}</CardHeader>
            <CardBody>
              <Stack style={{ gap: 6 }}>
                <Text style={{ color: text.secondary, fontSize: 13 }}>
                  <Text weight="semibold" as="span">that</Text> — limits the noun: "computations that were on a Cray" (only those ones).
                </Text>
                <Text style={{ color: text.secondary, fontSize: 13 }}>
                  <Text weight="semibold" as="span">which</Text> — adds a new fact (use commas): "computations, which were on a Cray, were more accurate."
                </Text>
              </Stack>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>Compound sentences</CardHeader>
            <CardBody>
              <Text style={{ color: text.secondary, fontSize: 13 }}>
                Two co-ordinate clauses must be of comparable weight. Don't mix major and trivial ideas in the same sentence.
              </Text>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>Sentence structure</CardHeader>
            <CardBody>
              <Text style={{ color: text.secondary, fontSize: 13 }}>
                Every sentence needs a subject and a predicate. Keep subject and verb close together.
              </Text>
            </CardBody>
          </Card>
        </Stack>
      </Grid>
    </Stack>
  );
}

function PunctuationSlide() {
  const { text, stroke, accent } = useHostTheme();
  const marks: { mark: string; name: string; rule: string }[] = [
    { mark: ".", name: "Full stop", rule: "Ends declarative sentences. Signifies abbreviation." },
    { mark: ",", name: "Comma", rule: "Separates parts that would confuse if they touched." },
    { mark: ";", name: "Semi-colon", rule: "Between closely related independent clauses; also separates list items." },
    { mark: ":", name: "Colon", rule: "Introduces exemplification, restatement, or elaboration." },
    { mark: "—", name: "Dash", rule: "Sets off parenthetic material. Can introduce a final upshot." },
    { mark: "-", name: "Hyphen", rule: "Connects compound words: ball-and-stick, box-girder." },
    { mark: "!", name: "Exclamation", rule: "Avoid in scientific writing — say what you want directly." },
    { mark: "'", name: "Apostrophe", rule: "Possession (Sutcliffe's) or contraction. No apostrophe in 'its' as possessive." },
    { mark: "( )", name: "Parentheses", rule: "Embrace asides. Don't let them cloud the main meaning." },
  ];
  return (
    <Stack style={{ gap: 16 }}>
      <SectionTag label="Section 7" />
      <Text style={{ color: text.secondary, lineHeight: 1.6 }}>
        Punctuation orders prose and sends signals about how to interpret it. Meaning can be changed dramatically by punctuation.
      </Text>
      <Grid columns={3} style={{ gap: 10 }}>
        {marks.map(({ mark, name, rule }) => (
          <div key={name} style={{ padding: 12, borderRadius: 6, border: `1px solid ${stroke.tertiary}` }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 6 }}>
              <Text style={{ color: accent.primary, fontWeight: 700, fontSize: 20, fontFamily: "serif" }}>
                {mark}
              </Text>
              <Text style={{ color: text.primary, fontWeight: 600, fontSize: 13 }}>{name}</Text>
            </div>
            <Text style={{ color: text.secondary, fontSize: 12, lineHeight: 1.5 }}>{rule}</Text>
          </div>
        ))}
      </Grid>
    </Stack>
  );
}

function StyleClaritySlide() {
  const { accent } = useHostTheme();
  const clearItems = [
    "Use simple language and concise construction.",
    "Short words rather than long.",
    "Familiar words, not obscure ones.",
    "When you've said something, make sure you've really said it.",
    "Don't waffle — if a sentence says only what the reader already knows, cut it.",
  ];
  const defineItems = [
    "Define all symbols on first use.",
    "Define all abbreviations: 'scanning electron microscope (SEM)'.",
    "Leave double space around symbols in text.",
  ];
  const emptyItems = [
    "Avoid clichés — corpses devoid of vitality.",
    "Avoid weak qualifiers: very, rather, somewhat, quite.",
    "'This very important point' → 'This point'",
    "'The agreement is quite good' — suggests it is not.",
  ];
  const reviseItems = [
    "Nobody gets it right first time.",
    "Some papers go through 8–10 drafts.",
    "The most spontaneous-seeming prose is often the most rewritten.",
    "Put the draft aside for at least 48 hours before revising.",
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Section 8" />
      <Quote>
        Style is approached through plainness, simplicity, good structure and desire to convey information in the most accessible way.
      </Quote>
      <Grid columns={2} style={{ gap: 16 }}>
        <Stack style={{ gap: 10 }}>
          <H3>8.1 Be clear</H3>
          <Stack style={{ gap: 8 }}>
            {clearItems.map((item, i) => (
              <div key={i}><Bullet accent={i === 4}>{item}</Bullet></div>
            ))}
          </Stack>
          <H3>8.3 Define everything</H3>
          <Stack style={{ gap: 8 }}>
            {defineItems.map((item, i) => (
              <div key={i}><Bullet>{item}</Bullet></div>
            ))}
          </Stack>
        </Stack>
        <Stack style={{ gap: 10 }}>
          <H3>8.4 Avoid empty words</H3>
          <Stack style={{ gap: 8 }}>
            {emptyItems.map((item, i) => (
              <div key={i}><Bullet accent={i === 1}>{item}</Bullet></div>
            ))}
          </Stack>
          <H3>8.5 Revise &amp; rewrite</H3>
          <Stack style={{ gap: 8 }}>
            {reviseItems.map((item, i) => (
              <div key={i}><Bullet>{item}</Bullet></div>
            ))}
          </Stack>
        </Stack>
      </Grid>
    </Stack>
  );
}

function PitfallsSlide() {
  const { text } = useHostTheme();
  const pitfalls: { label: string; body: string }[] = [
    { label: "Overstating", body: "'This paper questions the basic assumptions of fracture mechanics' — fills the reader with mistrust. Let the reader decide on importance." },
    { label: "Apologising", body: "'Unfortunately, there was insufficient time to complete the last set of tests' — suggests bad planning or laziness. Never, ever, apologise." },
    { label: "Jargon", body: "Jargon is the secret language of the field. It excludes the intelligent, otherwise well-informed reader. Avoid it unless genuinely necessary." },
    { label: "Patronising", body: "'The amazingly perceptive comment by Fleck…' or 'Readers familiar with my work will know…' — both condescending." },
    { label: "Breezy web-speak", body: "'Hi! me again with some hot news…' — The author says nothing and is showing off, drawing attention to themselves." },
    { label: "Acronym overload", body: "'The MEM, analysed by FE methods, was photographed by SEM and characterised by SAM.' — Minimise acronyms. Find other ways." },
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Sections 8.6 – 8.8" />
      <Grid columns={3} style={{ gap: 12 }}>
        {pitfalls.map(({ label, body }) => (
          <div key={label}>
            <Card>
              <CardHeader>{label}</CardHeader>
              <CardBody>
                <Text style={{ color: text.secondary, fontSize: 13, lineHeight: 1.5 }}>{body}</Text>
              </CardBody>
            </Card>
          </div>
        ))}
      </Grid>
    </Stack>
  );
}

function GoodWritingSlide() {
  const { text } = useHostTheme();
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Sections 8.9 – 8.12" />
      <Grid columns={2} style={{ gap: 16 }}>
        <Stack style={{ gap: 12 }}>
          <H3>8.9 Good First Sentence</H3>
          <Text style={{ color: text.secondary, fontSize: 13, lineHeight: 1.5 }}>
            Don't start with platitudes. Get a new fact, new idea, or a revealing comparison into the first line.
          </Text>
          <Compare
            poor="Metal foams are a new class of material attracting interest world-wide and with great potential…"
            better="Metal foams are not as strong as they should be. Models overestimate their strength by a factor of 2 to 5. This research explores the reasons."
          />
        </Stack>
        <Stack style={{ gap: 12 }}>
          <H3>8.10 Examples &amp; Analogies</H3>
          <Text style={{ color: text.secondary, fontSize: 13, lineHeight: 1.5 }}>
            Make the abstract concrete. Analogies relate a scientific problem to a familiar one.
          </Text>
          <Quote attribution="Ashby's analogy example">
            One cause of rolling friction is material damping. It is like riding a bicycle through sand: the rubbing sand particles dissipate energy much as atom rearrangements do.
          </Quote>
          <H3>8.11 Linking Sentences</H3>
          <Text style={{ color: text.secondary, fontSize: 13, lineHeight: 1.5 }}>
            End paragraphs with a word or phrase picked up in the first sentence of the next. The reader knows what's coming before reading it.
          </Text>
          <Quote>
            …To progress further, we need a way to rank the materials — a material index. A material index is a …
          </Quote>
        </Stack>
      </Grid>
    </Stack>
  );
}

function ChecklistSlide() {
  const { text, stroke, accent } = useHostTheme();
  const columns: { heading: string; items: string[]; primary?: boolean }[] = [
    {
      heading: "Concept & First Draft",
      primary: true,
      items: [
        "Make concept sheet", "Title and attribution", "Abstract", "Introduction",
        "Method", "Results", "Discussion", "Conclusions",
        "Acknowledgements", "References", "Figures and captions", "Appendices",
      ],
    },
    {
      heading: "Edited Draft",
      items: [
        "Clarity of argument", "Grammar checked", "Spelling verified",
        "Punctuation correct", "Style reviewed", "Waffle removed",
        "Symbols defined", "Abbreviations defined", "Figures self-contained",
        "References complete", "48-hour rest period",
      ],
    },
    {
      heading: "Visual Presentation",
      items: [
        "Good layout", "Clear headings", "Well-designed figures",
        "Axes labelled with units", "Curves labelled on graphs",
        "Captions informative", "Consistent formatting", "Legible at reduced size",
      ],
    },
  ];
  return (
    <Stack style={{ gap: 20 }}>
      <SectionTag label="Final Page of Manual" />
      <Text style={{ color: text.secondary }}>
        Use this checklist to see where you are at each stage of writing.
      </Text>
      <Grid columns={3} style={{ gap: 16 }}>
        {columns.map(({ heading, items, primary }) => (
          <div key={heading}>
            <Stack style={{ gap: 10 }}>
              <H3>{heading}</H3>
              <Stack style={{ gap: 6 }}>
                {items.map((item) => (
                  <div key={item} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <div
                      style={{
                        width: 14, height: 14, borderRadius: 3, flexShrink: 0,
                        border: `1.5px solid ${primary ? accent.primary : stroke.secondary}`,
                      }}
                    />
                    <Text style={{ color: text.secondary, fontSize: 13 }}>{item}</Text>
                  </div>
                ))}
              </Stack>
            </Stack>
          </div>
        ))}
      </Grid>
      <Callout tone="success">
        Put the draft on one side for at least 48 hours before editing. Then revise with fresh eyes.
      </Callout>
    </Stack>
  );
}

// ── slide registry ─────────────────────────────────────────────────────────

type SlideEntry = { title: string; subtitle?: string; Component: () => ReturnType<typeof TitleSlide> };

const SLIDES: SlideEntry[] = [
  { title: "How to Write a Paper", subtitle: "Mike Ashby · Engineering Department, University of Cambridge · 6th Edition, 2005", Component: TitleSlide },
  { title: "1. The Design Process", Component: DesignProcessSlide },
  { title: "2. Know Your Readers", Component: ReadersSlide },
  { title: "3. The Concept Sheet", Component: ConceptSheetSlide },
  { title: "4. Paper Structure — All 12 Sections", Component: PaperStructureSlide },
  { title: "Abstract & Introduction", Component: AbstractIntroSlide },
  { title: "Results & Discussion", Component: ResultsDiscussionSlide },
  { title: "5. Grammar Essentials", Component: GrammarSlide },
  { title: "7. Punctuation", Component: PunctuationSlide },
  { title: "8. Style — Clarity & Precision", Component: StyleClaritySlide },
  { title: "Common Pitfalls to Avoid", Component: PitfallsSlide },
  { title: "Good Writing Techniques", Component: GoodWritingSlide },
  { title: "Checklist for Progress", Component: ChecklistSlide },
];

// ── main ───────────────────────────────────────────────────────────────────

export default function AshbyHowToWritePaper() {
  const { bg, stroke, text, accent } = useHostTheme();
  const [idx, setIdx] = useCanvasState<number>("slide", 0);

  const { title, subtitle, Component: SlideComponent } = SLIDES[idx];

  return (
    <Stack style={{ minHeight: "100vh", background: bg.editor, paddingBottom: 32 }}>
      {/* Nav bar */}
      <div
        style={{
          padding: "12px 24px",
          borderBottom: `1px solid ${stroke.tertiary}`,
          background: bg.elevated,
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <Row gap={16} align="center">
          <Text style={{ color: text.secondary, fontSize: 12, fontWeight: 600 }}>
            HOW TO WRITE A PAPER · MIKE ASHBY
          </Text>
          <Spacer />
          <SlideProgress current={idx} total={SLIDES.length} />
          <Text style={{ color: text.secondary, fontSize: 12 }}>
            {idx + 1} / {SLIDES.length}
          </Text>
        </Row>
      </div>

      {/* Slide */}
      <div style={{ flex: 1, padding: "40px 40px 24px", maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Stack style={{ gap: 6, marginBottom: 24 }}>
          <H1>{title}</H1>
          {subtitle && <Text style={{ color: text.secondary }}>{subtitle}</Text>}
          <Divider />
        </Stack>
        <SlideComponent />
      </div>

      {/* Navigation */}
      <div
        style={{
          padding: "16px 40px",
          borderTop: `1px solid ${stroke.tertiary}`,
          position: "sticky",
          bottom: 0,
          background: bg.editor,
        }}
      >
        <Row gap={12} align="center" style={{ maxWidth: 960, margin: "0 auto" }}>
          <Button onClick={() => setIdx(Math.max(0, idx - 1))} disabled={idx === 0}>
            Previous
          </Button>
          <Spacer />
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "center" }}>
            {SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => setIdx(i)}
                style={{
                  padding: "3px 9px",
                  borderRadius: 4,
                  border: `1px solid ${i === idx ? accent.primary : stroke.tertiary}`,
                  background: i === idx ? `${accent.primary}22` : "transparent",
                  color: i === idx ? accent.primary : text.secondary,
                  cursor: "pointer",
                  fontSize: 12,
                  fontWeight: i === idx ? 600 : 400,
                }}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <Spacer />
          <Button
            onClick={() => setIdx(Math.min(SLIDES.length - 1, idx + 1))}
            disabled={idx === SLIDES.length - 1}
          >
            Next
          </Button>
        </Row>
      </div>
    </Stack>
  );
}
