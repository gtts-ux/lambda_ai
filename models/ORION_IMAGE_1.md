# orion image 1

Experimental local reference-guided image generation, published at the owner's
request after review of its actual imperfect outputs. Native output: **256 × 256**.

The 1,436,677 parameters consist of an own foreground mask head, own scene flow
and own learned 256px pixel decoder/spatial transform. All neural parameters
originate from this project's random initializations. No external pretrained AI
or hosted image generation. The NPZ contains inference tensors and metadata only.

Requires core **0.9.0** / Desktop **1.2.0**. Download individually in Settings →
Models, then open **Image Playground**. Terra has an additional own learned
image-request classifier in the application; existing conversation weights are
not replaced or renamed. Some requests are missed; explicit Playground is available.

Searches NASA and Wikimedia Commons reference photos and generates locally.
Reference credits/source links are retained locally. It does not fuse all
retrieved photos into a new 3-D model.

## Actual limitations

The reviewed Saturn V example selects a real flying rocket and star field, but
its foreground mask follows much of the exhaust plume and the generated rocket
is indistinct. Cup/vase/broccoli scenes preserve backgrounds better than object
geometry. Objects can be blurred, distorted or unrecognizable. This is not a
proven photorealistic or general text-to-image model.

The 5.29-hour continuation used 4604 human-masked COCO instances across 80 category
labels, 500 authored rocket training examples and 432 NASA photos. Composition
labels are artificial 2-D arrangements; originals were split before cropping.
On the small final artificial-scene test, whole-image L1 was 0.09693 versus
0.12827 for coarse enlargement. Foreground/background L1: 0.29239/0.06178.
These are pixel errors, **not semantic or perceptual quality scores**. The owner
example is an exposed regression, not an unseen test.

Sources: [COCO](https://cocodataset.org/),
[NASA media policies](https://www.nasa.gov/nasa-brand-center/images-and-media/),
[Commons](https://commons.wikimedia.org/), [flow matching](https://arxiv.org/abs/2210.02747).
Original attribution/license records remain in the private experiment. No photos,
annotations, training scripts or optimizer are distributed in the model release.
Original photos have their own terms; repository MIT licensing covers application
code and does not relicense source photography.

Artifact: orion-image-1-r1.npz, 5,365,641 bytes.
SHA-256: 1756742c2d2a0978b8ac1ffed768cac5fa04de96d5b2c4709f11633bf3181530.
Inspected NumPy/Torch maximum errors: mask logits 0.000163; flow/detail <0.000005.
