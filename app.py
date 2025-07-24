from flask import Flask, request, render_template, send_file
import fitz
from PIL import Image, ImageOps
import io
import os
import zipfile
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def invert_pdf_colors(input_path, output_path):
    doc = fitz.open(input_path)
    new_doc = fitz.open()
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        inverted = ImageOps.invert(img)

        img_byte = io.BytesIO()
        inverted.save(img_byte, format="PNG")
        img_byte.seek(0)

        rect = fitz.Rect(0, 0, pix.width, pix.height)
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=img_byte.read())

    new_doc.save(output_path)
    new_doc.close()
    doc.close()

def merge_pdfs(pdf_list, output_file):
    final_doc = fitz.open()
    for pdf in pdf_list:
        src = fitz.open(pdf)
        for page in src:
            final_doc.insert_pdf(src, from_page=page.number, to_page=page.number)
        src.close()
    final_doc.save(output_file)
    final_doc.close()

def layout_slides_3_per_page(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()

    page_width = 595
    page_height = 842
    margin_top = 5
    margin_side = 57
    right_margin = 5
    spacing = 0

    slide_width = page_width - margin_side - right_margin
    available_height = page_height - margin_top - 2 * spacing
    slide_height = available_height / 3

    for i in range(0, len(doc), 3):
        page = new_doc.new_page(width=page_width, height=page_height)
        for j in range(3):
            if i + j >= len(doc):
                break
            src_page = doc[i + j]
            pix = src_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            img_buffer = io.BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            top = margin_top + j * (slide_height + spacing)
            rect = fitz.Rect(margin_side, top, margin_side + slide_width, top + slide_height)
            page.insert_image(rect, stream=img_buffer.read(), keep_proportion=True)

        text = f"Page {(i // 3) + 1}"
        x = page_width - 100
        y = page_height - 20
        page.insert_text(fitz.Point(x, y), text, fontsize=10, fontname="helv", color=(0, 0, 0))

    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()

def zip_file(file_path):
    zip_path = file_path.replace(".pdf", ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, os.path.basename(file_path))
    return zip_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    files = request.files.getlist('pdfs')
    if not files or len(files) == 0:
        return "No files uploaded", 400

    unique_id = str(uuid.uuid4())
    temp_folder = os.path.join(UPLOAD_FOLDER, unique_id)
    os.makedirs(temp_folder, exist_ok=True)

    inverted_files = []
    for f in files:
        input_path = os.path.join(temp_folder, f.filename)
        f.save(input_path)
        inverted_path = os.path.join(temp_folder, f"inv_{f.filename}")
        invert_pdf_colors(input_path, inverted_path)
        inverted_files.append(inverted_path)

    merged_path = os.path.join(temp_folder, "merged.pdf")
    merge_pdfs(inverted_files, merged_path)

    final_pdf_path = os.path.join(OUTPUT_FOLDER, f"final_{unique_id}.pdf")
    layout_slides_3_per_page(merged_path, final_pdf_path)

    zip_path = zip_file(final_pdf_path)

    # Cleanup temp folder after processing (optional)
    # shutil.rmtree(temp_folder)

    return send_file(zip_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
