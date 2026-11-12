"""Words a translation keeps in English (translation agent rules). Offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audit.keep_terms import looks_untranslated, translatable_words  # noqa: E402

H = "blog.example.cloud"


def test_product_names_formats_and_platforms_do_not_count():
    assert translatable_words("Brand.PDF for Python via .NET", H) == []
    assert translatable_words("Convert DOCX to PDF in C# with REST API", H) == ["Convert", "to", "in", "with"]
    assert not looks_untranslated("Example Cloud Blog", H)  # host labels + one word
    assert not looks_untranslated("Brand.Total for .NET 25.1 | Brand.Cells for Java", H)
    assert not looks_untranslated("Get 25% OFF on Brand.Total", H)


def test_real_english_sentences_still_count():
    assert looks_untranslated("Manipulate PDF Documents using Brand.Cloud REST API", H)
    assert looks_untranslated("File Format and Document Processing APIs | Example Cloud", H)


def test_tenant_terms():
    assert not looks_untranslated("Document Automation Suite", H, [r"Document Automation Suite"])
