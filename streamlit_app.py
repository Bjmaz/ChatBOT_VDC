import streamlit as st
import openai

# Configura tu API Key de forma segura desde Streamlit Cloud
openai.api_key = st.secrets["openai_api_key"]

def recomendar_gpt(prompt):
    response = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes cuando se solicita una sugerencia técnica bajo normativa NTP o ISO 9001. Responde de forma clara y breve, máximo 3 líneas."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

st.set_page_config(page_title="ChatBot VDC - Revisión Técnica", layout="centered")
st.title("🧠 ChatBot VDC - DOSSIER DE CALIDAD")

formato = st.radio("📌 Selecciona un formato:", ["Registrar elementos observados (Formato 1)", "Completar acta de sesión ICE (Formato 2)"])

# ===== FORMATO 1 =====
if formato == "Registrar elementos observados (Formato 1)":
    if "elementos" not in st.session_state:
        st.session_state.elementos = []

    with st.form("form_elemento"):
        st.subheader("Completa la información Técnica del elemento observado")
        descripcion = st.text_input("🔧 Descripción del elemento")
        especialidad = st.selectbox("🏷️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("📎 Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("⚠️ Observación técnica detectada (dejar vacío si no hay)")
        submit1 = st.form_submit_button("💡 Generar recomendación")

    if submit1 and descripcion and especialidad:
        if observacion.strip():
            prompt = f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
            respuesta = recomendar_gpt(prompt)
            st.success("💡 Recomendación técnica generada:")
            st.markdown(f"**{respuesta}**")
        else:
            st.info("No se ingresó observación. GPT no intervendrá.")

        st.session_state.elementos.append({
            "descripcion": descripcion,
            "especialidad": especialidad,
            "enlace": enlace,
            "evidencia": evidencia,
            "observacion": observacion
        })

    if len(st.session_state.elementos) > 0:
        st.subheader("📋 Información posterior a la revisión:")
        comentarios = st.text_area("🗣️ Comentarios en sesión ICE")
        acuerdos = st.text_area("🤝 Acuerdos tomados")
        estado = st.selectbox("✅ Estado del elemento", ["Aprobado", "Observado", "Por Corregir"])
        duracion = st.text_input("⏱️ Duración de la sesión (ej. 45 minutos)")

        if st.button("✅ Finalizar revisión de elementos"):
            st.markdown("---")
            st.subheader("📌 Resumen del elemento(s):")
            for i, e in enumerate(st.session_state.elementos, 1):
                st.markdown(f"**Elemento {i}:** {e['descripcion']} ({e['especialidad']}) — Observación: {e['observacion'] or 'Ninguna'}")

            st.subheader("💡 Recomendaciones para próxima sesión ICE:")
            for e in st.session_state.elementos:
                if e["observacion"]:
                    prompt = f"Elemento: {e['descripcion']} ({e['especialidad']}) con observación: {e['observacion']}. Redacta una recomendación técnica breve para debatir en la próxima sesión ICE, bajo normativa peruana NTP (máximo 3 líneas)."
                    st.markdown(f"- **{recomendar_gpt(prompt)}**")

            st.success("✅ Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión del Formato 2.")

# ===== FORMATO 2 =====
elif formato == "Completar acta de sesión ICE (Formato 2)":
    st.subheader("🧾 Completar acta de sesión ICE Técnica")
    with st.form("form_ice"):
        proyecto = st.text_input("🏗️ Proyecto")
        fecha = st.text_input("📅 Fecha de sesión")
        lider = st.text_input("👤 Líder de sesión")
        participantes = st.text_area("👥 Participantes")
        duracion_ice = st.text_input("⏱️ Duración de la sesión ICE")

        tema = st.text_input("🗂️ Tema abordado")
        problema = st.text_area("⚠️ Problema abordado (dejar vacío si no hubo)")
        acuerdos_finales = st.text_area("🤝 Acuerdos finales tomados")

        submit2 = st.form_submit_button("💡 Generar resumen y conclusión")

    if submit2:
        st.markdown("---")
        st.subheader("📋 Resumen del acta registrada:")
        st.markdown(f"**Proyecto:** {proyecto}")
        st.markdown(f"**Fecha:** {fecha}")
        st.markdown(f"**Líder:** {lider}")
        st.markdown(f"**Participantes:** {participantes}")
        st.markdown(f"**Duración:** {duracion_ice}")
        st.markdown(f"**Tema:** {tema}")
        st.markdown(f"**Problema:** {problema or 'Ninguno'}")
        st.markdown(f"**Acuerdos:** {acuerdos_finales}")

        if problema.strip():
            prompt = f"Tema: {tema}. Problema: {problema}. Redacta una recomendación técnica breve y aplicable, bajo normativa NTP."
            st.success("💡 Recomendación:")
            st.markdown(f"**{recomendar_gpt(prompt)}**")

        cierre_prompt = f"Duración: {duracion_ice}. Tema tratado: {tema}. Problema detectado: {problema}. Acuerdos tomados: {acuerdos_finales}. Redacta una conclusión técnica breve para mejorar futuras sesiones ICE."
        cierre = recomendar_gpt(cierre_prompt)
        st.success("📌 Conclusión final:")
        st.markdown(f"**{cierre}**")
