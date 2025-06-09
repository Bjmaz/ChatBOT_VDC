import streamlit as st
import openai

# Configura tu clave de API
openai.api_key = st.secrets["openai_api_key"]

def preguntar_a_gpt(prompt):
    respuesta = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes cuando se solicita una sugerencia técnica bajo normativa NTP o ISO 9001. Responde de forma clara y breve, máximo 3 líneas."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content

st.set_page_config(page_title="ChatBot VDC", layout="centered")
st.title("🧠 ChatBot VDC - DOSSIER DE CALIDAD")

st.markdown("Completa la información del elemento observado. GPT solo actuará si hay observación técnica.")

with st.form("formulario_elemento"):
    descripcion = st.text_input("🔧 Descripción del elemento")
    especialidad = st.selectbox("🏷️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
    enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
    evidencia = st.text_input("📎 Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
    observacion = st.text_area("⚠️ Observación técnica detectada (dejar vacío si no hay)")
    generar = st.form_submit_button("💡 Generar recomendación")

if generar:
    if descripcion and especialidad:
        if observacion.strip():
            prompt = f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
            respuesta = preguntar_a_gpt(prompt)
            st.success("💡 Recomendación técnica generada:")
            st.markdown(f"**{respuesta}**")
        else:
            st.info("No se ingresó observación. GPT no intervendrá.")
    else:
        st.warning("Por favor completa al menos la descripción y especialidad.")

st.markdown("---")
st.caption("Desarrollado para revisión técnica VDC en sesiones ICE")
