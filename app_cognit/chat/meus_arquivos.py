import streamlit as st
from pinecone.grpc import PineconeGRPC as Pinecone
import os
from collections import defaultdict
from dotenv import load_dotenv

# 🔹 Carregar variáveis de ambiente
load_dotenv()

# 🔹 Configuração do Pinecone
PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]  
PINECONE_HOST = st.secrets["PINECONE_HOST"]

# 🔹 Inicializar Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

# 🔹 Usuário autenticado
user_email = st.session_state.get("user_email", None)
user_uid = st.session_state.get("user_uid", None)
if not user_email or not user_uid:
    st.error("⚠️ Você precisa estar autenticado para acessar seus arquivos.")
    st.stop()

st.title("📂 Meus Arquivos")

# 🔹 Buscar documentos do usuário no Pinecone
with st.spinner("🔍 Carregando seus arquivos..."):
    try:
        response = index.query(vector=[0]*1024, top_k=10000, include_metadata=True, namespace=user_uid)
        documentos = response.get("matches", [])
    except Exception as e:
        st.error(f"Erro ao buscar arquivos: {e}")
        documentos = []

# 🔹 Agrupar chunks por documento original
documentos_agrupados = defaultdict(list)
for doc in documentos:
    fonte = doc.get("metadata", {}).get("original_source", "Desconhecido")
    documentos_agrupados[fonte].append(doc)

# 🔹 Exibir documentos agrupados
if documentos_agrupados:
    st.write(f"📄 Total de documentos armazenados: **{len(documentos_agrupados)}**")
    
    # Criar filtro por tipo
    tipos = list(set(doc["metadata"].get("file_type", "Desconhecido") for doc in documentos))
    tipo_selecionado = st.selectbox("Filtrar por tipo de arquivo:", ["Todos"] + tipos)
    
    for fonte, docs in documentos_agrupados.items():
        if tipo_selecionado != "Todos" and docs[0].get("metadata", {}).get("file_type") != tipo_selecionado:
            continue
        
        texto_preview = docs[0]["metadata"].get("source_text", "Sem conteúdo")[0:300] + "..."
        
        with st.expander(f"📜 {fonte} ({len(docs)} chunks)"):
            st.write(f"🔹 **Preview:** {texto_preview}")
            
            if st.button(f"❌ Excluir {fonte}", key=fonte):
                with st.spinner("Removendo documento..."):
                    try:
                        ids_para_excluir = [doc["id"] for doc in docs]
                        
                        # Excluir em lotes de 900
                        for i in range(0, len(ids_para_excluir), 900):
                            index.delete(namespace=user_uid, ids=ids_para_excluir[i:i+900])
                            
                        st.success("✅ Documento removido com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
else:
    st.warning("⚠️ Nenhum documento encontrado na sua coleção.")
