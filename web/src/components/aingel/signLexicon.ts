/*
 * Vocabulary and sentence rule of the AINGEL signs catalogue v1.5.0 (AINGEL_Manos_y_Senas v1.0.0).
 * The signs are an AINGEL DESIGN pending validation by Deaf LSEC signers. The sentence rule is a simple
 * one (time first, question mark last, unknown words fingerspelled, articles dropped), NOT LSEC grammar.
 */

/** Sign ids understood by AingelSigner: words, actions, letters a..z and ñ, numbers n0..n10. */
export type SignId = string;

const WORDS: [SignId, string, string][] = [
  ["yo", "yo", "I"], ["tu", "tú", "you"], ["hola", "hola", "hello"], ["gracias", "gracias", "thank you"], ["porfavor", "por favor", "please"],
  ["si", "sí", "yes"], ["no", "no", "no"], ["bien", "bien", "good"], ["mal", "mal", "bad"], ["agua", "agua", "water"], ["comida", "comida", "food"],
  ["medicina", "medicina", "medicine"], ["casa", "casa", "home"], ["parque", "parque", "park"], ["pelota", "pelota", "ball"], ["libro", "libro", "book"],
  ["bano", "baño", "bathroom"], ["doctor", "doctor", "doctor"], ["familia", "familia", "family"], ["mama", "mamá", "mum"], ["papa", "papá", "dad"],
  ["hija", "hija", "daughter"], ["hijo", "hijo", "son"], ["dolor", "dolor", "pain"], ["ayuda", "ayuda", "help"], ["hoy", "hoy", "today"],
  ["manana", "mañana", "tomorrow"], ["ayer", "ayer", "yesterday"], ["pregunta", "¿pregunta?", "question?"],
  ["caminar", "caminar", "walk"], ["leer", "leer", "read"], ["comer", "comer", "eat"], ["beber", "beber", "drink"], ["dormir", "dormir", "sleep"],
  ["esperar", "esperar", "wait"], ["ir", "ir", "go"], ["venir", "venir", "come"], ["llamar", "llamar", "call"], ["ayudar", "ayudar", "help"],
  ["necesitar", "necesitar", "need"], ["querer", "querer", "want"], ["tener", "tener", "have"], ["jugar", "jugar", "play"],
];
const NAME: Record<SignId, [string, string]> = {};
WORDS.forEach(([id, es, en]) => { NAME[id] = [es, en]; });
"abcdefghijklmnñopqrstuvwxyz".split("").forEach((c) => { NAME[c] = [c.toUpperCase(), c.toUpperCase()]; });
for (let i = 0; i <= 10; i++) NAME["n" + i] = [String(i), String(i)];

export const signName = (id: SignId, spanish: boolean) => (NAME[id] ? NAME[id][spanish ? 0 : 1] : id);

const LEX: Record<string, SignId | null> = {};
const add = (id: SignId, ws: string) => ws.split(" ").forEach((w) => { LEX[w] = id; });
add("yo", "yo me mi mis conmigo i me my"); add("tu", "tu tus te ti usted ustedes vos contigo you your");
add("hola", "hola buenos buenas saludos hello hi"); add("gracias", "gracias agradezco thanks thank"); add("si", "si claro vale yes ok"); add("no", "no nunca nada never");
add("bien", "bien bueno buena feliz contento contenta tranquilo tranquila good fine well happy"); add("mal", "mal malo mala enfermo enferma triste bad sick sad");
add("agua", "agua water"); add("comida", "comida almuerzo desayuno cena merienda food lunch breakfast dinner");
add("medicina", "medicina medicinas medicamento medicamentos pastilla pastillas remedio remedios medicine medicines pill pills");
add("casa", "casa hogar home house"); add("parque", "parque parques park"); add("pelota", "pelota balon ball"); add("libro", "libro libros cuento book books"); add("bano", "bano bathroom toilet");
add("doctor", "doctor doctora medico medica hospital"); add("familia", "familia family"); add("mama", "mama madre mami mum mom mother"); add("papa", "papa padre papi dad father");
add("hija", "hija hijas nieta daughter granddaughter"); add("hijo", "hijo hijos nieto son grandson"); add("dolor", "dolor duele duelen dolores pain hurts"); add("ayuda", "ayuda auxilio socorro help");
add("hoy", "hoy ahora today now"); add("manana", "manana tomorrow"); add("ayer", "ayer yesterday");
add("caminar", "caminar camino caminas camina caminamos camine caminare caminaremos pasear paseo walk walked"); add("leer", "leer leo lees lee lei leyo leere leyendo leemos read reading");
add("comer", "comer como comes come comemos comi comere hambre eat hungry"); add("beber", "beber bebo bebes bebe tomar tomo tomas toma sed drink thirsty");
add("dormir", "dormir duermo duermes duerme dormi dormire sueno descansar descanso sleep tired"); add("esperar", "esperar espero esperas espera espere esperame wait");
add("ir", "ir voy vas va vamos van fui iremos ire go going"); add("venir", "venir vengo vienes viene vienen ven vino vendra come coming");
add("llamar", "llamar llama llamo llamas llame llamame telefono call phone"); add("ayudar", "ayudar ayudo ayudas ayudame ayudeme ayude");
add("necesitar", "necesitar necesito necesitas necesita necesitamos need"); add("querer", "querer quiero quieres quiere queremos quisiera want");
add("tener", "tener tengo tienes tiene tenemos have"); add("jugar", "jugar juego juegas juega jugamos jugue play");
["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez"].forEach((w, i) => { LEX[w] = "n" + i; LEX[String(i)] = "n" + i; });
LEX.una = null;
const STOP = new Set("el la los las un una unos unas de del al a en con y o que por para es esta estas estoy estan son era fue muy lo le les se su sus este ese eso esto ya tambien pero como cual donde cuando quien cuanto mas the an to of and or is are am was in on at with for it".split(" "));
const QW = new Set("que como donde cuando quien cual cuanto what how where when who which why".split(" "));

const norm = (w: string) => w.toLowerCase().replace(/ñ/g, "\u0001").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\u0001/g, "ñ");
export const spellSeq = (txt: string): SignId[] => norm(txt || "").split("").filter((c) => /[a-zñ]/.test(c)).slice(0, 16);

export type WordKind = "sign" | "spell" | "skip";
export type Built = { seq: SignId[]; words: { t: string; k: WordKind }[] };

/** Catalogue rule: time (today/yesterday/tomorrow) first, question last, unknown words fingerspelled. */
/** What follows «cómo» / «how» in «¿cómo estás?» and its variants: asked to you, or to someone else (or «usted»). */
const HOW_YOU = ["estas", "te va", "te sientes", "te encuentras", "has estado", "andas", "sigues", "amaneciste", "are you"].map((p) => p.split(" "));
const HOW_THEY = ["esta", "estan", "le va", "les va", "se siente", "se sienten", "se encuentra", "ha estado", "anda", "sigue", "amanecio", "is", "are"].map((p) => p.split(" "));
const startsWith = (after: string[], p: string[]) => p.every((x, k) => after[k] === x);

export function buildSentence(txt: string): Built | null {
  const raw = (txt || "").trim();
  if (!raw) return null;
  const first = raw.split(/\s+/)[0].replace(/[¿¡]/g, ""), firstW = norm(first).replace(/[!?.,;:]/g, "");
  // A plain opening «Como» is «I eat» («Como arroz»); it asks only when accented or the text has «?».
  const eatFirst = firstW === "como" && !/ó/i.test(first);
  let isQ = /\?/.test(raw) || (QW.has(firstW) && !eatFirst);
  const toks = raw.replace(/[¿¡!?.,;:]/g, " ").split(/\s+/).filter(Boolean);
  const words: Built["words"] = [], time: SignId[][] = [], main: SignId[][] = [], tail: SignId[][] = [];
  for (let i = 0; i < toks.length; i++) {
    const w = norm(toks[i]).replace(/ñ/g, "n"), nx = toks[i + 1] ? norm(toks[i + 1]).replace(/ñ/g, "n") : "";
    const after = toks.slice(i + 1).map((t) => norm(t).replace(/ñ/g, "n"));
    const how = w === "como" || w === "how";
    const toYou = how ? HOW_YOU.find((p) => startsWith(after, p)) : undefined;
    const toThem = how && !toYou ? HOW_THEY.find((p) => startsWith(after, p)) : undefined;
    // «¿Cómo estás?» → TÚ BIEN ? ; «¿Cómo está tu mamá?» → TÚ MAMÁ BIEN ? (not «comer»: 29-10-2026).
    if (toYou || toThem) {
      const n = (toYou || toThem)!.length;
      words.push({ t: toks.slice(i, i + 1 + n).join(" "), k: "sign" });
      if (toYou || toks.length === i + 1 + n) main.push(["tu"]);
      tail.push(["bien"]); isQ = true; i += n; continue;
    }
    // «Cómo» asking (accented, or opening a question) is the question word, not «I eat».
    if (w === "como" && (/ó/i.test(toks[i]) || (i === 0 && isQ))) { words.push({ t: toks[i], k: "skip" }); continue; }
    // Opening «Como …» without a subject is first person: YO COMER …
    if (w === "como" && i === 0) { words.push({ t: toks[i], k: "sign" }); main.push(["yo"], ["comer"]); continue; }
    if (w === "por" && nx === "favor") { words.push({ t: toks[i] + " " + toks[i + 1], k: "sign" }); main.push(["porfavor"]); i++; continue; }
    if ((w === "me" && nx === "llamo") || (w === "mi" && nx === "nombre") || (w === "my" && nx === "name")) {
      let j = i + 2;
      if (["es", "is"].includes(norm(toks[j] || ""))) j++;
      words.push({ t: toks.slice(i, j).join(" "), k: "sign" }); main.push(["yo"]);
      if (toks[j]) { words.push({ t: toks[j], k: "spell" }); main.push(spellSeq(toks[j])); }
      i = j; continue;
    }
    const id = LEX[w];
    if (id) { words.push({ t: toks[i], k: "sign" }); (id === "hoy" || id === "manana" || id === "ayer" ? time : main).push([id]); continue; }
    if (STOP.has(w) || QW.has(w)) { words.push({ t: toks[i], k: "skip" }); continue; }
    const sp = spellSeq(toks[i]).slice(0, 10);
    if (sp.length) { words.push({ t: toks[i], k: "spell" }); main.push(sp); } else words.push({ t: toks[i], k: "skip" });
  }
  let seq = ([] as SignId[]).concat(...time, ...main, ...tail);
  seq = seq.filter((s, i) => i === 0 || s !== seq[i - 1] || s.length === 1);
  if (isQ) seq.push("pregunta");
  return seq.length ? { seq: seq.slice(0, 40), words } : null;
}

const ci = (x: number, y: number, r: number) => `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
const HAND = "M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5M14 10.5V5.5a1.5 1.5 0 0 1 3 0V13c0 4-2.5 7-6.5 7S5 17.5 4.5 15l-1-3a1.4 1.4 0 0 1 2.5-1.2L8 13";

/** Signs Meta may use when it signs a sentence by meaning (backend assistance.gloss): words and numbers. */
export const GLOSS_VOCABULARY: Record<SignId, string> = Object.fromEntries([
  ...WORDS.map(([id, es, en]) => [id, es === en ? es : `${es} / ${en}`]),
  ...Array.from({ length: 11 }, (_, i) => [`n${i}`, String(i)]),
]);

/** Meta's gloss as the hands' sequence (fingerspelled words become letters), or null if any item is unusable. */
export function glossSeq(gloss: unknown): SignId[] | null {
  if (!Array.isArray(gloss) || !gloss.length) return null;
  const seq: SignId[] = [];
  for (const item of gloss) {
    const sign = item && typeof item.sign === "string" ? item.sign : "", spell = item && typeof item.spell === "string" ? item.spell : "";
    if (sign && sign in GLOSS_VOCABULARY) seq.push(sign);
    else if (spell && spellSeq(spell).length) seq.push(...spellSeq(spell));
    else return null;
  }
  return seq.slice(0, 40);
}

/** Board for signs → voice / text: the catalogue words most useful in daily care. */
export const BOARD: SignId[] = ["hola", "gracias", "porfavor", "si", "no", "yo", "tu", "bien", "mal", "dolor", "agua", "comer", "medicina", "bano", "ayuda", "doctor", "familia", "casa", "dormir", "pregunta"];

/** 24×24 stroke pictograms for the board (same line style as the catalogue's). */
export const PICTOGRAM: Record<SignId, string> = {
  hola: HAND + "M19.5 3.5c1.3.9 2 2.2 2 3.8M3 3.5c-.5 1.2-.4 2.4.3 3.4",
  gracias: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  porfavor: "M5 12.5c2.2-.2 3.5 1 4.5 2.5M5 12.5V7a1.4 1.4 0 0 1 2.8 0v4.5M19 12.5c-2.2-.2-3.5 1-4.5 2.5M19 12.5V7a1.4 1.4 0 0 0-2.8 0v4.5M9.5 15l2.5 5 2.5-5",
  si: ci(12, 12, 8.5) + "M8 12.3l2.7 2.7 5.5-5.5",
  no: ci(12, 12, 8.5) + "M9 9l6 6M15 9l-6 6",
  yo: ci(12, 7, 3.2) + "M5.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M12 14.5v3",
  tu: ci(12, 7, 3.2) + "M5.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5",
  bien: "M7 11v8H4v-8zM7 11l3.5-6.5a1.8 1.8 0 0 1 3.3 1.3L13 10h5a2 2 0 0 1 2 2.3l-1 5.4a2 2 0 0 1-2 1.6H7",
  mal: "M7 13V5H4v8zM7 13l3.5 6.5a1.8 1.8 0 0 0 3.3-1.3L13 14h5a2 2 0 0 0 2-2.3l-1-5.4a2 2 0 0 0-2-1.6H7",
  dolor: "M13 2.5L6 13.5h5.5L10 21.5l8-11.5h-5.5z",
  agua: "M6 4h12l-1.5 15.5a1.5 1.5 0 0 1-1.5 1.4H9a1.5 1.5 0 0 1-1.5-1.4zM7 10h10",
  comer: ci(14, 12, 6.5) + ci(14, 12, 3) + "M4.5 4v16M3 4v4a1.5 1.5 0 0 0 3 0V4",
  medicina: "M7.05 16.95a3.5 3.5 0 0 1 0-4.95l5-5a3.5 3.5 0 0 1 4.95 4.95l-5 5a3.5 3.5 0 0 1-4.95 0zM9.5 9.5l5 5",
  bano: "M4 11h16v2a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6zM6 11V5.5A2.5 2.5 0 0 1 10.5 4M9 19l-1 2M15 19l1 2",
  ayuda: ci(12, 12, 8.5) + ci(12, 12, 3.5) + "M6 6l3.5 3.5M14.5 14.5L18 18M18 6l-3.5 3.5M9.5 14.5L6 18",
  doctor: "M5 4v5a4 4 0 0 0 8 0V4M9 13v2a5 5 0 0 0 10 0v-2" + ci(19, 11, 2),
  familia: ci(8, 7, 2.6) + ci(16, 7, 2.6) + "M3 19c.5-3.2 2.4-5 5-5s4.5 1.8 5 5M11 19c.5-3.2 2.4-5 5-5s4.5 1.8 5 5",
  casa: "M4 11l8-6.5 8 6.5M6 9.5V20h12V9.5M10 20v-5h4v5",
  dormir: "M19 14.5A7.5 7.5 0 1 1 9.5 5a6 6 0 0 0 9.5 9.5z",
  pregunta: "M9 9a3 3 0 1 1 4.2 2.8c-.8.4-1.2 1-1.2 1.9V15M12 18.6v.2",
};
