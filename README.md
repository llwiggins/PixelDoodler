# PixelDoodler

PixelDoodler is an interactive, pixel-wise annotation tool built for deep learning workflows. It lets you load image files or NumPy arrays, paint class labels directly on the data, and export label masks that can be fed into segmentation or other pixel-based machine-learning models.

## Installation

First create and activate a Python environment (e.g., using Conda). For example:

```bash
conda create -n PixelDoodler python=3.11
conda activate PixelDoodler
```

With [Git installed] on your machine, install the PixelDoodler package from GitHub using [pip][pip].

    pip install git+https://github.com/llwiggins/PixelDoodler.git@main

You can then use the tool by running
```bash
pixeldoodler
```

