Requirements
Python 3.9+ (recommended)
Tesseract OCR installed
Windows / macOS / Linux

Python packages
pip install pillow pytesseract mss

Setup Tesseract
Windows
Download: https://github.com/tesseract-ocr/tesseract
Install and add to PATH

Usage
Capture screenshots (loop)
python main.py capture

or with interval (seconds):
python main.py capture 2

Screenshots will be saved into:
screenshots/

OCR latest screenshot
python main.py ocr-latest

Output:

===== OCR RESULT =====
Email or phone
Password
Log In

Analyze page actions
python main.py analyze

Detects semantic actions like:
login
username field
password field
submit button

Locate UI elements (coordinates)
python main.py locate

Example output:
LOGIN FOUND AT:
{'text': 'log', 'x': 374, 'y': 16, 'w': 15, 'h': 12}
CENTER: 381 22
