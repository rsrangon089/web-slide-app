import os
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import io
import zipfile
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ----------- Utility Functions ----------- #

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
        final_doc.insert_pdf(src)
        src.close()
    final_doc.save(output_file)
    final_doc.close()


def layout_slides_3_per_page(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()

    page_width, page_height = 595, 842
    margin_top, margin_side, right_margin, spacing = 5, 57, 5, 0
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

        new_doc.insert_pdf(new_doc[-1])

    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()


def zip_file(pdf_path):
    zip_path = pdf_path.replace(".pdf", ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(pdf_path, os.path.basename(pdf_path))
    return zip_path


# ----------- Routes ----------- #

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_files = request.files.getlist("pdf_files")
        input_paths = []

        for file in uploaded_files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                input_paths.append(file_path)

        inverted_paths = []
        for path in input_paths:
            name = os.path.splitext(os.path.basename(path))[0]
            output_path = os.path.join(OUTPUT_FOLDER, f"{name}_inverted.pdf")
            invert_pdf_colors(path, output_path)
            inverted_paths.append(output_path)

        merged_path = os.path.join(OUTPUT_FOLDER, "merged.pdf")
        merge_pdfs(inverted_paths, merged_path)

        final_output_path = os.path.join(OUTPUT_FOLDER, "Final_Output.pdf")
        layout_slides_3_per_page(merged_path, final_output_path)

        zip_path = zip_file(final_output_path)
        return send_file(zip_path, as_attachment=True)

    return render_template("index.html")
