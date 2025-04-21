import streamlit as st
st.set_page_config(page_title="Cognit-Assistente Inteligente")
import base64
import firebase_admin
from streamlit_option_menu import option_menu
from firebase_admin import credentials, auth
import psycopg2
from psycopg2 import sql
import bcrypt
import re
import os
import jwt
import datetime
from dotenv import load_dotenv

load_dotenv()

##AQUI ESTAO OS CODIGOS QUE MEXEM NAS IMAGENS E NO CSS
def get_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def add_bg_from_local(image_path):
    base64_str = get_base64(image_path)
    bg_style = f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{base64_str}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    </style>
    """
    st.markdown(bg_style, unsafe_allow_html=True)

add_bg_from_local("imgs/home.jpg")


st.markdown(
    """
    <style>
        header {visibility: hidden;}
    </style>
    <style>
        [data-testid="stSidebar"] {
            background-color: rgba(0, 0, 0, 0);
        }
    </style>
    <style>
    div.stButton > button:first-child {
        background-color: #8B0000; /* Cor laranja */
        color: white;
        font-size: 16px;
        border-radius: 8px;
        padding: 10px;
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #800000; /* Cor mais escura ao passar o mouse */
    }
    </style>
    """,
    unsafe_allow_html=True
)

##AQUI ESTAO AS CONDICOES PARA AS ROLES

if "role" not in st.session_state:
	st.session_state.role = "Select"

ROLES = ["Selecione", "Conversores Uteis", "Chat com Documentos", "Chat Generativo"]


role =  st.session_state.role


##AQUI ESTAO AS PAGINAS

def login():
	st.header("Vamos comecar!")
	role =  st.selectbox("Escolha seu modelo.", ROLES)
	if st.button("Escolher", use_container_width=True):
		st.session_state.role = role
		st.rerun()

def logout():
	st.session_state.role = "Select"
	st.rerun()

logout_page = st.Page(logout, title="Voltar", icon=":material/logout:")
settings = st.Page("settings.py", title="Profile settings", icon=":material/settings:")

chat_1 = st.Page(
	"chat/chat.py",
	title="Chat para Documentos",
	icon=":material/help:",
	default = (role == 'Chat com Documentos')

)

add_file_1 = st.Page(
        "chat/add_file.py",
        title="Adicionar conhecimento",
        icon=":material/help:",
        
)

my_files_1 = st.Page(
        "chat/meus_arquivos.py",
        title="Meus Arquivos",
        icon=":material/help:",
        
)

conversor_1 = st.Page(
	"conversor_audio/transcribe_audio_in_chunks.py",
	title="Conversor Audio/Texto",
	icon=":material/help:",
	default = (role == "Conversores Uteis")
)

extrator_1 = st.Page(
        "text_extractor/extrator.py",
        title="Conversor Imagem/Texto",
        icon=":material/help:",

)

resumo_1 = st.Page(
        "text_extractor/resumo_inteligente.py",
        title="Conversor Audio/Resumo",
        icon=":material/help:",

)

llm_1 = st.Page(
        "llm_pages/llm_pdf.py",
        title="Conversor Audio/Resumo",
        icon=":material/help:",
	default = (role == "Chat Generativo")
)

# 🔐 Configuração de segurança para JWT
SECRET_KEY = st.secrets["security"]["SECRET_KEY"]

def generate_session_token(email):
    """Gera um token JWT baseado no e-mail do usuário."""
    payload = {
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)  # Expira em 2 horas
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

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

# 🔥 Evita ataques de força bruta com rate limiting
if "login_attempts" not in st.session_state:
    st.session_state["login_attempts"] = {}

def rate_limit(email):
    """Bloqueia o usuário por 5 minutos após 5 tentativas falhas."""
    now = datetime.datetime.utcnow()
    attempts = st.session_state["login_attempts"].get(email, [])

    # Filtra tentativas nos últimos 5 minutos
    attempts = [t for t in attempts if now - t < datetime.timedelta(minutes=5)]
    
    if len(attempts) >= 5:
        return True  # Usuário bloqueado

    st.session_state["login_attempts"][email] = attempts + [now]
    return False

# 🔹 Banco de Dados PostgreSQL
DB_CONFIG = st.secrets["postgresql"]

def connect_db():
    """Conecta ao banco de dados PostgreSQL de forma segura."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None
        
def debit_coins(email, amount):
    """Debita moedas do usuário no banco de dados."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Verificar saldo atual do usuário
        cursor.execute(sql.SQL("SELECT coins FROM users WHERE email = %s"), (email,))
        result = cursor.fetchone()

        if not result:
            st.error("⚠️ Usuário não encontrado.")
            return False

        current_coins = result[0]

        # Verificar se há saldo suficiente
        if current_coins < amount:
            st.warning("⚠️ Saldo insuficiente para realizar esta operação.")
            return False

        # Debitar as moedas
        cursor.execute(sql.SQL("UPDATE users SET coins = %s WHERE email = %s"), (current_coins - amount, email))
        conn.commit()
        return True

    except Exception as e:
        st.error(f"⚠️ Erro ao debitar moedas: {e}")
        return False

    finally:
        if conn:
            conn.close()


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

def hash_password(password):
    """Gera um hash seguro para a senha antes de armazená-la no banco."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()
    


# 🔹 Autenticação Firebase
cred = credentials.Certificate("cognit-ai-users-e77eca71a5c9.json")

if not firebase_admin._apps:  # ✅ Garante que não chamamos initialize_app() duas vezes
    firebase_admin.initialize_app(cred)

# 🔹 Inicializa variáveis de sessão
if "session_token" not in st.session_state:
    st.session_state["session_token"] = None
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None
if "user_uid" not in st.session_state:
    st.session_state["user_uid"] = None


def verify_firebase_password(email, password):
    """Verifica a senha do usuário no Firebase e PostgreSQL."""
    try:
        user = auth.get_user_by_email(email)
        
        with connect_db() as conn:
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT password FROM users WHERE email = %s", (email,))
                    result = cursor.fetchone()
                    
                    if result:
                        stored_hashed_password = result[0]
                        if bcrypt.checkpw(password.encode(), stored_hashed_password.encode()):
                            return user  # ✅ Login válido
        return None  # ❌ Senha incorreta

    except firebase_admin.auth.UserNotFoundError:
        return None  # ❌ Usuário não encontrado
    except Exception as e:
        print(f"Erro na autenticação: {e}")
        return None

def authenticate_user():
    """Autentica o usuário de forma segura."""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.image("imgs/logo.png", use_container_width=True)

        if verify_session():
            email = st.session_state.get("user_email", None)
            if email and "user_coins" not in st.session_state:
                st.session_state["user_coins"] = get_user_coins(email)
            return True

        menu_selection = option_menu(
            menu_title=None,
            options=["Login", "Cadastro"],
            icons=["box-arrow-in-right", "person-plus"],
            default_index=0,
            orientation="horizontal"
        )

        # 🔹 Captura de valores no session_state para evitar inconsistências
        if "email_input" not in st.session_state:
            st.session_state["email_input"] = ""
        if "password_input" not in st.session_state:
            st.session_state["password_input"] = ""

        email = st.text_input("Endereço de E-Mail", value=st.session_state["email_input"], placeholder="Digite seu e-mail")
        password = st.text_input("Senha", value=st.session_state["password_input"], type="password", placeholder="Digite sua senha")

        if menu_selection == "Login":
            def login_user():
                """Executa o login do usuário de forma segura"""
                st.session_state["email_input"] = email
                st.session_state["password_input"] = password
                
                if not email.strip() or not password.strip():
                    st.warning("⚠️ Preencha todos os campos antes de continuar.")
                    return

                if rate_limit(email):
                    st.error("🚫 Muitas tentativas de login! Tente novamente em 5 minutos.")
                    return
                
                try:
                    user = verify_firebase_password(email, password)
                    
                    if user is None:
                        st.warning("⚠️ Usuário ou senha incorretos.")
                        return
                    
                    token = generate_session_token(email)
                    
                    # 🔹 Atualiza a sessão e força atualização imediata
                    st.session_state.update({
                        "session_token": token,
                        "user_email": email,
                        "user_uid": user.uid,
                        "user_coins": get_user_coins(email),
                        "email_input": "",
                        "password_input": ""
                    })
                    
                    st.success("✅ Login realizado com sucesso! Bem-vindo!")
                    
                
                except Exception as e:
                    st.error(f"⚠️ Ocorreu um erro inesperado: {str(e)}")

            st.button("Entrar", on_click=login_user, use_container_width=True)

        else:  # Cadastro de usuário
            username = st.text_input("Nome de usuário", placeholder="Digite seu nome")
            phone = st.text_input("Telefone (com DDD)", placeholder="(11) 98765-4321")

            def create_account():
                """Cria uma conta no Firebase e PostgreSQL."""
                st.session_state["email_input"] = email
                st.session_state["password_input"] = password

                if not username.strip() or not email.strip() or not password.strip() or not phone.strip():
                    st.warning("⚠️ Todos os campos são obrigatórios.")
                    return

                hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

                with connect_db() as conn:
                    if conn:
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute(sql.SQL("SELECT 1 FROM users WHERE email = %s OR username = %s"), (email, username))
                                if cursor.fetchone():
                                    st.error("⚠️ Este e-mail ou nome de usuário já está em uso.")
                                    return

                                cursor.execute(sql.SQL("""
                                    INSERT INTO users (username, email, password, phone, coins) 
                                    VALUES (%s, %s, %s, %s, %s)
                                """), (username, email, hashed_password, phone, 100))
                                conn.commit()

                        except psycopg2.IntegrityError:
                            st.error("⚠️ Erro ao salvar dados. Tente novamente.")
                            conn.rollback()
                            return
                        except Exception as e:
                            st.error(f"⚠️ Erro ao salvar dados: {e}")
                            return

                try:
                    auth.create_user(email=email, password=password, uid=username)
                    
                    # 🔹 Atualiza sessão após cadastro
                    st.session_state.update({
                        "user_email": email,
                        "session_token": generate_session_token(email),
                        "user_uid": username,
                        "user_coins": 100,
                        "email_input": "",
                        "password_input": ""
                    })
                    
                    st.success("✅ Conta criada com sucesso! Faça login agora.")
                    st.balloons()
                    
                
                except firebase_admin.auth.EmailAlreadyExistsError:
                    st.error("⚠️ Este e-mail já está em uso.")
                except firebase_admin.auth.UidAlreadyExistsError:
                    st.error("⚠️ Este nome de usuário já está em uso.")    
                except Exception as e:
                    st.error(f"⚠️ Erro ao criar conta: {e}")

            st.button("Criar Conta", on_click=create_account, use_container_width=True)

    return False
    
if authenticate_user():
    account_pages = [logout_page, settings]
    chat_pages = [chat_1, add_file_1, my_files_1]
    model_pages = [conversor_1, extrator_1]
    llm_pages = [llm_1]

    page_dict = {}
    if st.session_state.role == "Chat com Documentos":
        page_dict["Chat com Documentos"] = chat_pages
    if st.session_state.role == "Chat Generativo":
        page_dict["Chat Generativo"] = llm_pages
    if st.session_state.role == "Conversores Uteis":
        page_dict["Conversores Uteis"] = model_pages

    pg = st.navigation({"Conta": account_pages} | page_dict) if page_dict else st.navigation([st.Page(login)])
    pg.run()

