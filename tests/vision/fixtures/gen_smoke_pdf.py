"""生成一个用于分诊测试的最小 PDF。仅用于 Phase 1 冒烟测试。"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pathlib import Path

out_path = Path(__file__).parent / "smoke_test_sample.pdf"
c = canvas.Canvas(str(out_path), pagesize=A4)
w, h = A4

# 页 1：纯文本
c.setFont("Helvetica", 11)
c.drawString(50, h - 60, "Page 1 Native Text Layer Only")
c.drawString(50, h - 80, "Normal text-based PDF page for triage smoke test.")
c.drawString(50, h - 100, "The document_triage should classify this as 'text'.")
for i in range(30):
    c.drawString(50, h - 130 - i * 15, f"Content line {i}: lorem ipsum dolor sit amet.")
c.showPage()

# 页 2：双栏文本
c.setFont("Helvetica", 10)
for i in range(20):
    c.drawString(50, h - 60 - i * 15, f"Left col line {i}: some content here")
    c.drawString(320, h - 60 - i * 15, f"Right col {i}: parallel column data")
c.showPage()

# 页 3：包含"图片"区域（画大矩形，字符很少）
c.setFont("Helvetica", 8)
c.drawString(50, h - 30, "Page 3")
c.rect(50, 100, 500, 600, stroke=1, fill=0)
c.showPage()

c.save()
print(f"OK -> {out_path}")
