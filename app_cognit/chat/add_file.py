import streamlit as st
import pandas as pd
from io import StringIO
from uuid import uuid4
from streamlit_option_menu import option_menu
from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from pinecone.grpc import PineconeGRPC as Pinecone
import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

# 🔹 Carregar variáveis de ambiente
load_dotenv()

DB_CONFIG = st.secrets["postgresql"]

# 🔹 Configuração do Pinecone
PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]  
PINECONE_HOST = st.secrets["PINECONE_HOST"]
BATCH_SIZE = 400  

# 🔹 Inicializar Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

# 🔹 Inicializar modelo de embeddings da Mistral
embed_model = MistralAIEmbeddings(model="mistral-embed")

# 🔹 Usuário autenticado
user_email = st.session_state.get("user_email", None)
user_uid = st.session_state.get("user_uid", None)
if not user_email or not user_uid:
    st.error("⚠️ Você precisa estar autenticado para enviar arquivos.")
    st.stop()

# 🎨 Criar menu horizontal com `option_menu`
file_type = option_menu(
    menu_title=None,
    options=["CSV", "PDF", "TXT"],
    icons=["table", "file-pdf", "file-text"],
    menu_icon="cloud-upload",
    default_index=0,
    orientation="horizontal",
    
)

# 🔹 Upload do arquivo
file_extensions = {"CSV": ["csv"], "PDF": ["pdf"], "TXT": ["txt"]}
uploaded_file = st.file_uploader(f"Selecione um arquivo {file_type}", type=file_extensions[file_type])

def cleanup_temp_file(temp_file_path):
    """Remove o arquivo temporário com segurança."""
    try:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    except Exception as e:
        st.warning(f"⚠️ Não foi possível remover o arquivo temporário: {e}")

if uploaded_file:
    preview_text = ""  # Variável para armazenar a pré-visualização
    documents = []  # Variável para armazenar chunks

    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{uuid4()}.{file_type.lower()}")

    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    try:
        if file_type == "CSV":
            dataframe = pd.read_csv(uploaded_file)
            st.write("📋 **Pré-visualização do CSV:**")
            st.dataframe(dataframe.head())

            loader = CSVLoader(file_path=temp_file_path)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)
            documents = loader.load_and_split(text_splitter=text_splitter)

        elif file_type == "PDF":
            with st.spinner("🔍 Carregando arquivo PDF..."):
                loader = PyPDFLoader(temp_file_path)
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                documents = loader.load_and_split(text_splitter=text_splitter)

        elif file_type == "TXT":
            with st.spinner("📄 Carregando arquivo TXT..."):
                loader = TextLoader(temp_file_path, encoding="utf-8")
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
                documents = loader.load_and_split(text_splitter=text_splitter)
    
        # 🔹 Pré-visualizar apenas o primeiro chunk
        if documents:
            preview_text = """
""".join([doc.page_content[:500] for doc in documents[:5]])

        st.write(f"📄 **Pré-visualização do {file_type}:**")
        st.text(preview_text + "..." if len(preview_text) > 500 else preview_text)

        # 🔹 Botão para processar o arquivo
        if st.button(f"🚀 Enviar {file_type} para DataStore | 🪙50"):
            try:
                with st.spinner("📄 Processando arquivo e enviando para o DataStore..."):
                    texts = [doc.page_content for doc in documents]
                    metadatas = [{"source": uploaded_file.name, "source_text": doc.page_content, "original_source": uploaded_file.name, **doc.metadata} for doc in documents]
                    embeddings = embed_model.embed_documents(texts)

                    data = [
                        {"id": str(uuid4()), "values": emb, "metadata": meta}
                        for emb, meta in zip(embeddings, metadatas)
                    ]

                    def chunker(seq, batch_size):
                        return (seq[pos:pos + batch_size] for pos in range(0, len(seq), batch_size))

                    async_results = [
                        index.upsert(vectors=chunk, namespace=user_uid, async_req=True)
                        for chunk in chunker(data, batch_size=BATCH_SIZE)
                    ]
                    [async_result.result() for async_result in async_results]

                    st.success(f"✅ {file_type} enviado com sucesso para o DataStore")

            except Exception as e:
                st.error(f"⚠️ Erro ao enviar arquivo: {e}")
    
    finally:
        cleanup_temp_file(temp_file_path)
