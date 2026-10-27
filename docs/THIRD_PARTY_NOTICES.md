# Third-party components — local prototype inventory

The application currently uses Django, Django REST Framework, Pillow, httpx, Channels/Daphne, websockets, cryptography, PyOTP, qrcode, OpenCV, NumPy, React, Vite and TypeScript, with exact resolved dependencies in the Python and npm lockfiles. Preserve their bundled licenses/notices when packaging a distributable; this inventory is not a completed transitive-license audit.

Additional assets/material:

- Meta SAM parser: **SAM License**; copied from the installed package to `licenses/meta_sam_parser.txt`. Do not label it MIT.
- YuNet model: MIT license, copied to `licenses/face_detection_yunet.txt`.
- SFace model: Apache-2.0 license from OpenCV Zoo model directory, copied to `licenses/face_recognition_sface.txt`. Pinned source and weight hashes: `FACE_MODELS.json`. Upstream training provenance and downstream biometric deployment conditions are not fully audited.
- VizWiz VQA annotations: CC BY 4.0 according to the official task page. Attribution, source and archive hash in `DATASET_MANIFEST.json`. Thirty annotations remain in ignored local evaluation storage; no corpus images or training dataset are bundled in this repository.

Project source license selection and a complete transitive inventory must be finalized before public hackathon repository publication. Nothing in this file grants rights to private family photos or consent for biometric enrollment.
