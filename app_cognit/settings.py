import streamlit as st
import psycopg2
import jwt
import os
import datetime

# 🔐 Configuração de segurança para JWT
SECRET_KEY = st.secrets["security"]["SECRET_KEY"]

def verify_session():
    """Verifica se o usuário está autenticado com base no token JWT."""
    token = st.session_state.get("session_token")
    if not token:
        return False
    
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token["email"]
    except jwt.ExpiredSignatureError:
        st.error("Sua sessão expirou. Faça login novamente.")
        return False
    except jwt.InvalidTokenError:
        st.error("Sessão inválida. Faça login novamente.")
        return False

# 🔹 Configuração do Banco de Dados PostgreSQL
DB_CONFIG = st.secrets["postgresql"]

@st.cache_data(ttl=60)  # Cache de 60 segundos
def get_user_info_cached(email):
    """Obtém as informações do usuário com cache para reduzir consultas ao banco."""
    return get_user_info(email)

def connect_db():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def get_user_info(email):
    """Obtém as informações do usuário de forma segura."""
    with connect_db() as conn:
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT username, email, phone, coins FROM users WHERE email = %s", (email,))
                    result = cursor.fetchone()
                    if result:
                        return {
                            "username": result[0],
                            "email": result[1],
                            "phone": result[2],
                            "coins": result[3]
                        }
            except Exception as e:
                st.error(f"Erro ao buscar informações do usuário: {e}")
    return None

def logout():
    """Realiza o logout do usuário e recarrega a interface."""
    for key in ["session_token", "user_email", "user_coins"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()  # Atualiza a interface para refletir o logout

# 🔹 Página de Configurações
st.title("Configurações da Conta")

# 🚀 **Validação Segura da Sessão**
if not verify_session():
    st.warning("🔒 Você precisa estar logado para acessar as configurações.")
    st.stop()

# Obtém o e-mail do usuário logado
email = st.session_state.get("user_email")

if not email:
    st.warning("⚠️ Não foi possível recuperar seu e-mail. Faça login novamente.")
    st.stop()

# Obtém as informações do usuário
user_info = get_user_info_cached(email)

if user_info:
    st.subheader("👤 Informações do Usuário")
    
    st.write(f"**📛 Nome:** {user_info['username']}")
    st.write(f"**📧 E-mail:** {user_info['email']}")
    st.write(f"**📞 Telefone:** {user_info['phone']}")

    # Exibe a quantidade de moedas com ícone do Bootstrap
    coins = user_info["coins"]
    st.metric(label="Saldo Atual de Moedas", value=f"💰 {coins}")

    # Botão para atualizar saldo com cache e proteção de conexão
    if st.button("Atualizar Saldo", use_container_width=True):
        new_balance = get_user_info_cached(email)["coins"]  # 🔒 Usa cache para otimizar
        st.session_state["user_coins"] = new_balance
        st.success("Saldo atualizado!")
        st.rerun()

    # Separador para organização
    st.divider()

    # Botão de logout com ícone do Bootstrap
    if st.button("Sair da Conta", use_container_width=True):
        logout()
else:
    st.error("❌ Não foi possível recuperar as informações da conta. Tente novamente mais tarde.")

