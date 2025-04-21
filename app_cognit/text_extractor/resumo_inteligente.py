import streamlit as st
import whisper
import os
from pydub import AudioSegment
from pyannote.audio import Pipeline
from openai import OpenAI
from dotenv import load_dotenv

# 🔹 Carregar variáveis de ambiente
load_dotenv()

# 🔹 Configuração de modelos
WHISPER_MODEL = "large-v2"
PYANNOTE_AUTH_TOKEN = st.secrets["PYANNOTE_AUTH_TOKEN"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# 🔹 Inicializar Whisper
whisper_model = whisper.load_model(WHISPER_MODEL)

# 🔹 Inicializar PyAnnote para separação de falantes
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization", use_auth_token=PYANNOTE_AUTH_TOKEN)

# 🔹 Inicializar OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

st.title("🎙️ Conversor de Áudio para Resumo Inteligente & Diálogo Estruturado")

# 🔹 Exibir spinner enquanto carrega os modelos
with st.spinner("🔄 Carregando modelos..."):
    whisper_model = whisper.load_model(WHISPER_MODEL)
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization", use_auth_token=PYANNOTE_AUTH_TOKEN)
    client = OpenAI(api_key=OPENAI_API_KEY)

# 🔹 Upload do arquivo de áudio
uploaded_file = st.file_uploader("Selecione um arquivo de áudio", type=["mp3", "wav", "m4a"])

if uploaded_file:
    file_name = uploaded_file.name
    temp_file_path = f"temp_{file_name}"
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    
    st.audio(uploaded_file, format="audio/mp3")
    
    with st.spinner("🔍 Processando áudio..."):
        # 🔹 Converter para WAV se necessário
        if not file_name.endswith(".wav"):
            audio = AudioSegment.from_file(temp_file_path)
            temp_wav_path = temp_file_path.replace(file_name.split(".")[-1], "wav")
            audio.export(temp_wav_path, format="wav")
            temp_file_path = temp_wav_path
        
        # 🔹 Separação de falantes
        diarization = pipeline(temp_file_path)
        speaker_map = {}
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            if speaker not in speaker_map:
                speaker_map[speaker] = []
            speaker_map[speaker].append((turn.start, turn.end))
        
        # 🔹 Transcrição com Whisper
        result = whisper_model.transcribe(temp_file_path)
        full_transcript = result["text"]
        
        # 🔹 Organizar transcrição por falante
        structured_transcript = ""
        for speaker, segments in speaker_map.items():
            structured_transcript += f"\n**{speaker}:**\n"
            for start, end in segments:
                structured_transcript += f"{full_transcript} [Trecho {start:.2f}s - {end:.2f}s]\n"
        
        st.subheader("📝 Transcrição Estruturada")
        st.text_area("", structured_transcript, height=300)
        
        # 🔹 Gerar resumo inteligente
        with st.spinner("📄 Criando resumo..."):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "Resuma a seguinte transcrição de uma reunião de forma clara e objetiva."},
                          {"role": "user", "content": structured_transcript}]
            )
            resumo = response.choices[0].message.content
        
        st.subheader("📌 Resumo Inteligente")
        st.text_area("", resumo, height=200)
        
        # 🔹 Remover arquivos temporários
        os.remove(temp_file_path)
        if 'temp_wav_path' in locals():
            os.remove(temp_wav_path)
