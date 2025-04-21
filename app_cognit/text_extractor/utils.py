import os
import re
import openai
from langdetect import detect
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Inicializa o cliente OpenAI com a chave da API
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def save_uploaded_file(uploaded_file, save_path="temp_image.png"):
    """Salva a imagem enviada para processamento."""
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return save_path

def delete_temp_file(file_path):
    """Remove arquivos temporários após o processamento."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except PermissionError:
        pass

def clean_extracted_text(text):
    """Remove espaços extras e caracteres indesejados do texto extraído."""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)  # Substitui múltiplos espaços por um único
    return text

def detect_language(text):
    """Detecta o idioma do texto extraído."""
    try:
        lang = detect(text)
        return lang
    except:
        return "unknown"
def refine_text_with_llm(text):
    """Refina o texto extraído usando um LLM (GPT-4) da OpenAI."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um assistente que melhora textos extraídos de OCR, corrigindo erros e formatando corretamente."},
                {"role": "user", "content": f"Corrija e formate o seguinte texto extraído de OCR:\n{text}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao refinar texto com LLM: {e}"
