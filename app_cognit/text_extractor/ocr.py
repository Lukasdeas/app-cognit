import cv2
import pytesseract
import numpy as np

CUSTOM_OCR_CONFIG = r'--oem 3 --psm 6'

def preprocess_image(image_path):
    """Pré-processa a imagem para otimizar a extração de texto."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Aplicando um filtro para redução de ruído
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Binarização (Otsu Threshold)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return thresh

def extract_text(image_path):
    """Extrai texto da imagem usando Tesseract OCR."""
    processed_img = preprocess_image(image_path)
    text = pytesseract.image_to_string(processed_img, config=CUSTOM_OCR_CONFIG)
    return text
