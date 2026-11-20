# orion 1.2

An optional own-weight image model for Image Playground. Core app 0.11.0 /
Desktop 1.4.0 or newer is required. Download it individually in Settings → Models,
then choose **Orion 1.2** in Image Playground. Orion Image 1 remains available.

The complete description is searched with strict Safe Search. Up to ten reference
photos are recorded; the first usable scene reference conditions this model. It
does not combine ten camera views into a novel 3-D object. The own local flow and
learned pixel decoder produce a native 256 × 256 RGB image. Full-frame conditioning
avoids the old forced foreground crop and destructive object-mask selection.
No pretrained image/text encoder, external AI weights or hosted image AI is used.

The inference archive contains exactly the selected own mask, flow and detail
tensors: **1,436,677 learned parameters**. The mask is retained for architecture
compatibility and is unused in full-frame mode. Selected flow update 12000 and
detail update 11500 follow the owner's previous composition model. The bounded
continuation took about 6.47 hours on CPU. Training data/code/optimizer/user chats
are not distributed with the artifact.

Training used 5432 whole COCO/NASA photos, real COCO captions and NASA query labels,
with original-photo splits (4312 training / 563 development / 557 final), category
balancing and separate artificial 2-D composition replay. Final selection was
checked on 24 final-split photos: reference-reconstruction L1 0.0361 versus 0.3460
for the source weights in the same full-frame inference mode; PSNR 29.92 versus
12.41 dB. Edge and separate car/person guards passed. These compare reconstruction
fidelity, not semantic prompt accuracy or a general image-generation benchmark.
The two exposed owner examples were inspected separately and were not training
targets or unseen test cases.

**Limits:** This is reference-guided reconstruction/variation. Outputs can closely
resemble the selected online photograph. Accurate new viewpoints, original complex
scenes, exact counts and general language understanding are not established.
Details can blur or distort. A faithful rendering of a poorly matched reference
can still fail the prompt. Safe Search is enabled, but filtering is not perfect.
Source credits and links remain attached to saved images; consult original terms.
512/1024 exports enlarge the native 256 image and do not add newly learned detail.

Price remains 1000 tokens per Unicode prompt word per image at 256, ×2 at 512 or
×4 at 1024, multiplied by count. Only completed saved images are charged. The shared
allowance, chat models, previous images and chats remain compatible.

Artifact: `orion-1.2-r1.npz`, 5,365,715 bytes.

SHA256: `045482c0f5a814561cb049058f2ceb98c65ad9cdd8791cc291e8f99edf39a217`

Selected private checkpoint SHA256:
`4876d40da3550e2dff56750b2b1ebcb32f99997d4507902cf240806ede4c8655`.
