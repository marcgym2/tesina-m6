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
    ["2", "métricas: RPS para el pronóstico de quintiles, IR para la inversión"],
  ];
  items.forEach(([value, label], i) => stat(s, MX + i * (w + 0.4), TOP + 0.1, w, value, label));
  textCard(s, MX, 4.75, CW, 1.75, "Por qué sirve como laboratorio",
    "La evaluación fue en vivo, no una simulación histórica. Los envíos reales de todos los equipos, el código oficial de evaluación y el código de varios métodos ganadores son públicos.");
}

// 4 ── Sources of illusion
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
    ["RQ1", "Persistencia", "¿Los métodos ganadores de la M6 siguen superando al uniforme fuera del periodo de competencia?"],
    ["RQ2", "Evaluación limpia", "Con validación sin fuga de información, ¿algún modelo supera al uniforme en RPS de forma significativa?"],
    ["RQ3", "Pronóstico frente a decisión", "¿Un mejor RPS se traduce en un mejor IR?"],
    ["RQ4", "Cascada de sesgos", "¿Cuánto del desempeño de un procedimiento ingenuo desaparece al corregir cada sesgo?"],
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

  text(s, "Protocolo contra la fuga de información", { x: MX, y: 3.95, w: CW, h: 0.4, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
  const rules = [
    "Todo split es temporal (walk-forward)",
    "Todo estadístico se ajusta solo con el pasado",
    "Quintiles calculados dentro de cada periodo",
    "Purga y embargo si las etiquetas se traslapan",
    "Universo con la información de cada fecha",
    "Costos de transacción, con y sin ellos",
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
  text(s, "Inferencia: comparación pareada contra el uniforme (Diebold y Mariano) con ajuste de Holm por comparaciones múltiples.", {
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
  const labels = ["Equipos en el ranking", "RPS medio mejor que el uniforme", "Significativos sin ajuste", "Significativos tras Holm"];
  const values = [n(v("equipos.n")), n(v("equipos.mejor_media")), n(v("equipos.sig_sin_ajuste")), n(v("equipos.sig_holm"))];
  s.addChart(pres.charts.BAR, [{ name: "Equipos", labels, values }], chartBase({
    x: MX, y: TOP, w: 7.6, h: 4.6, barDir: "bar", catAxisOrientation: "maxMin", chartColors: [HEX.accent1],
    showValue: true, dataLabelPosition: "outEnd", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 60,
    objectName: "Equipos significativos",
  }));
  const x = MX + 8.0, w = CW - 8.0;
  card(s, x, TOP, w, 4.6);
  text(s, "RPS e IR entre equipos", { x: x + 0.3, y: TOP + 0.3, w: w - 0.6, h: 0.45, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
  text(s, v("equipos.spearman"), { x: x + 0.3, y: TOP + 0.85, w: w - 0.6, h: 1.0, fontSize: 60, bold: true, color: C.accent2, fontFace: "Cambria", valign: "bottom" });
  text(s, `Correlación de Spearman entre el RPS y el IR globales. IC 95 %: ${v("equipos.spearman_ic")}; p = ${v("equipos.spearman_p")}.`, {
    x: x + 0.3, y: TOP + 2.0, w: w - 0.6, h: 1.1, fontSize: 15, color: C.accent4,
  });
  text(s, "Pronosticar mejor no se asoció con invertir mejor.", { x: x + 0.3, y: TOP + 3.25, w: w - 0.6, h: 1.0, fontSize: 18, bold: true });
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
    x: MX, y: TOP, w: 7.8, h: 4.3, barDir: "bar", catAxisOrientation: "maxMin", catAxisLabelPos: "low",
    chartColors: MODELS.map(([k]) => (n(v(`${k}.dif_p2`)) < 0 ? HEX.accent1 : HEX.accent2)),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0000", valAxisLabelFormatCode: "0.000",
    barGapWidthPct: 50, objectName: "Diferencia de RPS por modelo",
  }));
  text(s, `Diferencia media de RPS contra el uniforme en ${v("uniforme.n_p2")} periodos (negativa = mejor). RPS del uniforme: ${v("uniforme.rps_p2")}.`, {
    x: MX, y: TOP + 4.35, w: 7.8, h: 0.5, fontSize: 12, color: C.accent4,
  });
  const x = MX + 8.2, w = CW - 8.2;
  stat(s, x, TOP - 0.1, w, v("covsim.rel_p2"), "del RPS del uniforme: la mejora del mejor modelo, la simulación desde covarianzas", C.accent1, 54);
  stat(s, x, TOP + 2.25, w, v("covsim.mejor_p2"), "de los periodos en los que ese modelo supera al uniforme. Pequeña, pero muy regular", C.accent1, 54);
}

// 11 ── Interpretation
{
  const s = contentSlide(
    "La ventaja viene de la volatilidad, no de la dirección",
    "Los seis modelos que superan al uniforme explotan que los activos difieren en volatilidad. Eso anticipa qué activos terminarán en los quintiles extremos, no cuáles subirán, y por eso no contradice la eficiencia de mercado."
  );
  const w = (CW - 2 * 0.4) / 3, h = 4.3;
  const cards = [
    ["Todos explotan la volatilidad", `La simulación desde covarianzas supone que ningún activo rinde más que otro, y aun así es el mejor modelo. Hasta la frecuencia histórica supera al uniforme (${v("baselines.dif_p2")}).`, C.accent1],
    ["La complejidad no ayudó", "El gradient boosting, con nueve variables y búsqueda de hiperparámetros, queda por debajo de un modelo con un solo parámetro.", C.accent6],
    ["El modelo fundacional fue el único peor", `TimesFM-3 aumenta el RPS en ${v("timesfm.dif_p2")} y solo supera al uniforme en el ${v("timesfm.mejor_p2")} de los periodos.`, C.accent2],
  ];
  cards.forEach(([head, body, color], i) => {
    const x = MX + i * (w + 0.4);
    card(s, x, TOP, w, h);
    badge(s, x + 0.3, TOP + 0.3, i + 1, color);
    text(s, head, { x: x + 0.3, y: TOP + 1.15, w: w - 0.6, h: 0.95, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
    text(s, body, { x: x + 0.3, y: TOP + 2.2, w: w - 0.6, h: 1.9, fontSize: 16 });
  });
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
    x: MX, y: TOP, w: 7.6, h: 4.3, barDir: "col", barGrouping: "clustered", catAxisLabelPos: "high",
    chartColors: [HEX.accent5, HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.0000", valAxisLabelFormatCode: "0.0000",
    showLegend: true, legendPos: "b", legendColor: CHART_TEXT.color, legendFontFace: CHART_TEXT.fontFace, legendFontSize: CHART_TEXT.size,
    objectName: "Persistencia por método",
  }));
  text(s, "Diferencia media de RPS contra el uniforme (negativa = mejor).", { x: MX, y: TOP + 4.35, w: 7.6, h: 0.4, fontSize: 12, color: C.accent4 });
  const x = MX + 8.0, w = CW - 8.0;
  text(s, "¿Qué tan fiel es cada método a lo que envió su equipo?", { x, y: TOP, w, h: 0.8, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  const fid = [
    ["FinQBoost", `Validado: correlación de ${v("finqboost.fid_corr")} con sus envíos.`, C.accent1],
    ["wound-ignite", `Validado en parte: ${v("wound_ignite.fid_corr_mes10")} en el décimo envío.`, C.accent3],
    ["AdaGaussMC", `No validado: correlación de ${v("adagaussmc.fid_corr")}.`, C.accent2],
  ];
  fid.forEach(([name, body, color], i) => {
    const y = TOP + 0.95 + i * 1.2;
    card(s, x, y, w, 1.05);
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.4, w: 0.25, h: 0.25, fill: { color }, line: { color, width: 0 }, objectName: oname("Dot") });
    text(s, name, { x: x + 0.7, y: y + 0.12, w: w - 0.9, h: 0.35, fontSize: 16, bold: true });
    text(s, body, { x: x + 0.7, y: y + 0.48, w: w - 0.9, h: 0.5, fontSize: 14, color: C.accent4 });
  });
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
    x: MX, y: TOP, w: 7.6, h: 4.3, barDir: "col", catAxisLabelPos: "low",
    chartColors: irTable.rows.map((r, i) => (i === 0 ? HEX.accent4 : HEX.accent1)),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", barGapWidthPct: 60,
    objectName: "IR neto por portafolio",
  }));
  text(s, "IR agregado del periodo 2, neto de costos de 10 pb sobre la rotación. El IR de la M6 no anualiza.", {
    x: MX, y: TOP + 4.35, w: 7.6, h: 0.4, fontSize: 12, color: C.accent4,
  });
  const x = MX + 8.0, w = CW - 8.0;
  stat(s, x, TOP - 0.1, w, `${better} de ${active}`, "portafolios que se apartan del benchmark superan su IR neto", C.accent2, 54);
  stat(s, x, TOP + 2.25, w, v("inversion.spearman_modelos"), `correlación de Spearman entre RPS e IR neto en ${v("inversion.spearman_modelos_n")} portafolios. IC 95 %: ${v("inversion.spearman_modelos_ic")}`, C.accent2, 54);
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
      x: MX, y: TOP, w: 8.3, h: 4.3, showValue: false, valAxisMinVal: 0, valAxisLabelFormatCode: "0.0",
      showLegend: true, legendPos: "b", legendColor: CHART_TEXT.color, legendFontFace: CHART_TEXT.fontFace, legendFontSize: CHART_TEXT.size,
      catAxisLabelFontSize: 11, objectName: "Sharpe por paso de la cascada",
    })
  );
  text(s, "Sharpe anualizado en el periodo 2. Cada paso agrega una corrección a las anteriores.", { x: MX, y: TOP + 4.35, w: 8.3, h: 0.4, fontSize: 12, color: C.accent4 });
  const x = MX + 8.7, w = CW - 8.7;
  stat(s, x, TOP - 0.1, w, v("cascada.sharpe_s0"), `Sharpe del procedimiento ingenuo: ${v("cascada.veces_bench_s0")} veces el de pesos iguales`, C.accent2, 54);
  stat(s, x, TOP + 2.25, w, v("cascada.sharpe_s6"), `Sharpe con todas las correcciones y costos, por debajo del ${v("cascada.sharpe_bench")} de pesos iguales`, C.accent1, 54);
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
  col(MX, "Inversión", "Sharpe anualizado: ingenuo → limpio", v("cascada.sharpe_s0"), v("cascada.sharpe_s6"), C.accent2,
    `Los sesgos lo inflaron: se pierden ${v("cascada.caida_sharpe")} puntos y queda bajo el ${v("cascada.sharpe_bench")} de pesos iguales.`);
  col(MX + w + 0.4, "Pronóstico", "Diferencia de RPS contra el uniforme: ingenuo → limpio", v("cascada.dif_s0"), v("cascada.dif_s6"), C.accent1,
    "Los sesgos no lo inflaron: el modelo evaluado con honestidad pronostica mejor.");
  text(s, `Con split temporal y purga, pero con las variables ingenuas, la ventaja casi desaparece (${v("cascada.dif_s2")}, p = ${v("cascada.p_s2")}): lo aprendido dependía de haber visto el futuro.`, {
    x: MX, y: TOP + h + 0.3, w: CW, h: 0.9, fontSize: 16, italic: true, color: C.accent4,
  });
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
  const w = (CW - 0.4) / 2, h = 3.9;
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
}

// 18 ── Takeaways and future work
{
  const s = contentSlide(
    "Cuatro preguntas ante el “trading con IA”",
    "Para el inversionista no profesional: un resultado sólido en una métrica de pronóstico no implica una estrategia rentable. Trabajo futuro: repetir la cascada con otros órdenes y modelos, evaluar reglas de inversión basadas en modelos de riesgo y abordar la pregunta sobre atención y rendimientos."
  );
  const qs = [
    "¿El periodo de prueba es posterior a todo lo que el modelo vio?",
    "¿Los activos se eligieron antes o después de conocer su destino?",
    "¿Cuántas variantes se probaron?",
    "¿El resultado descuenta los costos?",
  ];
  const w = (CW - 0.4) / 2, h = 1.15;
  qs.forEach((q, i) => {
    const x = MX + (i % 2) * (w + 0.4), y = TOP + Math.floor(i / 2) * (h + 0.3);
    card(s, x, y, w, h);
    badge(s, x + 0.3, y + 0.275, i + 1, C.accent1);
    text(s, q, { x: x + 1.15, y, w: w - 1.4, h, fontSize: 18, valign: "middle" });
  });
  const y = TOP + 2 * (h + 0.3) + 0.1;
  text(s, "Trabajo futuro", { x: MX, y, w: CW, h: 0.4, fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
  const fw = [
    "Repetir la cascada con otros órdenes y otros modelos.",
    "Evaluar reglas de inversión basadas en modelos de riesgo.",
    "Estudiar la relación entre atención y rendimientos (RQ5).",
  ];
  text(s, fw.map((b, i) => ({ text: b, options: { bullet: true, breakLine: i < fw.length - 1, paraSpaceAfter: 4 } })), {
    x: MX, y: y + 0.5, w: CW, h: 1.1, fontSize: 16,
  });
}

// ------------------------------------------------------------------------ write

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log(`Wrote ${path.relative(ROOT, OUT)}`);
})();
