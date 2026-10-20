"""Text of a PDF (pypdf), pages given as 1-based first:last; prints page markers. Usage: pdf_text.py file.pdf [1:20]"""
import sys
from pypdf import PdfReader

r = PdfReader(sys.argv[1])
a, b = (int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else f"1:{len(r.pages)}").split(":"))
print(f"pages {len(r.pages)}")
for i in range(a - 1, min(b, len(r.pages))):
    print(f"===== page {i + 1}")
    print(r.pages[i].extract_text())
