# Gel Mask R-CNN App

A Flask web application for visualizing gel electrophoresis image segmentation using Mask R-CNN (NEXTFLOW).
See: https://github.com/moonc/Nextflow-MASKRCNN-GEL

## Features

- Upload gel electrophoresis images
- Run instance segmentation using a pre-trained or custom Mask R-CNN model
- View and download overlayed segmentation results

## Requirements

- Python 3.10
- Conda 
- PyTorch and Torchvision
- Flask
- Nextflow-MASKRCNN-GEL Repository

## Setup with Conda

### 1. Clone the Repositories

```bash
git clone https://github.com/moonc/gel_maskrcnn_app.git
cd gel_maskrcnn_app
```
```bash
git clone https://github.com/moonc/Nextflow-MASKRCNN-GEL.git
```


### 2. Create Conda Environment

```bash
conda create -n gel-maskrcnn python=3.10 -y
conda activate gel-maskrcnn
```

### 3. Install Dependencies

```bash
# Install PyTorch with CPU support (or use CUDA if preferred)
conda install pytorch torchvision torchaudio cpuonly -c pytorch -y

# Scientific stack and Flask
conda install -c conda-forge numpy flask pillow -y

# Pip-only dependencies
pip install -r requirements.txt
```

## Model Weights

The model expects weights to be placed at:

```
model_weights/maskrcnn.pth
```

This file must be provided manually.

### Option: Use Pretrained COCO Model

To use a pretrained COCO model instead, modify `app.py`:

Replace:
```python
model.load_state_dict(torch.load('model_weights/maskrcnn.pth'))
```
With:
```python
model = torchvision.models.detection.maskrcnn_resnet50_fpn(pretrained=True)
```

## Running the App

```bash
python app.py
```

Then open your browser to:

```
http://127.0.0.1:5000
```

## Optional: Run with Docker

```bash
docker build -t gel_maskrcnn_app .
docker run -p 5000:5000 gel_maskrcnn_app
```

Ensure that `maskrcnn.pth` is in the correct location before building the image.

## Project Structure

```
.
├── app.py                   # Flask entrypoint
├── templates/
│   └── index.html           # Frontend
├── static/
│   └── ...                  # Uploaded images and overlays
├── model_weights/
│   └── maskrcnn.pth         # Model checkpoint
└── requirements.txt         # Python dependencies
```

