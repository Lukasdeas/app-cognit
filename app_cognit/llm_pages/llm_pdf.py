import streamlit as st
import fitz  # PyMuPDF para PDFs digitais
import pytesseract
from PIL import Image
import io
from openai import OpenAI

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# Configuração da API OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

def extract_text_from_pdf(uploaded_file):
    """Extrai texto de um PDF digital."""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        return "\n".join([page.get_text("text") for page in doc]).strip() or None

def extract_text_from_scanned_pdf(uploaded_file):
    """Extrai texto de um PDF escaneado utilizando OCR."""
    images = convert_pdf_to_images(uploaded_file)
    return "\n".join([pytesseract.image_to_string(img) for img in images]).strip()

def convert_pdf_to_images(uploaded_file):
    """Converte um PDF escaneado em imagens."""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        return [Image.open(io.BytesIO(page.get_pixmap().tobytes("png"))) for page in doc]

def split_text(text, max_tokens=4000):
    """Divide um texto longo em chunks menores para processamento eficiente."""
    words = text.split()
    chunks, current_chunk = [], []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk, current_length = [], 0
        current_chunk.append(word)
        current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def chat_with_llm(prompt, context):
    """Interage com o modelo LLM processando o contexto em chunks para evitar limites de tokens."""
    text_chunks = split_text(context, max_tokens=4000)
    responses = []
    
    for chunk in text_chunks:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em processamento de PDFs."},
                {"role": "user", "content": f"{chunk}\n\n{prompt}"}
            ],
            temperature=0.7
        )
        responses.append(response.choices[0].message.content)
    
    return "\n---\n".join(responses)

# Interface Streamlit
st.title("📄 Agente LLM para PDFs")

uploaded_file = st.file_uploader("Envie um arquivo PDF", type=["pdf"])

if uploaded_file:
    st.write("### Extraindo texto...")
    text = extract_text_from_pdf(uploaded_file) or extract_text_from_scanned_pdf(uploaded_file)
    
    if text:
        st.text_area("Texto extraído:", text[:1000] + "... (Texto truncado)" if len(text) > 1000 else text, height=300)
        
        st.write("### Interaja com o assistente")
        user_input = st.text_area("Faça uma pergunta ou peça uma ação (ex: Resuma o documento, Gere 5 perguntas de múltipla escolha)")
        
        if st.button("Enviar") and user_input:
            response = chat_with_llm(user_input, text)
            st.write("### Resposta do LLM:")
            st.write(response)
    else:
        st.error("Não foi possível extrair texto do PDF.")
