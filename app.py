
import streamlit as st
import pymupdf
from pathlib import Path

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="PDF Privacy Cleaner",
    page_icon="🛡️",
    layout="wide"
)

MAX_FILE_SIZE_MB = 100

# --------------------------------------------------
# PDF PROCESSING FUNCTIONS
# --------------------------------------------------

def count_annotations(doc):
    total = 0

    for page in doc:
        total += len(list(page.annots() or []))

    return total


def remove_metadata(doc):
    """
    Remove standard PDF metadata and XML/XMP metadata.
    """
    doc.set_metadata({})
    doc.del_xml_metadata()


def basic_clean(doc, remove_annotations, remove_attachments):
    """
    Basic metadata cleaning with optional removal
    of annotations and embedded attachments.
    """

    remove_metadata(doc)

    if remove_annotations:
        for page in doc:

            # Remove comments and annotations
            for annot in list(page.annots() or []):
                page.delete_annot(annot)

            # Remove form widgets
            for widget in list(page.widgets() or []):
                page.delete_widget(widget)

    if remove_attachments:
        for name in list(doc.embfile_names()):
            doc.embfile_del(name)

    return doc.tobytes(
        garbage=4,
        deflate=True
    )


def deep_clean(doc):
    """
    Use PyMuPDF's sanitization functionality to
    remove potentially sensitive document content.
    """

    doc.scrub(
        attached_files=True,
        clean_pages=True,
        embedded_files=True,
        hidden_text=True,
        javascript=True,
        metadata=True,
        redactions=True,
        redact_images=0,
        remove_links=True,
        reset_fields=True,
        reset_responses=True,
        thumbnails=True,
        xml_metadata=True
    )

    remove_metadata(doc)

    return doc.tobytes(
        garbage=4,
        deflate=True
    )


def full_reconstruction(doc, dpi, progress_callback=None):
    """
    Create a completely new PDF using rendered
    page images instead of copying original PDF objects.

    Original text objects, annotations, attachments,
    links, forms, and document structure are not copied.
    """

    output = pymupdf.open()

    try:
        total_pages = doc.page_count

        for index in range(total_pages):

            page = doc.load_page(index)

            # Render the visible page without annotations
            pixmap = page.get_pixmap(
                dpi=dpi,
                alpha=False,
                annots=False
            )

            # Create a fresh page
            new_page = output.new_page(
                width=page.rect.width,
                height=page.rect.height
            )

            # Insert only the rendered page image
            image_bytes = pixmap.tobytes("png")

            new_page.insert_image(
                new_page.rect,
                stream=image_bytes
            )

            if progress_callback:
                progress_callback((index + 1) / total_pages)

        # Remove metadata from the newly created PDF
        remove_metadata(output)

        # Save as a fresh, non-incremental PDF
        return output.tobytes(
            garbage=4,
            deflate=True
        )

    finally:
        output.close()


def process_pdf(
    pdf_bytes,
    mode,
    remove_annotations=False,
    remove_attachments=False,
    dpi=200,
    progress_callback=None
):
    """
    Main processing controller.
    """

    source = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    try:
        if source.needs_pass:
            raise ValueError(
                "This PDF is password protected. "
                "Unlock it before processing."
            )

        if source.page_count == 0:
            raise ValueError("The PDF contains no pages.")

        if mode == "Basic Clean":

            return basic_clean(
                source,
                remove_annotations,
                remove_attachments
            )

        elif mode == "Deep Clean":

            return deep_clean(source)

        elif mode == "Full Reconstruction":

            return full_reconstruction(
                source,
                dpi,
                progress_callback
            )

        else:
            raise ValueError("Invalid cleaning mode.")

    finally:
        source.close()


# --------------------------------------------------
# VERIFICATION
# --------------------------------------------------

def verify_pdf(pdf_bytes):

    result = {}

    with pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf"
    ) as doc:

        metadata = doc.metadata or {}

        metadata_fields = [
            "title",
            "author",
            "subject",
            "keywords",
            "creator",
            "producer",
            "creationDate",
            "modDate",
            "trapped"
        ]

        remaining_metadata = {
            key: metadata.get(key)
            for key in metadata_fields
            if metadata.get(key)
            and str(metadata.get(key)).strip().lower()
            not in ("none", "null")
        }

        xml_metadata = doc.get_xml_metadata()

        annotation_count = count_annotations(doc)

        link_count = sum(
            len(page.get_links())
            for page in doc
        )

        text_count = sum(
            len(page.get_text().strip())
            for page in doc
        )

        image_only = all(
            len(page.get_images(full=True)) > 0
            and len(page.get_text().strip()) == 0
            for page in doc
        )

        result = {
            "pages": doc.page_count,
            "metadata": remaining_metadata,
            "xmp_present": bool(xml_metadata),
            "attachments": doc.embfile_count(),
            "annotations": annotation_count,
            "links": link_count,
            "text_characters": text_count,
            "image_only": image_only,
            "pdf_version_count": doc.version_count
        }

    return result


# --------------------------------------------------
# USER INTERFACE
# --------------------------------------------------

st.title("PDF Privacy Cleaner")

st.write(
    "Inspect PDF documents, remove metadata, "
    "and optionally reconstruct them."
)

st.divider()

st.subheader("1. Upload PDF")

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"]
)

if uploaded_file:

    pdf_bytes = uploaded_file.getvalue()

    file_size_mb = len(pdf_bytes) / (1024 * 1024)

    if file_size_mb > MAX_FILE_SIZE_MB:

        st.error(
            f"File exceeds the {MAX_FILE_SIZE_MB} MB limit."
        )
        st.stop()

    try:

        original_doc = pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        if original_doc.needs_pass:

            password = st.text_input(
                "Enter PDF password",
                type="password"
            )

            if not password:
                st.warning("This PDF requires a password.")
                st.stop()

            if not original_doc.authenticate(password):
                st.error("Incorrect PDF password.")
                st.stop()

        metadata = original_doc.metadata or {}

        original_versions = original_doc.version_count

        st.success("PDF uploaded successfully.")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Pages",
            original_doc.page_count
        )

        col2.metric(
            "File Size",
            f"{file_size_mb:.2f} MB"
        )

        col3.metric(
            "PDF Versions Reported",
            original_versions
        )

        st.divider()

        # ------------------------------------------
        # METADATA INSPECTION
        # ------------------------------------------

        st.subheader("2. Existing PDF Metadata")

        metadata_display = {
            key: value
            for key, value in metadata.items()
            if value and key not in ("format", "encryption")
        }

        if metadata_display:

            st.json(metadata_display)

        else:

            st.info("No standard metadata detected.")

        st.write(
            f"**Embedded attachments:** "
            f"{original_doc.embfile_count()}"
        )

        st.write(
            f"**Annotations:** "
            f"{count_annotations(original_doc)}"
        )

        original_doc.close()

        st.divider()

        # ------------------------------------------
        # CLEANING MODES
        # ------------------------------------------

        st.subheader("3. Select Cleaning Mode")

        mode = st.radio(
            "Cleaning method",
            [
                "Basic Clean",
                "Deep Clean",
                "Full Reconstruction"
            ]
        )

        remove_annotations = False
        remove_attachments = False
        dpi = 200

        if mode == "Basic Clean":

            st.info(
                "Removes standard document metadata "
                "and XMP metadata."
            )

            remove_annotations = st.checkbox(
                "Also remove annotations, comments "
                "and form widgets"
            )

            remove_attachments = st.checkbox(
                "Also remove embedded attachments"
            )

        elif mode == "Deep Clean":

            st.warning(
                "Performs structural sanitization. "
                "This also removes hidden text, links, "
                "JavaScript, attachments, thumbnails "
                "and form data. Pending redactions "
                "will be applied."
            )

        elif mode == "Full Reconstruction":

            st.warning(
                "Creates a new PDF from rendered page images. "
                "Original selectable text, annotations, "
                "attachments, links, forms and bookmarks "
                "will not be preserved."
            )

            dpi = st.select_slider(
                "Output resolution (DPI)",
                options=[150, 200, 250, 300],
                value=200
            )

            st.caption(
                "Higher DPI improves image quality but "
                "increases processing time and file size."
            )

        st.divider()

        # ------------------------------------------
        # PROCESSING
        # ------------------------------------------

        if st.button(
            "Clean PDF",
            type="primary",
            use_container_width=True
        ):

            progress = st.progress(0)

            try:

                with st.spinner("Processing PDF..."):

                    cleaned_pdf = process_pdf(
                        pdf_bytes=pdf_bytes,
                        mode=mode,
                        remove_annotations=remove_annotations,
                        remove_attachments=remove_attachments,
                        dpi=dpi,
                        progress_callback=progress.progress
                    )

                progress.progress(1.0)

                st.success(
                    "PDF processing completed."
                )

                # ----------------------------------
                # DOWNLOAD
                # ----------------------------------

                original_name = Path(
                    uploaded_file.name
                ).stem

                suffix = (
                    "_reconstructed"
                    if mode == "Full Reconstruction"
                    else "_cleaned"
                )

                output_name = (
                    f"{original_name}{suffix}.pdf"
                )

                st.download_button(
                    label="Download Cleaned PDF",
                    data=cleaned_pdf,
                    file_name=output_name,
                    mime="application/pdf",
                    use_container_width=True
                )

                # ----------------------------------
                # VERIFICATION
                # ----------------------------------

                st.divider()

                st.subheader("4. Output Verification")

                audit = verify_pdf(cleaned_pdf)

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Pages",
                    audit["pages"]
                )

                col2.metric(
                    "Attachments",
                    audit["attachments"]
                )

                col3.metric(
                    "Annotations",
                    audit["annotations"]
                )

                st.write("**Metadata verification**")

                if (
                    not audit["metadata"]
                    and not audit["xmp_present"]
                ):

                    st.success(
                        "Standard metadata and XMP metadata "
                        "are absent."
                    )

                else:

                    st.warning(
                        f"Metadata still detected: "
                        f"{audit['metadata']}"
                    )

                if mode == "Full Reconstruction":

                    if audit["image_only"]:

                        st.success(
                            "All output pages contain rendered "
                            "images and no selectable text objects."
                        )

                        st.success(
                            "The new PDF contains no copied "
                            "original PDF page structure or "
                            "incremental revision chain."
                        )

                    else:

                        st.warning(
                            "Image-only verification was "
                            "not successful for every page."
                        )

                else:

                    st.write(
                        f"Remaining text characters: "
                        f"{audit['text_characters']}"
                    )

                    st.write(
                        f"Remaining links: "
                        f"{audit['links']}"
                    )

                    st.write(
                        f"PDF update versions reported: "
                        f"{audit['pdf_version_count']}"
                    )

                output_size = len(cleaned_pdf) / (1024 * 1024)

                st.write(
                    f"**Output size:** {output_size:.2f} MB"
                )

                st.caption(
                    "Verification checks the generated PDF only. "
                    "It does not inspect cloud version histories, "
                    "backups, external logs or the original file."
                )

            except Exception as error:

                st.error(
                    f"Processing failed: {error}"
                )

    except Exception as error:

        st.error(f"Unable to open PDF: {error}")

st.divider()

st.caption(
    "PDF Privacy Cleaner | Local PDF processing | Version 1.1"
)
