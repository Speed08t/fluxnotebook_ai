#!/usr/bin/env python3
"""
Create a test PDF with mathematical content for testing the PDF upload functionality.
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os

def create_test_pdf():
    filename = "test_math_notes.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Page 1 - Calculus Notes
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Calculus Notes - Derivatives")
    
    c.setFont("Helvetica", 12)
    y = height - 100
    
    content = [
        "Basic Derivative Rules:",
        "",
        "1. Power Rule: d/dx(x^n) = n*x^(n-1)",
        "",
        "2. Product Rule: d/dx(f*g) = f'*g + f*g'",
        "",
        "3. Chain Rule: d/dx(f(g(x))) = f'(g(x)) * g'(x)",
        "",
        "Examples:",
        "",
        "Find the derivative of f(x) = 3x^2 + 2x - 5",
        "Solution: f'(x) = 6x + 2",
        "",
        "Find the derivative of g(x) = sin(x^2)",
        "Solution: g'(x) = cos(x^2) * 2x = 2x*cos(x^2)",
    ]
    
    for line in content:
        c.drawString(50, y, line)
        y -= 20
    
    c.showPage()
    
    # Page 2 - Integration Notes
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Integration Techniques")
    
    c.setFont("Helvetica", 12)
    y = height - 100
    
    content2 = [
        "Basic Integration Rules:",
        "",
        "1. Power Rule: ∫x^n dx = x^(n+1)/(n+1) + C",
        "",
        "2. Substitution: ∫f(g(x))g'(x) dx = ∫f(u) du where u = g(x)",
        "",
        "3. Integration by Parts: ∫u dv = uv - ∫v du",
        "",
        "Examples:",
        "",
        "Evaluate ∫(2x + 3) dx",
        "Solution: x^2 + 3x + C",
        "",
        "Evaluate ∫x*e^(x^2) dx",
        "Solution: Let u = x^2, du = 2x dx",
        "∫x*e^(x^2) dx = (1/2)∫e^u du = (1/2)e^(x^2) + C",
    ]
    
    for line in content2:
        c.drawString(50, y, line)
        y -= 20
    
    c.save()
    print(f"Created test PDF: {filename}")
    return filename

if __name__ == "__main__":
    try:
        filename = create_test_pdf()
        print(f"Test PDF created successfully: {filename}")
        print("You can now upload this PDF to test the functionality.")
    except ImportError:
        print("reportlab not found. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "reportlab"])
        filename = create_test_pdf()
        print(f"Test PDF created successfully: {filename}")
