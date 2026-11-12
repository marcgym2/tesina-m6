// Build the defense deck (thesis/slides/tesina_defensa.pptx).
//
//   cd thesis/slides && npm install && node build_slides.js
//
// Every result quoted on a slide is read from thesis/_variables.yml, thesis/_generated/
// or results/ (CLAUDE.md: no result is typed by hand). Run
// `uv run python scripts/build_thesis_results.py` first if results changed.

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("./apply_theme.js");

const THESIS = path.resolve(__dirname, "..");
const ROOT = path.resolve(THESIS, "..");
const OUT = path.join(__dirname, "tesina_defensa.pptx");

// ------------------------------------------------------------------------- data

function loadVars(file) {
  const vars = {};
  let group = null;
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    let m;
    if ((m = line.match(/^(\w+):\s*$/))) {
      group = vars[m[1]] = {};
    } else if ((m = line.match(/^\s+(\w+):\s*"(.*)"\s*$/)) && group) {
      group[m[1]] = m[2];
    }
  }
  return vars;
}

const V = loadVars(path.join(THESIS, "_variables.yml"));

/** Variable as displayed in the thesis, e.g. v("covsim.dif_p2") -> "−0.0049". */
function v(key) {
  const [g, k] = key.split(".");
  if (!V[g] || V[g][k] === undefined) throw new Error(`Missing variable ${key}`);
  return V[g][k];
}

/** Numeric value of a displayed figure ("−0.0049" -> -0.0049, "3.0 %" -> 3). */
function n(text) {
  const x = parseFloat(String(text).replace("−", "-").replace(/[^0-9.+-]/g, ""));
  if (Number.isNaN(x)) throw new Error(`Not a number: ${text}`);
  return x;
}

function mdTable(file) {
  const rows = fs
    .readFileSync(file, "utf8")
    .split("\n")
    .filter((l) => l.startsWith("|") && !/^\|[-:| ]+\|$/.test(l))
    .map((l) => l.split("|").slice(1, -1).map((c) => c.trim()));
  return { header: rows[0], rows: rows.slice(1) };
}

function csv(file) {
  const [head, ...lines] = fs.readFileSync(file, "utf8").trim().split("\n");
  const cols = head.split(",");
  return lines.map((l) => Object.fromEntries(l.split(",").map((c, i) => [cols[i], c])));
}

/** Run directory pinned in scripts/build_thesis_results.py (single source of truth). */
function pinnedRun(name) {
  const src = fs.readFileSync(path.join(ROOT, "scripts", "build_thesis_results.py"), "utf8");
  const m = src.match(new RegExp(`"${name}":\\s*"([^"]+)"`));
  if (!m) throw new Error(`Run ${name} is not pinned`);
  return path.join(ROOT, "results", name, m[1]);
}

const MODELS = [
  ["covsim", "Simulación desde covarianzas"],
  ["finqboost", "FinQBoost"],
  ["wound_ignite", "wound-ignite"],
  ["gbm", "GBM multiclase"],
  ["adagaussmc", "AdaGaussMC"],
  ["baselines", "Frecuencia histórica"],
  ["timesfm", "TimesFM-3"],
];
const irTable = mdTable(path.join(THESIS, "_generated", "tbl-ir.md"));
const cascade = csv(path.join(pinnedRun("cascade"), "cascade.csv"));

// ------------------------------------------------------------------------ theme

const THEME = {
  name: "Tesina M6",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A2F", // ink
    lt1: "FFFFFF",
    dk2: "0F3D3E", // deep teal: dominant
    lt2: "EDF3F1", // pale tint for cards
    accent1: "1F7A6C", // teal: what is real
    accent2: "D1432F", // vermilion: what is illusion
    accent3: "E0A526", // amber
    accent4: "5B6B70", // muted text
    accent5: "9DB8B2",
    accent6: "2F4858",
    hlink: "1F7A6C",
    folHlink: "5B6B70",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "¿Cuánto del alfa es ilusión?";
pres.author = "Marco Antonio Obregón Flores";
const C = pres.SchemeColor;

const W = 13.33;
const MX = 0.6; // side margin
const CW = W - 2 * MX; // content width
const TOP = 1.95; // content top on content slides
const SHORT_TITLE = "¿Cuánto del alfa es ilusión?  ·  Tesina MCD, FCFM UANL";

function footer(color) {
  return [
    {
      text: {
        text: SHORT_TITLE,
        options: { x: MX, y: 6.95, w: 8, h: 0.3, fontSize: 10, color, margin: 0, isTextBox: true },
      },
    },
  ];
}

pres.defineSlideMaster({
  title: "COVER",
  background: { color: HEX.dk2 },
  objects: [
    {
      placeholder: {
        options: {
          name: "title", type: "title", x: MX, y: 1.5, w: 10.5, h: 1.5,
          fontSize: 54, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0,
        },
        text: "",
      },
    },
    {
      placeholder: {
        options: {
          name: "body", type: "body", x: MX, y: 3.25, w: 10.5, h: 1.5,
          fontSize: 22, color: C.accent5, valign: "top", margin: 0,
        },
        text: "",
      },
    },
  ],
});

for (const [name, bg, titleColor, footColor] of [
  ["CONTENT", HEX.lt1, C.text2, C.accent4],
  ["CONTENT_DARK", HEX.dk2, C.background1, C.accent5],
]) {
  pres.defineSlideMaster({
    title: name,
    background: { color: bg },
    objects: [
      {
        placeholder: {
          options: {
            name: "title", type: "title", x: MX, y: 0.45, w: CW, h: 1.3,
            fontSize: 36, bold: true, color: titleColor, valign: "top", align: "left", margin: 0,
          },
          text: "",
        },
      },
      ...footer(footColor),
    ],
    slideNumber: { x: W - MX - 0.6, y: 6.95, w: 0.6, h: 0.3, fontSize: 10, color: footColor, align: "right" },
  });
}

// ---------------------------------------------------------------------- helpers

let section = "";
function startSection(title) {
  section = title;
  pres.addSection({ title });
}

function contentSlide(title, notes, dark = false) {
  const s = pres.addSlide({ masterName: dark ? "CONTENT_DARK" : "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}

let uid = 0;
const oname = (base) => `${base} ${++uid}`;

function text(s, t, opts) {
  s.addText(t, { isTextBox: true, margin: 0, color: C.text1, fontSize: 16, valign: "top", objectName: oname("Text"), ...opts });
}

function card(s, x, y, w, h, fill = C.background2) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: oname("Card"),
  });
}

/** Card with a heading and a paragraph. */
function textCard(s, x, y, w, h, head, body, o = {}) {
  card(s, x, y, w, h, o.fill);
  const pad = 0.3;
  text(s, head, {
    x: x + pad, y: y + pad, w: w - 2 * pad, h: o.headH || 0.45, fontSize: o.headSize || 20, bold: true,
    color: o.headColor || C.text2, fontFace: "Cambria",
  });
  text(s, body, {
    x: x + pad, y: y + pad + (o.headH || 0.45) + 0.1, w: w - 2 * pad, h: h - 2 * pad - (o.headH || 0.45) - 0.1,
    fontSize: o.bodySize || 16, color: o.bodyColor || C.text1,
  });
}

/** Big number with a label under it. */
function stat(s, x, y, w, value, label, color = C.accent1, size = 60) {
  text(s, value, { x, y, w, h: 1.0, fontSize: size, bold: true, color, fontFace: "Cambria", valign: "bottom" });
  text(s, label, { x, y: y + 1.1, w, h: 0.9, fontSize: 15, color: C.accent4 });
}

/** Number in a filled circle (the deck's motif). */
function badge(s, x, y, label, fill = C.accent1, d = 0.6) {
  s.addText(String(label), {
    shape: pres.shapes.OVAL, x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 },
    color: C.background1, bold: true, fontSize: 18, align: "center", valign: "middle", margin: 0,
    isTextBox: true, fontFace: "Cambria", objectName: oname("Badge"),
  });
}

/** Dark band at the bottom with the slide's message in one plain sentence. */
function takeaway(s, t, label = "En corto:") {
  card(s, MX, 6.0, CW, 0.7, C.text2);
  text(s, [
    { text: `${label}  `, options: { bold: true, color: C.accent3 } },
    { text: t, options: { color: C.background1 } },
  ], { x: MX + 0.3, y: 6.0, w: CW - 0.6, h: 0.7, fontSize: 16, valign: "middle" });
}

const CHART_TEXT = { fontFace: "+mn-lt", color: HEX.accent4, size: 12 };
function chartBase(extra) {
  return {
    catAxisLabelColor: CHART_TEXT.color, valAxisLabelColor: CHART_TEXT.color,
    catAxisLabelFontFace: CHART_TEXT.fontFace, valAxisLabelFontFace: CHART_TEXT.fontFace,
    catAxisLabelFontSize: CHART_TEXT.size, valAxisLabelFontSize: CHART_TEXT.size,
    dataLabelColor: HEX.dk1, dataLabelFontFace: CHART_TEXT.fontFace, dataLabelFontSize: CHART_TEXT.size,
    valGridLine: { color: "DDE5E3", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: false, showTitle: false,
    ...extra,
  };
}

// ----------------------------------------------------------------------- slides

// 1 ── Cover
startSection("Planteamiento");
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: section });
  s.addText("¿Cuánto del alfa es ilusión?", { placeholder: "title" });
  s.addText(
    "Evaluación honesta de pronósticos probabilísticos de rendimiento relativo con aprendizaje automático: réplica y extensión de la competencia M6",
    { placeholder: "body" }
  );
  text(s, "Marco Antonio Obregón Flores", { x: MX, y: 5.5, w: 9, h: 0.4, fontSize: 20, bold: true, color: C.background1 });
  text(s, "Maestría en Ciencia de Datos  ·  FCFM, UANL  ·  2026", { x: MX, y: 5.95, w: 9, h: 0.4, fontSize: 16, color: C.accent5 });
  s.addNotes("Presentación de la tesina. El título resume la pregunta: cuánto del desempeño que reportan las estrategias de aprendizaje automático sobrevive a una evaluación honesta.");
}

// 2 ── Motivation
{
  const s = contentSlide(
    "Entre la promesa y la teoría",
    "La hipótesis de mercados eficientes dice que no se puede superar al mercado de forma sistemática. Al mismo tiempo circulan promesas de trading con IA respaldadas por simulaciones históricas. La pregunta útil no es si el ML le gana al mercado, sino cuánto de lo que se reporta sobrevive a una evaluación honesta."
  );
  const h = 2.35, w = (CW - 0.4) / 2;
  textCard(s, MX, TOP, w, h, "Lo que se promete",
    "Plataformas, cursos y productos ofrecen “trading con inteligencia artificial” a inversionistas no profesionales, casi siempre con simulaciones históricas de rendimientos sobresalientes.",
    { headColor: C.accent2 });
  textCard(s, MX + w + 0.4, TOP, w, h, "Lo que dice la teoría",
    "Si los precios incorporan la información disponible, superar al mercado de forma sistemática no debería ser posible (hipótesis de mercados eficientes).",
    { headColor: C.accent1 });
  card(s, MX, TOP + h + 0.4, CW, 1.7, C.text2);
  text(s, "¿Cuánto del desempeño que reporta una estrategia sobrevive cuando se le evalúa con honestidad?", {
    x: MX + 0.4, y: TOP + h + 0.4, w: CW - 0.8, h: 1.7, fontSize: 24, italic: true, color: C.background1,
    fontFace: "Cambria", valign: "middle",
  });
}

// 3 ── M6
{
  const s = contentSlide(
    "La competencia M6 como laboratorio",
    "La M6 fue la primera competencia M dedicada a mercados financieros. Se evaluó en vivo, sobre datos que no existían al pronosticar. Sus envíos, su código de evaluación y el código de varios ganadores son públicos, y ya pasó tiempo suficiente para evaluar esos métodos con datos nuevos."
  );
  const w = (CW - 3 * 0.4) / 4;
  const items = [
    ["100", "activos: 50 acciones del S&P 500 y 50 ETF internacionales"],
    [v("uniforme.n_p1"), "periodos de cuatro semanas, de marzo de 2022 a febrero de 2023"],
    [v("replica.equipos"), "equipos en el ranking global de la competencia"],
    ["2", "calificaciones: una para el pronóstico (RPS) y otra para la inversión (IR)"],
  ];
  items.forEach(([value, label], i) => stat(s, MX + i * (w + 0.4), TOP + 0.1, w, value, label));
  textCard(s, MX, 4.75, CW, 1.75, "Por qué sirve como laboratorio",
    "La evaluación fue en vivo, no una simulación histórica. Los envíos reales de todos los equipos, el código oficial de evaluación y el código de varios métodos ganadores son públicos.");
}

// 4 ── How the M6 scores (defines quintiles, uniform, RPS, IR)
{
  const s = contentSlide(
    "Cómo se califica en la M6",
    "Antes de los resultados, las reglas del juego. Cada periodo los 100 activos se ordenan por rendimiento y se parten en cinco grupos de 20: los quintiles. El pronóstico es una probabilidad por quintil para cada activo. El uniforme pone 20 % en cada quintil: es no saber nada, y es el rival a vencer. El RPS mide el error: menor es mejor. Aparte se califica la inversión con el IR, y ahí el rival es invertir lo mismo en todos los activos."
  );
  const w = (CW - 0.4) / 2, h = 3.85, pad = 0.3;
  const panel = (x, head, body) => {
    card(s, x, TOP, w, h);
    text(s, head, { x: x + pad, y: TOP + 0.25, w: w - 2 * pad, h: 0.45, fontSize: 22, bold: true, color: C.text2, fontFace: "Cambria" });
    text(s, body, { x: x + pad, y: TOP + 0.8, w: w - 2 * pad, h: 1.0, fontSize: 15 });
  };
  // Left: the forecast
  panel(MX, "1. El pronóstico",
    "Cada periodo los 100 activos se ordenan por rendimiento y se parten en 5 quintiles de 20. Se pronostica la probabilidad de que cada activo caiga en cada quintil.");
  const bars = (x0, heights, color, label) => {
    const bw = 0.36, gap = 0.08, base = TOP + 2.9;
    heights.forEach((p, i) => {
      const bh = (p / 40) * 0.9;
      s.addShape(pres.shapes.RECTANGLE, { x: x0 + i * (bw + gap), y: base - bh, w: bw, h: bh, fill: { color }, line: { color, width: 0 }, objectName: oname("Barra") });
    });
    text(s, label, { x: x0, y: base + 0.06, w: 2.6, h: 0.3, fontSize: 12, color: C.accent4 });
  };
  bars(MX + pad, [20, 20, 20, 20, 20], C.accent4, "Uniforme: 20 % a cada quintil");
  bars(MX + pad + 2.95, [34, 14, 8, 14, 30], C.accent1, "Un modelo (ejemplo ilustrativo)");
  text(s, [{ text: "RPS: ", options: { bold: true } }, { text: "el error del pronóstico. Menor es mejor." }], {
    x: MX + pad, y: TOP + 3.35, w: w - 2 * pad, h: 0.35, fontSize: 15,
  });
  // Right: the investment
  const x = MX + w + 0.4;
  panel(x, "2. La inversión",
    "Además del pronóstico, cada participante arma un portafolio con esos mismos activos, y se le califica por separado.");
  const row = (y, lead, body) => {
    card(s, x + pad, y, w - 2 * pad, 0.75, C.background1);
    text(s, [{ text: `${lead}  `, options: { bold: true, color: C.text2 } }, { text: body }], {
      x: x + pad + 0.2, y, w: w - 2 * pad - 0.4, h: 0.75, fontSize: 15, valign: "middle",
    });
  };
  row(TOP + 1.85, "IR:", "rendimiento ajustado por riesgo. Mayor es mejor.");
  row(TOP + 2.75, "Rival:", "invertir lo mismo en los 100 activos (pesos iguales).");
  takeaway(s, "pronosticar 20 % en todo es no saber nada. Un modelo que no le gana a eso no aporta.", "El uniforme:");
}

// 4b ── Sources of illusion
{
  const s = contentSlide(
    "Cinco fuentes de desempeño ilusorio",
    "Las cinco inflan los resultados en la misma dirección y sus efectos se acumulan. La tesina las mide una por una en la cascada de sesgos."
  );
  const items = [
    ["Fuga de información", "Usar datos que no estaban disponibles al momento de decidir."],
    ["Validación no temporal", "Validación cruzada aleatoria aplicada a series financieras."],
    ["Sesgo de supervivencia", "Elegir el universo de activos después de conocer su destino."],
    ["Sobreajuste por búsqueda", "Probar muchas configuraciones y reportar solo la mejor."],
    ["Costos omitidos", "Ignorar lo que cuesta operar la estrategia."],
  ];
  const w = (CW - 4 * 0.3) / 5, h = 3.6;
  items.forEach(([head, body], i) => {
    const x = MX + i * (w + 0.3);
    card(s, x, TOP + 0.3, w, h);
    badge(s, x + 0.25, TOP + 0.55, i + 1, C.accent2);
    text(s, head, { x: x + 0.25, y: TOP + 1.35, w: w - 0.5, h: 0.9, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
    text(s, body, { x: x + 0.25, y: TOP + 2.3, w: w - 0.5, h: 1.5, fontSize: 15 });
  });
  text(s, "Todas inflan los resultados en la misma dirección, y sus efectos se acumulan.", {
    x: MX, y: 6.15, w: CW, h: 0.4, fontSize: 16, italic: true, color: C.accent4,
  });
}

// 5 ── Research questions
{
  const s = contentSlide(
    "Cuatro preguntas de investigación",
    "RQ5, sobre atención en Wikipedia y rendimientos, era opcional y queda como trabajo futuro."
  );
  const rq = [
    ["RQ1", "Persistencia", "¿Los métodos ganadores de la M6 siguen ganando con datos nuevos?"],
    ["RQ2", "Evaluación limpia", "Evaluado sin trampas, ¿algún modelo pronostica mejor que el uniforme?"],
    ["RQ3", "Pronóstico frente a decisión", "¿Pronosticar mejor sirve para invertir mejor?"],
    ["RQ4", "Cascada de sesgos", "¿Cuánto se infla un resultado cuando se evalúa mal?"],
  ];
  const w = (CW - 0.4) / 2, h = 2.1;
  rq.forEach(([tag, head, body], i) => {
    const x = MX + (i % 2) * (w + 0.4), y = TOP + Math.floor(i / 2) * (h + 0.35);
    card(s, x, y, w, h);
    badge(s, x + 0.3, y + 0.3, tag.slice(2), C.accent1);
    text(s, head, { x: x + 1.1, y: y + 0.3, w: w - 1.4, h: 0.6, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria", valign: "middle" });
    text(s, body, { x: x + 1.1, y: y + 1.0, w: w - 1.4, h: 0.95, fontSize: 16 });
  });
}

// 6 ── Design
startSection("Metodología");
{
  const s = contentSlide(
    "Dos periodos, un mismo protocolo",
    "El periodo 1 es la competencia original: ahí los modelos se comparan con los envíos reales de los equipos. El periodo 2 es la prueba fuera de muestra: datos que nadie vio durante la competencia. El mismo protocolo contra la fuga de información se aplica a todos los modelos, y se verifica con pruebas automáticas."
  );
  const n1 = n(v("uniforme.n_p1")), n2 = n(v("uniforme.n_p2"));
  const w1 = 4.0, w2 = CW - w1 - 0.15, y = TOP + 0.1, h = 1.5;
  card(s, MX, y, w1, h, C.accent6);
  card(s, MX + w1 + 0.15, y, w2, h, C.accent1);
  const tl = (x, w, head, sub) => {
    text(s, head, { x: x + 0.3, y: y + 0.2, w: w - 0.6, h: 0.5, fontSize: 20, bold: true, color: C.background1, fontFace: "Cambria" });
    text(s, sub, { x: x + 0.3, y: y + 0.75, w: w - 0.6, h: 0.6, fontSize: 15, color: C.background1 });
  };
  tl(MX, w1, `Periodo 1 · ${n1} periodos`, "Mar 2022 – feb 2023. La M6 original.");
  tl(MX + w1 + 0.15, w2, `Periodo 2 · ${n2} periodos`, "Mar 2023 – nov 2026. Datos que nadie vio durante la competencia.");

  text(s, "Regla de fondo: el modelo nunca ve el futuro", { x: MX, y: 3.95, w: CW, h: 0.4, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
  const rules = [
    "Entrenar y probar en orden temporal",
    "Ajustar todo solo con datos del pasado",
    "Calcular los quintiles dentro de cada periodo",
    "Separar entrenamiento y prueba si se traslapan",
    "Usar los activos que existían en cada fecha",
    "Reportar con y sin costos de operar",
  ];
  const w = (CW - 2 * 0.3) / 3;
  rules.forEach((r, i) => {
    const x = MX + (i % 3) * (w + 0.3), yy = 4.5 + Math.floor(i / 3) * 1.0;
    card(s, x, yy, w, 0.8);
    badge(s, x + 0.15, yy + 0.15, i + 1, C.accent1, 0.5);
    text(s, r, { x: x + 0.8, y: yy, w: w - 0.95, h: 0.8, fontSize: 15, valign: "middle" });
  });
}

// 7 ── Models
{
  const s = contentSlide(
    "Siete modelos contra el pronóstico uniforme",
    "El benchmark de pronóstico es el uniforme: 0.2 por quintil. Se evalúan una referencia simple, tres métodos de equipos ganadores y tres modelos propios. Significancia: prueba pareada de Diebold y Mariano contra el uniforme, con ajuste de Holm por comparaciones múltiples."
  );
  const rows = [
    ["Referencia", "Frecuencia histórica", "Frecuencia pasada de cada quintil por activo"],
    ["Ganadores M6", "FinQBoost", "Gradient boosting sobre variables técnicas"],
    ["Ganadores M6", "wound-ignite", "Covarianzas de 200 días y simulación gaussiana"],
    ["Ganadores M6", "AdaGaussMC", "Volatilidad adaptativa y simulación (reimplementado del artículo)"],
    ["Propio", "GBM multiclase", "Quintil a partir de variables de precio"],
    ["Propio", "Simulación desde covarianzas", "Covarianza EWMA con media cero: un solo parámetro"],
    ["Propio", "TimesFM-3", "Nada: modelo fundacional preentrenado, zero-shot"],
  ];
  const head = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.dk2 }, fontSize: 15 } });
  const cell = (t, i, bold) => ({ text: t, options: { color: C.text1, bold: !!bold, fontSize: 15, fill: { color: i % 2 ? HEX.lt2 : HEX.lt1 } } });
  s.addTable(
    [[head("Grupo"), head("Modelo"), head("Qué aprende")], ...rows.map((r, i) => [cell(r[0], i), cell(r[1], i, true), cell(r[2], i)])],
    { x: MX, y: TOP, w: CW, colW: [2.2, 3.6, CW - 5.8], rowH: 0.48, border: { type: "none" }, margin: [0.05, 0.15, 0.05, 0.15], valign: "middle", objectName: "Tabla de modelos" }
  );
  text(s, "Cada modelo se compara con el uniforme periodo por periodo, y se exige evidencia más fuerte por haber probado varios modelos a la vez.", {
    x: MX, y: 6.05, w: CW, h: 0.6, fontSize: 15, italic: true, color: C.accent4,
  });
}

// 8 ── Replication
startSection("Resultados");
{
  const s = contentSlide(
    "La réplica reproduce el leaderboard oficial",
    "El RPS y el IR se implementaron a partir del código oficial y se validaron contra el leaderboard publicado. Para coincidir hubo que inferir reglas no documentadas, como el redondeo del RPS antes de ordenar y el tratamiento de empates. Los dos programas oficiales, en R y en Python, no son equivalentes cuando hay empates o precios faltantes."
  );
  const w = (CW - 2 * 0.4) / 3;
  stat(s, MX, TOP + 0.1, w, v("replica.rangos_distintos"), "rangos distintos de los oficiales");
  stat(s, MX + w + 0.4, TOP + 0.1, w, v("replica.filas_mes"), "puntajes mensuales comparados");
  stat(s, MX + 2 * (w + 0.4), TOP + 0.1, w, v("replica.equipos"), "equipos del ranking global");
  const h = 2.0, w2 = (CW - 0.4) / 2;
  textCard(s, MX, 4.4, w2, h, "Las cifras globales coinciden",
    `${v("replica.mejor_rps")} equipos superaron al benchmark en RPS, ${v("replica.mejor_ir")} en IR y ${v("replica.mejor_ambos")} en ambas métricas.`);
  textCard(s, MX + w2 + 0.4, 4.4, w2, h, "Reglas que el código no documenta",
    "Hubo que inferir el redondeo del RPS y el manejo de empates. Los programas oficiales en R y en Python no son equivalentes.");
}

// 9 ── Teams in period 1
{
  const s = contentSlide(
    "Periodo 1: pocos equipos se distinguen del uniforme",
    "Con doce periodos, la gran mayoría de los equipos que quedaron arriba del benchmark no se distingue estadísticamente de él. Además, entre esos equipos, pronosticar mejor no se asoció con invertir mejor: la correlación de Spearman entre RPS e IR es prácticamente cero."
  );
  const labels = ["Equipos en el ranking", "Mejores que el uniforme en promedio", "Con diferencia significativa", "Tras corregir comparaciones múltiples"];
  const values = [n(v("equipos.n")), n(v("equipos.mejor_media")), n(v("equipos.sig_sin_ajuste")), n(v("equipos.sig_holm"))];
  s.addChart(pres.charts.BAR, [{ name: "Equipos", labels, values }], chartBase({
    x: MX, y: TOP, w: 7.6, h: 3.8, barDir: "bar", catAxisOrientation: "maxMin", chartColors: [HEX.accent1],
    showValue: true, dataLabelPosition: "outEnd", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 60,
    objectName: "Equipos significativos",
  }));
  const x = MX + 8.0, w = CW - 8.0;
  card(s, x, TOP, w, 3.8);
  text(s, "¿Pronosticar bien e invertir bien van juntos?", { x: x + 0.3, y: TOP + 0.3, w: w - 0.6, h: 0.8, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  text(s, v("equipos.spearman"), { x: x + 0.3, y: TOP + 1.05, w: w - 0.6, h: 1.0, fontSize: 60, bold: true, color: C.accent2, fontFace: "Cambria", valign: "bottom" });
  text(s, `Correlación de Spearman entre RPS e IR (0 = sin relación). IC 95 %: ${v("equipos.spearman_ic")}.`, {
    x: x + 0.3, y: TOP + 2.2, w: w - 0.6, h: 1.1, fontSize: 15, color: C.accent4,
  });
  takeaway(s, `de ${v("equipos.n")} equipos, solo ${v("equipos.sig_holm")} le ganan al uniforme con claridad, y pronosticar mejor no se asoció con invertir mejor.`);
}

// 10 ── Models in period 2 (RQ2)
{
  const s = contentSlide(
    `RQ2: ${v("modelos.sig_p2")} de ${v("modelos.n")} modelos superan al uniforme`,
    "Periodo 2, fuera de muestra. La mejora es pequeña pero muy regular: esa regularidad, y no el tamaño, es lo que produce valores p tan bajos. El resultado no depende de cómo se trate a los activos deslistados (sensibilidad D4)."
  );
  s.addChart(pres.charts.BAR, [{
    name: "Diferencia de RPS contra el uniforme, periodo 2",
    labels: MODELS.map(([, name]) => name),
    values: MODELS.map(([k]) => n(v(`${k}.dif_p2`))),
  }], chartBase({
    x: MX, y: TOP, w: 7.8, h: 3.5, barDir: "bar", catAxisOrientation: "maxMin", catAxisLabelPos: "low",
    chartColors: MODELS.map(([k]) => (n(v(`${k}.dif_p2`)) < 0 ? HEX.accent1 : HEX.accent2)),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0000", valAxisLabelFormatCode: "0.000",
    barGapWidthPct: 50, objectName: "Diferencia de RPS por modelo",
  }));
  text(s, `Diferencia de RPS contra el uniforme en ${v("uniforme.n_p2")} periodos. Barra hacia la izquierda = menos error que el uniforme.`, {
    x: MX, y: TOP + 3.55, w: 7.8, h: 0.5, fontSize: 12, color: C.accent4,
  });
  const x = MX + 8.2, w = CW - 8.2;
  stat(s, x, TOP - 0.1, w, v("covsim.rel_p2"), "menos error que el uniforme: el mejor modelo", C.accent1, 54);
  stat(s, x, TOP + 1.85, w, v("covsim.mejor_p2"), "de los periodos en los que ese modelo le gana al uniforme", C.accent1, 54);
  takeaway(s, "casi todos los modelos pronostican un poco mejor que el uniforme. La mejora es pequeña, pero se repite periodo tras periodo.");
}

// 11 ── Interpretation
{
  const s = contentSlide(
    "La ventaja viene de la volatilidad, no de la dirección",
    "Los seis modelos que superan al uniforme explotan que los activos difieren en volatilidad. Eso anticipa qué activos terminarán en los quintiles extremos, no cuáles subirán, y por eso no contradice la eficiencia de mercado."
  );
  const w = (CW - 2 * 0.4) / 3, h = 3.8;
  const cards = [
    ["Todos explotan la volatilidad", "El mejor modelo supone que ningún activo rinde más que otro. Solo sabe cuáles se mueven más, y con eso basta.", C.accent1],
    ["La complejidad no ayudó", "El gradient boosting, con nueve variables, queda por debajo de un modelo con un solo parámetro.", C.accent6],
    ["El modelo fundacional fue el único peor", `TimesFM-3 pronostica peor que el uniforme: solo le gana en el ${v("timesfm.mejor_p2")} de los periodos.`, C.accent2],
  ];
  cards.forEach(([head, body, color], i) => {
    const x = MX + i * (w + 0.4);
    card(s, x, TOP, w, h);
    badge(s, x + 0.3, TOP + 0.3, i + 1, color);
    text(s, head, { x: x + 0.3, y: TOP + 1.15, w: w - 0.6, h: 0.95, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
    text(s, body, { x: x + 0.3, y: TOP + 2.2, w: w - 0.6, h: 1.4, fontSize: 16 });
  });
  takeaway(s, "los modelos anticipan qué activos tendrán movimientos extremos, no cuáles van a subir. Eso no contradice la eficiencia del mercado.");
}

// 12 ── RQ1 persistence
{
  const s = contentSlide(
    "RQ1: la ventaja de los ganadores persiste",
    "FinQBoost es el único método validado por completo contra los envíos reales del equipo. wound-ignite solo se valida en parte y AdaGaussMC no queda validado: su renglón es el desempeño del procedimiento que describe el artículo, no el del equipo. La persistencia se explica porque las diferencias de volatilidad entre activos son estables."
  );
  const methods = [["finqboost", "FinQBoost"], ["wound_ignite", "wound-ignite"], ["adagaussmc", "AdaGaussMC"]];
  const labels = methods.map(([, name]) => name);
  s.addChart(pres.charts.BAR, [
    { name: "Periodo 1 (competencia)", labels, values: methods.map(([k]) => n(v(`${k}.dif_p1`))) },
    { name: "Periodo 2 (después)", labels, values: methods.map(([k]) => n(v(`${k}.dif_p2`))) },
  ], chartBase({
    x: MX, y: TOP, w: 7.6, h: 3.5, barDir: "col", barGrouping: "clustered", catAxisLabelPos: "high",
    chartColors: [HEX.accent5, HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.0000", valAxisLabelFormatCode: "0.0000",
    showLegend: true, legendPos: "b", legendColor: CHART_TEXT.color, legendFontFace: CHART_TEXT.fontFace, legendFontSize: CHART_TEXT.size,
    objectName: "Persistencia por método",
  }));
  text(s, "Diferencia media de RPS contra el uniforme (negativa = mejor).", { x: MX, y: TOP + 3.55, w: 7.6, h: 0.4, fontSize: 12, color: C.accent4 });
  const x = MX + 8.0, w = CW - 8.0;
  text(s, "¿El código reproduce lo que envió el equipo?", { x, y: TOP, w, h: 0.7, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  const fid = [
    ["FinQBoost", `Sí (correlación de ${v("finqboost.fid_corr")})`, C.accent1],
    ["wound-ignite", `En parte (${v("wound_ignite.fid_corr_mes10")} en un envío)`, C.accent3],
    ["AdaGaussMC", `No (correlación de ${v("adagaussmc.fid_corr")})`, C.accent2],
  ];
  fid.forEach(([name, body, color], i) => {
    const y = TOP + 0.8 + i * 1.0;
    card(s, x, y, w, 0.85);
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.3, w: 0.25, h: 0.25, fill: { color }, line: { color, width: 0 }, objectName: oname("Dot") });
    text(s, name, { x: x + 0.7, y: y + 0.1, w: w - 0.9, h: 0.33, fontSize: 16, bold: true });
    text(s, body, { x: x + 0.7, y: y + 0.45, w: w - 0.9, h: 0.3, fontSize: 14, color: C.accent4 });
  });
  takeaway(s, "la ventaja de los ganadores no desapareció después de la competencia, porque las diferencias de volatilidad entre activos son estables.");
}

// 13 ── RQ3 forecast vs decision
{
  const better = v("inversion.mejores_que_bench_p2"), active = v("inversion.activos");
  const s = contentSlide(
    "RQ3: pronosticar mejor no es invertir mejor",
    "La mayoría de los modelos invierte con pesos iguales, así que su IR es el del benchmark. De los portafolios que se apartan de él, ninguno lo supera en IR neto. Saber qué activos son más volátiles no dice en qué dirección se moverán. Advertencia: el IR de la M6 no anualiza, así que crece con el número de periodos."
  );
  const iNet = irTable.header.lastIndexOf("IR neto");
  const short = (name) => name.replace(/\s*\(.*\)/, "");
  s.addChart(pres.charts.BAR, [{
    name: "IR neto, periodo 2",
    labels: irTable.rows.map((r) => short(r[0])),
    values: irTable.rows.map((r) => n(r[iNet])),
  }], chartBase({
    x: MX, y: TOP, w: 7.6, h: 3.5, barDir: "col", catAxisLabelPos: "low",
    chartColors: irTable.rows.map((r, i) => (i === 0 ? HEX.accent4 : HEX.accent1)),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", barGapWidthPct: 60,
    objectName: "IR neto por portafolio",
  }));
  text(s, "IR del periodo 2, ya descontados los costos de operar. Barra más alta = mejor inversión.", {
    x: MX, y: TOP + 3.55, w: 7.6, h: 0.4, fontSize: 12, color: C.accent4,
  });
  const x = MX + 8.0, w = CW - 8.0;
  stat(s, x, TOP - 0.1, w, `${better} de ${active}`, "portafolios distintos al de pesos iguales lo superan", C.accent2, 54);
  stat(s, x, TOP + 1.85, w, v("inversion.spearman_modelos"), `correlación entre pronosticar bien e invertir bien, en ${v("inversion.spearman_modelos_n")} portafolios`, C.accent2, 54);
  takeaway(s, "saber qué activos se mueven más no dice hacia dónde se moverán, y eso es lo que necesita un portafolio.");
}

// 14 ── RQ4 cascade
{
  const s = contentSlide(
    "RQ4: la cascada de sesgos desinfla el Sharpe",
    "El mismo gradient boosting, evaluado con distinto cuidado. El procedimiento ingenuo reporta un Sharpe que duplica al de pesos iguales. Casi toda esa ventaja proviene de la fuga de información: desaparece con el split temporal y la purga de etiquetas. Con todas las correcciones y costos, queda por debajo del benchmark."
  );
  const SHORT = { "+ preprocesamiento solo con el pasado": "+ preproceso con el pasado", "+ universo point-in-time": "+ universo en cada fecha", "+ costos de transacción": "+ costos" };
  const labels = cascade.map((r) => SHORT[r.name] || r.name);
  s.addChart(
    [
      { type: pres.charts.BAR, data: [{ name: "Gradient boosting", labels, values: cascade.map((r) => +(+r.sharpe).toFixed(2)) }], options: { chartColors: [HEX.accent1], barGapWidthPct: 50 } },
      { type: pres.charts.LINE, data: [{ name: "Pesos iguales", labels, values: cascade.map((r) => +(+r.sharpe_benchmark).toFixed(2)) }], options: { chartColors: [HEX.accent2], lineSize: 2, lineDataSymbol: "none", lineDash: ["dash"] } },
    ],
    chartBase({
      x: MX, y: TOP, w: 8.3, h: 3.5, showValue: false, valAxisMinVal: 0, valAxisLabelFormatCode: "0.0",
      showLegend: true, legendPos: "b", legendColor: CHART_TEXT.color, legendFontFace: CHART_TEXT.fontFace, legendFontSize: CHART_TEXT.size,
      catAxisLabelFontSize: 11, objectName: "Sharpe por paso de la cascada",
    })
  );
  text(s, "Sharpe (rendimiento por unidad de riesgo) del mismo modelo. Cada barra corrige un error más de evaluación.", { x: MX, y: TOP + 3.55, w: 8.3, h: 0.4, fontSize: 12, color: C.accent4 });
  const x = MX + 8.7, w = CW - 8.7;
  stat(s, x, TOP - 0.1, w, v("cascada.sharpe_s0"), `Sharpe mal evaluado: ${v("cascada.veces_bench_s0")} veces el de pesos iguales`, C.accent2, 54);
  stat(s, x, TOP + 1.85, w, v("cascada.sharpe_s6"), `Sharpe bien evaluado: debajo del ${v("cascada.sharpe_bench")} de pesos iguales`, C.accent1, 54);
  takeaway(s, "el mismo modelo parece duplicar al portafolio de pesos iguales o quedar debajo de él, según el cuidado con que se le evalúe.");
}

// 15 ── RQ4 reading
{
  const s = contentSlide(
    "La ilusión estuvo en la decisión, no en el pronóstico",
    "En la métrica de inversión los sesgos inflan mucho el desempeño. En la de pronóstico no: el modelo evaluado con honestidad pronostica mejor que el evaluado con trampa, porque sustituir las variables estandarizadas con toda la muestra por rangos entre activos elimina una fuga y además representa mejor la posición relativa. Con split temporal y purga, pero aún con las variables ingenuas, la ventaja casi desaparece."
  );
  const w = (CW - 0.4) / 2, h = 3.3;
  const col = (x, head, sub, a, b, color, foot) => {
    card(s, x, TOP, w, h);
    text(s, head, { x: x + 0.35, y: TOP + 0.3, w: w - 0.7, h: 0.45, fontSize: 22, bold: true, color: C.text2, fontFace: "Cambria" });
    text(s, sub, { x: x + 0.35, y: TOP + 0.8, w: w - 0.7, h: 0.35, fontSize: 14, color: C.accent4 });
    text(s, [
      { text: a, options: { color: C.accent4 } },
      { text: "  →  ", options: { color: C.accent4 } },
      { text: b, options: { color } },
    ], { x: x + 0.35, y: TOP + 1.2, w: w - 0.7, h: 1.0, fontSize: 38, bold: true, fontFace: "Cambria", valign: "middle" });
    text(s, foot, { x: x + 0.35, y: TOP + 2.3, w: w - 0.7, h: 0.8, fontSize: 16 });
  };
  col(MX, "Inversión", "Sharpe: mal evaluado → bien evaluado", v("cascada.sharpe_s0"), v("cascada.sharpe_s6"), C.accent2,
    `Los sesgos lo inflaron: se pierden ${v("cascada.caida_sharpe")} puntos y queda bajo el ${v("cascada.sharpe_bench")} de pesos iguales.`);
  col(MX + w + 0.4, "Pronóstico", "Ventaja en RPS sobre el uniforme: mal evaluado → bien evaluado", v("cascada.dif_s0"), v("cascada.dif_s6"), C.accent1,
    "Los sesgos no lo inflaron: el modelo evaluado con honestidad pronostica mejor.");
  takeaway(s, "la fuga de información infló la ganancia aparente del portafolio, no la calidad del pronóstico.");
}

// 16 ── Limitations
startSection("Conclusiones");
{
  const s = contentSlide(
    "Limitaciones",
    "Cinco limitaciones que acotan la lectura de los resultados."
  );
  const items = [
    ["Periodo 1 corto", `Solo ${v("uniforme.n_p1")} observaciones: la evidencia descansa en el periodo 2.`],
    ["Validación parcial de los ganadores", "Dos de tres métodos no se validaron por completo contra sus envíos; el de sebrad no se evaluó."],
    ["Cascada con un orden y un modelo", "Otro orden atribuiría partes distintas a cada sesgo, y un paso mezcla dos efectos."],
    ["Sharpe e IR descriptivos", "Sus diferencias en la cascada no tienen prueba estadística."],
    ["Un solo régimen de mercado", "En el periodo 2 el portafolio de pesos iguales subió; no se sabe qué pasaría a la baja."],
  ];
  const h = 0.8;
  items.forEach(([head, body], i) => {
    const y = TOP + i * (h + 0.12);
    card(s, MX, y, CW, h);
    badge(s, MX + 0.2, y + 0.15, i + 1, C.accent6, 0.5);
    text(s, head, { x: MX + 0.95, y, w: 3.9, h, fontSize: 16, bold: true, color: C.text2, valign: "middle" });
    text(s, body, { x: MX + 5.0, y, w: CW - 5.2, h, fontSize: 15, valign: "middle" });
  });
}

// 17 ── Conclusions
{
  const s = contentSlide(
    "Una respuesta en dos partes",
    "Lo que no es ilusión es la mejora en el pronóstico de quintiles: real, pequeña y muy regular. Lo ilusorio es leer esa mejora como capacidad de ganarle al mercado. Ninguno de los dos números de la cascada requiere mala fe: la diferencia está en errores de procedimiento fáciles de cometer y difíciles de ver desde fuera.",
    true
  );
  const w = (CW - 0.4) / 2, h = 3.4;
  const col = (x, head, color, bullets) => {
    card(s, x, TOP, w, h, C.background1);
    s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: TOP + 0.42, w: 0.3, h: 0.3, fill: { color }, line: { color, width: 0 }, objectName: oname("Dot") });
    text(s, head, { x: x + 0.85, y: TOP + 0.3, w: w - 1.2, h: 0.55, fontSize: 22, bold: true, color: C.text2, fontFace: "Cambria", valign: "middle" });
    text(s, bullets.map((b, i) => ({ text: b, options: { bullet: true, breakLine: i < bullets.length - 1, paraSpaceAfter: 10 } })), {
      x: x + 0.35, y: TOP + 1.05, w: w - 0.7, h: h - 1.3, fontSize: 16,
    });
  };
  col(MX, "Lo que no es ilusión", C.accent1, [
    `${v("modelos.sig_p2")} de ${v("modelos.n")} modelos superan al uniforme en un periodo que ninguno vio, tras ajustar por comparaciones múltiples.`,
    "Los métodos ganadores de la M6 conservan su ventaja.",
    "La mejora en RPS es real, pequeña y muy regular.",
  ]);
  col(MX + w + 0.4, "Lo que sí es ilusión", C.accent2, [
    "Leer esa mejora como capacidad de ganarle al mercado: proviene de anticipar la volatilidad.",
    "Ningún portafolio derivado de los pronósticos superó al de pesos iguales.",
    `El mismo modelo reporta un Sharpe de ${v("cascada.sharpe_s0")} con fuga de información y de ${v("cascada.sharpe_s6")} sin ella y con costos.`,
  ]);
  text(s, [
    { text: "Trabajo futuro:  ", options: { bold: true, color: C.accent3 } },
    { text: "repetir la cascada con otros órdenes y modelos, probar reglas de inversión basadas en modelos de riesgo, y estudiar atención y rendimientos (RQ5)." },
  ], { x: MX, y: TOP + 3.7, w: CW, h: 0.8, fontSize: 16, color: C.background1 });
}

// 18 ── What to ask (closing message for the non-professional investor)
{
  const s = contentSlide(
    "Qué preguntar ante un backtest espectacular",
    "Cierre para el inversionista no profesional. Cuando alguien muestra una simulación histórica con rendimientos sobresalientes, estas cuatro preguntas corresponden a los errores de evaluación que medí en la cascada. Si no hay respuesta clara a alguna, el resultado dice poco."
  );
  text(s, "Para quien recibe una promesa de “trading con IA”: una pregunta por cada error de evaluación que mide la tesina.", {
    x: MX, y: TOP - 0.05, w: CW, h: 0.5, fontSize: 16, color: C.accent4,
  });
  const qs = [
    ["¿El periodo de prueba es posterior a todo lo que el modelo vio?", "Si no: el modelo vio el futuro"],
    ["¿Los activos se eligieron antes de conocer su destino?", "Si no: solo quedan los que sobrevivieron"],
    ["¿Cuántas variantes se probaron?", "Si fueron muchas: se reporta la más afortunada"],
    ["¿El resultado descuenta los costos de operar?", "Si no: la ganancia está inflada"],
  ];
  const h = 0.85;
  qs.forEach(([q, why], i) => {
    const y = TOP + 0.65 + i * (h + 0.13);
    card(s, MX, y, CW, h);
    badge(s, MX + 0.2, y + 0.175, i + 1, C.accent1, 0.5);
    text(s, q, { x: MX + 0.95, y, w: 6.7, h, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
    text(s, why, { x: MX + 7.9, y, w: CW - 8.1, h, fontSize: 15, color: C.accent2, valign: "middle" });
  });
}

// 19 ── Glossary (backup for questions)
startSection("Respaldo");
{
  const s = contentSlide(
    "Glosario",
    "Diapositiva de respaldo para la sesión de preguntas."
  );
  const rows = [
    ["Quintil", "Cada uno de los 5 grupos de 20 activos, ordenados por rendimiento en el periodo."],
    ["Uniforme", "Pronóstico de 20 % para cada quintil: el de quien no sabe nada. Es el rival a vencer."],
    ["RPS", "Error del pronóstico de quintiles. Menor es mejor."],
    ["IR", "Calificación de la inversión en la M6: rendimiento ajustado por riesgo. Mayor es mejor."],
    ["Sharpe", "Rendimiento por unidad de riesgo, anualizado."],
    ["Fuga de información", "Usar, al entrenar o decidir, datos que aún no existían en esa fecha."],
    ["Purga y embargo", "Quitar del entrenamiento lo que se traslapa con la prueba y dejar un margen entre ambos."],
    ["Ajuste de Holm", "Corrección que exige más evidencia cuando se prueban varios modelos a la vez."],
    ["Sesgo de supervivencia", "Evaluar solo con los activos que siguen existiendo hoy."],
  ];
  const cell = (t, i, bold) => ({ text: t, options: { color: bold ? C.text2 : C.text1, bold: !!bold, fontSize: 15, fill: { color: i % 2 ? HEX.lt1 : HEX.lt2 } } });
  s.addTable(rows.map((r, i) => [cell(r[0], i, true), cell(r[1], i)]), {
    x: MX, y: TOP - 0.2, w: CW, colW: [3.0, CW - 3.0], rowH: 0.5, border: { type: "none" },
    margin: [0.05, 0.15, 0.05, 0.15], valign: "middle", objectName: "Glosario",
  });
}

// ------------------------------------------------------------------------ write

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log(`Wrote ${path.relative(ROOT, OUT)}`);
})();
