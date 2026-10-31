# Third-party notices

AINGEL is the work of its own authors. This file preserves the notices of third-party components it
uses or adapts. Declared licences of every npm, Android and Python dependency are listed in
[`docs/THIRD_PARTY_INVENTORY.md`](docs/THIRD_PARTY_INVENTORY.md); models, datasets and services in
[`docs/THIRD_PARTY_NOTICES.md`](docs/THIRD_PARTY_NOTICES.md). Full licence texts are in
[`docs/licenses/`](docs/licenses/). Readiness review: [`docs/PUBLICATION_READINESS.md`](docs/PUBLICATION_READINESS.md).
This is not a completed legal audit.

What is distributed to end users (reviewed 2026-10-30):

- Web bundle (browser): React, ReactDOM, scheduler, three.js, AINGEL code (incl. the AingelOrb renderer).
  Montserrat is fetched from Google Fonts, not bundled.
- Android APK: AndroidX / Jetpack Compose / CameraX, Kotlin stdlib, kotlinx-coroutines,
  kotlinx-serialization-core, OkHttp, Okio and the other Apache-2.0 artefacts listed in the inventory;
  libyuv (BSD-3-Clause) inside CameraX `camera-core`; Public Suffix List data (MPL-2.0) inside OkHttp;
  Montserrat font files (OFL-1.1); AINGEL code and assets. The APK copy of this notice is
  `android/app/src/main/assets/licenses/THIRD_PARTY_NOTICES.md`.
- Server only (not distributed unless a container image is published): Python packages, Meta SAM parser,
  YuNet/SFace weights (downloaded at setup, never committed), MedlinePlus index, sign clip catalogue.

-----------------------------------------------------------
Thinking Orbs
-----------------------------------------------------------

Project:
Thinking Orbs

Official website:
https://www.thinkingorbs.com/

Source repository:
https://github.com/yogesharc/thinking-orbs

Copyright (c) 2026 Yogesh

Licensed under the MIT License.

This project uses and/or adapts portions of Thinking Orbs.
The original copyright and license notice are preserved below.

MIT License

Copyright (c) 2026 Yogesh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

-----------------------------------------------------------

Where it is used:

- Web (`web/src/components/aingel/`) and Android (`android/app/src/main/java/ec/aingel/mobile/AingelOrb.kt`)
  contain the AingelOrb renderer from the AINGEL UI package v1.1.1 (Fibonacci dot sphere, face, eyes,
  orbits, audio-reactive layer). It follows the Thinking Orbs integration brief and state model; the
  notice above is kept with the web distribution in `web/public/THIRD_PARTY_NOTICES.txt`.

-----------------------------------------------------------
three.js 0.184.0
-----------------------------------------------------------

Project: three.js — https://threejs.org/ · https://github.com/mrdoob/three.js
Installed from npm (`three@0.184.0`) and bundled into the web chunk `hands3d-*.js`, where the `@license`
header is kept. The Android app does not include three.js: it draws the same hands with its own OpenGL
port (`Hands3D.kt`).

Where it is used: the articulated 3D hands of the sign translator (engine of the *AINGEL Manos y Señas*
package, `web/src/components/aingel/hands3d/`). No external 3D models are used: the hand geometry is
generated in code.

The MIT License

Copyright © 2010-2026 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

-----------------------------------------------------------
React 19.3.1, ReactDOM 19.3.1 and scheduler 0.28.0 (web bundle)
-----------------------------------------------------------

Project: React — https://react.dev/ · https://github.com/facebook/react
Installed from npm and bundled into the web build. Licence: MIT (same text for react, react-dom and
scheduler). Copy: `docs/licenses/React_MIT.txt`.

MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

-----------------------------------------------------------
Android libraries under the Apache License 2.0 (APK)
-----------------------------------------------------------

AndroidX (activity, annotation, appcompat, arch-core, autofill, collection, concurrent-futures, core,
cursoradapter, customview, drawerlayout, emoji2, exifinterface, fragment, graphics-path, interpolator,
lifecycle incl. lifecycle-service, loader, profileinstaller, savedstate, startup, tracing,
vectordrawable, versionedparcelable, viewpager), Jetpack Compose (runtime, ui, foundation, animation,
material3, material-ripple, material-icons-core), CameraX 1.4.2 (camera2, core, lifecycle, video, view)
— Copyright The Android Open Source Project.
Kotlin stdlib 2.2.20 / jdk7 / jdk8, kotlinx-coroutines 1.10.2, kotlinx-serialization-core 1.7.3,
JetBrains annotations 23.0.0 — Copyright JetBrains s.r.o. and Kotlin Programming Language contributors.
OkHttp 4.12.0 and Okio 3.6.0 — Copyright Square, Inc.
Guava listenablefuture 1.0, AutoValue annotations 1.6.3 — Copyright Google LLC.
JSpecify 1.0.0 — Copyright The JSpecify Authors.

All 120 artefacts of the release runtime classpath (exact list and versions in
`docs/THIRD_PARTY_INVENTORY.md`) declare the Apache License, Version 2.0 in their official Maven POMs
(checked 2026-10-30). Licensed under the Apache License, Version 2.0 (the "License"); you may not use
these files except in compliance with the License. You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0 — full text: `docs/licenses/Apache-2.0.txt`. Unless required by
applicable law or agreed to in writing, software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND. No NOTICE file was found inside these
jars/AARs, other than the OkHttp Public Suffix notice below.

-----------------------------------------------------------
libyuv (inside CameraX camera-core native libraries, APK)
-----------------------------------------------------------

`androidx.camera:camera-core:1.4.2` declares, besides Apache-2.0, the BSD licence of libyuv
(https://chromium.googlesource.com/libyuv/libyuv) for its bundled native code. Full text:
`docs/licenses/libyuv_BSD-3-Clause.txt`.

Copyright 2011 The LibYuv Project Authors. All rights reserved.
Licensed under the BSD 3-Clause licence (see the file above for conditions and disclaimer).

-----------------------------------------------------------
Public Suffix List (inside OkHttp, APK)
-----------------------------------------------------------

OkHttp 4.12.0 bundles `okhttp3/internal/publicsuffix/publicsuffixes.gz`, compiled from the Public Suffix
List (https://publicsuffix.org/list/public_suffix_list.dat). It is subject to the terms of the Mozilla
Public License, v. 2.0 (https://mozilla.org/MPL/2.0/). The file is distributed unmodified; its Source Code
Form is available at the URL above and in the OkHttp source (https://github.com/square/okhttp).
Full text: `docs/licenses/MPL-2.0.txt`.

-----------------------------------------------------------
Montserrat
-----------------------------------------------------------

Montserrat typeface, loaded from Google Fonts on the web and bundled in `android/app/src/main/res/font/`.
Copyright 2011 The Montserrat Project Authors (https://github.com/JulietaUla/Montserrat).
Licensed under the SIL Open Font License, Version 1.1. Full text: `docs/licenses/Montserrat_OFL.txt`
(also shipped in the APK as `assets/licenses/Montserrat_OFL.txt`).

-----------------------------------------------------------
MedlinePlus
-----------------------------------------------------------

Health topic summaries from MedlinePlus, U.S. National Library of Medicine (https://medlineplus.gov).
The summaries are in the public domain in the United States; images, A.D.A.M. encyclopedia and other
third-party material on MedlinePlus are not used. Attribution shown in the app: "MedlinePlus,
National Library of Medicine". AINGEL retrieves these texts for a question; no model was trained on them.

-----------------------------------------------------------
Server-side components (not shipped to browsers or the APK)
-----------------------------------------------------------

- YuNet face detector (`face_detection_yunet_2023mar.onnx`, OpenCV Zoo commit 48b10fa5): MIT,
  Copyright (c) 2020 Shiqi Yu. Text: `docs/licenses/face_detection_yunet.txt`.
- SFace face recogniser (`face_recognition_sface_2021dec.onnx`, same commit): Apache-2.0 per the OpenCV Zoo
  model directory LICENSE. Text: `docs/licenses/face_recognition_sface.txt`.
  Both weights are downloaded by `backend/scripts/setup_face_models.py` into `.local/face-models/`
  (ignored by Git, mounted read-only in containers); they are not in the repository or the images.
- Meta SAM parser (`meta-sam-parser` 0.1.0, pip): SAM License (Meta), not an OSI licence. Anyone who
  redistributes it must include the agreement: `docs/licenses/meta_sam_parser.txt`.
- Python packages (Django, DRF, Channels/Daphne, httpx, Pillow, OpenCV, NumPy, cryptography, psycopg,
  redis-py, etc.): licences in `docs/THIRD_PARTY_INVENTORY.md`. If a backend container image is ever
  published, their notices must travel with it; psycopg / psycopg-binary are LGPL-3.0 and certifi is
  MPL-2.0.
- Meta Model API (Muse Spark, SAM 3.1, Voice Transcribe): remote service under Meta's terms; no model
  weights are distributed.
