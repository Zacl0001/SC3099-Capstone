# Responsible for:
#
# Upload file
# Validate file type
# Store file
# Retrieve file
# Delete file
# Extract text
# Later you can support:
#
# .txt
# .md
# .docx
# .pdf
# For the MVP, I'd start with .txt.
#
# Get the complete pipeline working first.

from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from docx import Document
from zipfile import BadZipFile
from lxml.etree import XMLSyntaxError

STORAGE_ROOT  = Path(__file__).resolve().parents[3] / "storage" # builds path to storage folder

def prepare_upload_directory() -> Path:
    upload_directory = STORAGE_ROOT / "transcripts" #path to subfolder
    upload_directory.mkdir(parents=True, exist_ok=True)

    return upload_directory

def save_transcript_file(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()

    if extension not in {".pdf", ".docx", ".txt"}:
        raise ValueError("Only PDF, DOCX AND TXT Files supported")

    upload_directory = prepare_upload_directory()
    stored_name = f"{uuid4().hex}{extension}"
    destination = upload_directory / stored_name
    max_bytes = 10 * 1024 * 1024
    total_bytes = 0

    try: 
        with destination.open("xb") as output: #creates new binary file
            while chunk := file.file.read(1024 * 1024): #reads 1mb at a time
                total_bytes += len(chunk)

                if total_bytes > max_bytes:
                    raise ValueError("File must not exceed 10MB")

                output.write(chunk)

        if total_bytes == 0:
            raise ValueError("Empty file, please upload another file")

    except Exception:
        destination.unlink(missing_ok=True) #deletes incomplete file

        raise 

    return f"transcripts/{stored_name}"


def extract_transcript_txt(storage_key: str) -> str:
    file_path = (STORAGE_ROOT / storage_key).resolve()

    if not file_path.is_relative_to(STORAGE_ROOT.resolve()): #checks if file path is in storage folder
        raise ValueError("Invalid storage key")

    extension = file_path.suffix.lower()

    if extension == ".txt":

        try:
            text = file_path.read_text(encoding="utf-8-sig")

        except UnicodeDecodeError as exc:
            raise ValueError("save txt file using UTF-8 encoding") from exc

    elif extension == ".pdf":
        text = extract_pdf_text(file_path)

    elif extension == ".docx":
        text = extract_docx_text(file_path)

    else:
        raise ValueError("Extraction only supports PDF, WORD and TXT files only")

    text = text.strip()

    if not text:
        raise ValueError("transcript contains no text")

    return text

def extract_pdf_text(file_path: Path) -> str:
    try:
        with file_path.open("rb") as source:
            reader = PdfReader(source)

            if reader.is_encrypted:
                raise ValueError("Encrypted pdfs are not supported")

            pages = []

            for page in reader.pages:
                pages.append(page.extract_text() or "")


    except PdfReadError as exc:
        raise ValueError("Unable to read this PDF file") from exc


    text = "\n".join(pages).strip()

    if not text:
        raise ValueError("PDF contains no extractable text")


    return text


def extract_docx_text(file_path: Path) -> str:
    try:
        with file_path.open("rb") as source:
            document = Document(source)
            paragraphs = []

            for paragraph in document.paragraphs:
                paragraphs.append(paragraph.text)

    except (BadZipFile, XMLSyntaxError, KeyError, ValueError) as exc:
        raise ValueError("Unable to read this DOCX file") from exc


    text = "\n".join(paragraphs).strip()


    if not text:
        raise ValueError("this docx file contains no extractable text")

    return text