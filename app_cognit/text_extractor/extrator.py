import streamlit as st
import jwt
import os
import magic
import logging
import shutil
import psycopg2
from psycopg2 import sql
from PIL import Image
from text_extractor.ocr import extract_text
from text_extractor.utils import (
    save_uploaded_file, clean_extracted_text, detect_language, refine_text_with_llm
)
from dotenv import load_dotenv

# 🔹 Carregar variáveis de ambiente
load_dotenv()

DB_CONFIG = st.secrets["postgresql"]
SECRET_KEY = st.secrets["security"]["SECRET_KEY"]  # Reutiliza a mesma chave da página principal

# 🔹 Logger
logging.basicConfig(filename="uploads.log", level=logging.INFO)

### 🔐 Validação da Sessão Existente ###
def verify_session():
    """Verifica se o usuário está autenticado com base no token JWT armazenado na sessão."""
    token = st.session_state.get("session_token")
    
    if not token:
        st.error("⚠️ Você precisa estar autenticado para acessar esta página.")
        st.stop()

    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token["email"]  # Retorna o e-mail do usuário autenticado
    except jwt.ExpiredSignatureError:
        st.error("Sua sessão expirou. Faça login novamente.")
        st.stop()
    except jwt.InvalidTokenError:
        st.error("Sessão inválida. Faça login novamente.")
        st.stop()

# 🔹 Verificar Sessão (sem gerar novos tokens)
user_email = verify_session()

### 🔹 Conexão com o Banco de Dados ###
def connect_db():
    """Conecta ao banco de dados PostgreSQL de forma segura."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

### 🪙 Gerenciamento de Moedas ###
def get_user_coins(email):
    """Obtém a quantidade de moedas do usuário de forma segura."""
    with connect_db() as conn:
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT coins FROM users WHERE email = %s", (email,))
                    result = cursor.fetchone()
                    return result[0] if result else 0
            except Exception as e:
                st.error(f"Erro ao buscar moedas: {e}")
                return 0
    return 0

def debit_coins(email, amount):
    """Debita moedas do usuário com transação atômica para evitar race conditions."""
    with connect_db() as conn:
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT coins FROM users WHERE email = %s FOR UPDATE", (email,))
                    result = cursor.fetchone()
                    
                    if not result or result[0] < amount:
                        st.warning("⚠️ Saldo insuficiente ou erro na operação.")
                        return False

                    cursor.execute("UPDATE users SET coins = coins - %s WHERE email = %s", (amount, email))
                    conn.commit()
                    return True

            except Exception as e:
                st.error(f"⚠️ Erro ao debitar moedas: {e}")
                return False
    return False

cost_per_upload = 30


# 🎨 Interface da Página
st.write(f"🚀 Bem-vindo, Faça o upload de uma imagem para processá-la.")

# Upload da imagem
uploaded_file = st.file_uploader("🖼️ Escolha uma imagem", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # 🔹 Verificação de tamanho (Máximo 5MB)
    if uploaded_file.size > 5 * 1024 * 1024:
        st.error("⚠️ Arquivo muito grande! O limite é 5MB.")
        st.stop()

    # 🔹 Verificação do tipo de arquivo para evitar exploits
    mime = magic.Magic(mime=True)
    file_mime = mime.from_buffer(uploaded_file.getvalue())

    valid_mime_types = ["image/png", "image/jpeg"]
    if file_mime not in valid_mime_types:
        st.error("⚠️ Tipo de arquivo inválido! Apenas PNG e JPG são aceitos.")
        st.stop()

    # 🔹 Exibir saldo do usuário
    user_balance = get_user_coins(user_email)

    # 🔹 Botão para confirmar processamento
    if st.button(f"🚀 Processar Imagem | 🪙30"):
        if user_balance < cost_per_upload:
            st.warning("⚠️ Saldo insuficiente para processar esta imagem.")
        else:
            # 🔹 Salvar a imagem temporariamente
            img_path = save_uploaded_file(uploaded_file)

            # 🔹 Log de upload
            logging.info(f"Usuário enviou uma imagem para processamento.")

            # Exibir a imagem carregada
            st.image(Image.open(img_path), caption="Imagem carregada", use_container_width=True)

            # 🔹 Processamento OCR e IA
            try:
                with st.spinner("🔍 Extraindo texto..."):
                    extracted_text = extract_text(img_path)
                    cleaned_text = clean_extracted_text(extracted_text)

                with st.spinner("🤖 Refinando texto com IA..."):
                    refined_text = refine_text_with_llm(cleaned_text)

                # 🔹 Detecção de idioma
                language = detect_language(cleaned_text)
                st.write(f"🌍 **Idioma Detectado:** `{language}`")

                # 🔹 Exibir textos processados
                st.subheader("📌 Texto Extraído (OCR):")
                st.text_area("Texto bruto extraído:", cleaned_text, height=200)

                st.subheader("✨ Texto Refinado (CognitAI):")
                st.text_area("Texto aprimorado pela IA:", refined_text, height=200)

                # 🔹 Debitar moedas após sucesso
                if debit_coins(user_email, cost_per_upload):
                    st.success(f"✅ Processamento concluído!")

                # 🔹 Botão para baixar o texto refinado
                st.download_button("📥 Baixar Texto Refinado", refined_text, file_name="refined_text.txt")

            finally:
                # 🔥 Exclusão segura do arquivo
                if os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except Exception as e:
                        st.error("⚠️ Erro ao remover arquivo.")
