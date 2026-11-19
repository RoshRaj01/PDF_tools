# PDF Privacy Cleaner

A Streamlit-based web application to clean sensitive metadata, annotations, and embedded attachments from PDF files.

## Features

- **Metadata Removal**: Strip standard PDF metadata and XML/XMP metadata.
- **Annotation & Attachment Cleaning**: Remove comments, markups, and embedded files.
- **User-Friendly Interface**: Built with Streamlit for quick and simple operation.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/RoshRaj01/PDF_tools.git
   cd PDF_tools
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the Streamlit application:
```bash
streamlit run app.py
```
