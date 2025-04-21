import streamlit as st
from pinecone import Pinecone
from langchain_mistralai import MistralAIEmbeddings
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
import os
import time
from dotenv import load_dotenv

load_dotenv()

# 🔹 Configuração do Pinecone
PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]
PINECONE_HOST = st.secrets["PINECONE_HOST"]

# 🔹 Inicializar Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

# 🔹 Inicializar modelo de embeddings da Mistral
MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]
embed_model = MistralAIEmbeddings(
    model="mistral-embed",
    mistral_api_key=MISTRAL_API_KEY
)

# 🔹 Usuário autenticado
user_email = st.session_state.get("user_email", None)
user_uid = st.session_state.get("user_uid", None)

if not user_email or not user_uid:
    st.error("⚠️ Você precisa estar autenticado para acessar o chat.")
    st.stop()

# 🔹 Configuração do Chat
st.title("Chat com seus Documentos")

# Inicializar histórico do chat e contexto acumulativo
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibir mensagens anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada do usuário
if user_query := st.chat_input("Digite sua pergunta sobre os documentos..."):
    # Exibir mensagem do usuário
    st.chat_message("user").markdown(user_query)
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.spinner("🔍 Buscando informações nos seus documentos..."):
        try:
            # 🔹 Gerar embedding da consulta
            xq = embed_model.embed_query(user_query)

            # 🔹 Buscar documentos relevantes no Pinecone
            res = index.query(vector=xq, top_k=12, include_metadata=True, namespace=user_uid)  # 🔹 Aumentamos o `top_k`

            # 🔹 Verificar se há resultados
            if not res["matches"]:
                st.warning("⚠️ Nenhum resultado encontrado nos seus dados.")
                contexts = ["Nenhum contexto relevante encontrado."]
            else:
                # 🔹 Ordenação refinada para priorizar documentos mais relevantes
                results = sorted(res["matches"], key=lambda x: x["score"], reverse=True)
                contexts = [item["metadata"].get("source_text", "Texto não disponível") for item in results]
                sources = [item["metadata"].get("source", "Fonte desconhecida") for item in results]

                # 🔹 Gerar trechos de resposta sem truncamento excessivo
                structured_context = "\n\n".join([
                    f"Trecho {i+1} (Fonte: {sources[i]}):\n{contexts[i]}"
                    for i in range(len(contexts))
                ])

            # 🔹 Ajustar histórico de conversa para manter melhor o contexto
            conversation_history = st.session_state.messages[-8:]  # 🔹 Expandimos para 10 mensagens anteriores

            conversation_history.append({"role": "user", "content": f"""
            Você deve responder usando APENAS as informações abaixo. Se as informações não forem suficientes, apenas diga: "Não encontrei informações suficientes nos documentos."

            <contexto>
            {structured_context}
            </contexto>

            Pergunta: {user_query}
            """})

            # 🔹 Inicializar cliente Mistral
            client = Mistral(api_key=MISTRAL_API_KEY)

            # 🔹 Tentativa com retries automáticos para erro 429
            max_retries = 3
            retry_delay = 5  # segundos
            for attempt in range(max_retries):
                try:
                    response = client.chat.complete(
                        model="mistral-large-latest",
                        temperature=0,
                        messages=[{"role": "system", "content": "Você é um assistente especializado em responder perguntas com base nos documentos fornecidos."}] + conversation_history,
                    )
                    bot_response = response.choices[0].message.content
                    break  # Sai do loop se a requisição for bem-sucedida
                except SDKError as e:
                    if "429" in str(e):
                        st.warning(f"🚦 Limite de requisições excedido. Tentando novamente ({attempt+1}/{max_retries})...")
                        time.sleep(retry_delay)
                    else:
                        raise e
            else:
                st.error("⚠️ O serviço atingiu o limite de requisições. Por favor, tente novamente mais tarde.")
                bot_response = "Não foi possível obter uma resposta no momento. Tente novamente mais tarde."

        except SDKError:
            st.error("⚠️ Erro ao acessar o modelo de IA. Tente novamente mais tarde.")
            bot_response = "Não foi possível processar sua solicitação devido a um erro no servidor."

        except Exception:
            st.error("⚠️ Ocorreu um erro inesperado. Tente novamente mais tarde.")
            bot_response = "Houve um erro ao processar sua pergunta. Tente novamente."

    # Exibir resposta do assistente
    with st.chat_message("assistant"):
        st.markdown(bot_response)

    # Adicionar resposta ao histórico
    st.session_state.messages.append({"role": "assistant", "content": bot_response})

    # 🔹 Feedback do usuário
    feedback = st.radio("A resposta foi útil?", ("👍 Sim", "👎 Não"), horizontal=True)
    if feedback == "👎 Não":
        st.text_area("Nos diga como podemos melhorar:", key="feedback_input")

