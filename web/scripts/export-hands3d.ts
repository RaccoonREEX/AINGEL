/*
 * Exports AINGEL's three.js hand poses and the converted catalogue signs (hands3d/convert.ts) as JSON for the
 * native Android renderer (Hands3D.kt), so web and Android sign exactly the same data.
 * Run: npm run export:android-hands  →  android/app/src/main/assets/hands3d/signs3d.json
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { S } from "../src/components/aingel/signData";
import { ensureSign } from "../src/components/aingel/hands3d/convert";
// @ts-expect-error untyped engine module from the AINGEL hands package
import { library } from "../src/components/aingel/hands3d/library.js";
// @ts-expect-error untyped engine module from the AINGEL hands package
import { DIM, HAND_SCALE } from "../src/components/aingel/hands3d/handRig.js";
import listenEar from "../src/components/aingel/hands3d/listen_ear.json";

Object.keys(S).forEach((id) => ensureSign(id));

// Interface gesture «escuchando» (hands next to the ears) from AINGEL_Inicio_y_Ajustes v1.0.0, used while AINGEL
// learns the wake phrase. Not an LSEC sign. Inline fingers become a pose and the mirrored left hand is written out.
type HandKf = { pose?: string; fingers?: unknown; position?: number[]; rotation?: number[] };
const ear = listenEar as { id: string; keyframes: { t: number; ease?: string; right: HandKf; left: HandKf | "mirror" }[] };
library.registerSign({
  id: ear.id,
  keyframes: ear.keyframes.map((kf, i) => {
    const right: HandKf = { ...kf.right };
    if (right.fingers) { library.registerPose({ id: ear.id + "_" + i, fingers: right.fingers }); right.pose = ear.id + "_" + i; delete right.fingers; }
    const left = kf.left === "mirror" ? { ...right, position: right.position && [-right.position[0], right.position[1], right.position[2]] } : kf.left;
    return { t: kf.t, ease: kf.ease, right, left };
  }),
});
const out = {
  source: "AINGEL_Manos_y_Senas v1.0.0 · signs catalogue v1.5.0 converted by web/src/components/aingel/hands3d/convert.ts",
  status: "AINGEL design, pending LSEC validation",
  handScale: HAND_SCALE,
  dim: DIM,
  rest: library.rest,
  poses: Object.fromEntries([...library.poses].map(([id, p]: [string, { fingers: unknown }]) => [id, p.fingers])),
  signs: Object.fromEntries([...library.signs].map(([id, s]: [string, { keyframes: unknown }]) => [id, s.keyframes])),
};
const dir = new URL("../../android/app/src/main/assets/hands3d/", import.meta.url);
mkdirSync(dir, { recursive: true });
writeFileSync(new URL("signs3d.json", dir), JSON.stringify(out));
console.log(`signs3d.json: ${Object.keys(out.signs).length} signs, ${Object.keys(out.poses).length} poses`);
