import streamlit as st
import openai

# Configuración de API Key
openai.api_key = st.secrets["openai_api_key"]

# Función para preguntar a GPT
def preguntar_a_gpt(prompt):
    respuesta = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes cuando se solicita una sugerencia técnica bajo normativa NTP o ISO 9001. Responde de forma clara y breve, máximo 3 líneas."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content

# Configuración de la página
st.set_page_config(page_title="ChatBot VDC", layout="centered")
st.title("🧠 ChatBot VDC - DOSSIER DE CALIDAD")

# Menú de elección inicial
opcion = st.radio("¿Qué deseas hacer?", ["Selecciona una opción", "✅ Registrar elementos observados (Formato 1)", "📋 Completar acta de sesión ICE (Formato 2)"])

# FORMATO 1: Revisión de elementos observados
if opcion == "✅ Registrar elementos observados (Formato 1)":
    st.markdown("Completa la información del elemento observado. GPT solo actuará si hay observación técnica.")
    with st.form("form_elemento"):
        descripcion = st.text_input("🔧 Descripción del elemento")
        especialidad = st.selectbox("🏷️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("📎 Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("⚠️ Observación técnica detectada (dejar vacío si no hay)")
        comentarios = st.text_area("🗣️ Comentarios en sesión ICE")
        acuerdos = st.text_area("🤝 Acuerdos tomados")
        estado = st.selectbox("✅ Estado del elemento", ["", "Aprobado", "Observado", "Por Corregir"])
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
        st.caption("Gracias por usar el ChatBOT VDC. Tu revisión colaborativa ha sido registrada con éxito.")

# FORMATO 2: Acta de sesión ICE
elif opcion == "📋 Completar acta de sesión ICE (Formato 2)":
    st.markdown("Completa el acta de sesión técnica ICE. GPT solo redactará una conclusión final para futuras sesiones.")
    with st.form("form_ice"):
        proyecto = st.text_input("🏗️ Proyecto")
        fecha = st.date_input("📅 Fecha de sesión")
        lider = st.text_input("👤 Líder de sesión")
        participantes = st.text_area("👥 Participantes")
        agenda = st.text_area("🗂️ Temas abordados")
        acuerdos_ice = st.text_area("🤝 Acuerdos de la sesión")
        generar_ice = st.form_submit_button("📌 Generar conclusión final")

    if generar_ice:
        cierre = f"Temas: {agenda}. Acuerdos: {acuerdos_ice}. Redacta una conclusión técnica breve y una recomendación para mejorar futuras sesiones ICE. Máximo 3 líneas."
        respuesta = preguntar_a_gpt(cierre)
        st.success("📌 Conclusión final generada:")
        st.markdown(f"**{respuesta}**")
        st.markdown("---")
        st.caption("Gracias por usar el ChatBOT VDC. Tu revisión colaborativa ha sido registrada con éxito.")
