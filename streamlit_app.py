import streamlit as st
import openai

# Configuración de clave de API
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

# --- FORMATO 1 ---
if formato == "Registrar elementos observados (Formato 1)":
    st.header("🛠️ Completa la información Técnica del elemento observado")

    if "elementos" not in st.session_state:
        st.session_state.elementos = []

    if "proyecto_f1" not in st.session_state:
        st.session_state.proyecto_f1 = st.text_input("🏗️ Proyecto")

    with st.form("form_elemento"):
        descripcion = st.text_input("🔧 Descripción del elemento")
        especialidad = st.selectbox("✍️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("⚙️ Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("⚠️ Observación técnica detectada")
        agregar = st.form_submit_button("➕ Agregar elemento")

        if agregar and descripcion and especialidad:
            st.session_state.elementos.append({
                "descripcion": descripcion,
                "especialidad": especialidad,
                "enlace": enlace,
                "evidencia": evidencia,
                "observacion": observacion
            })
            st.success("Elemento agregado correctamente.")

    if st.session_state.elementos:
        st.subheader("📌 Elementos registrados:")
        for idx, elem in enumerate(st.session_state.elementos):
            st.markdown(f"**{idx+1}.** {elem['descripcion']} ({elem['especialidad']})")

        if st.button("💡 Generar recomendaciones"):
            for idx, elem in enumerate(st.session_state.elementos):
                if elem['observacion']:
                    prompt = f"Elemento: {elem['descripcion']} ({elem['especialidad']}). Enlace: {elem['enlace']}. Evidencia: {elem['evidencia']}. Observación: {elem['observacion']}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
                    respuesta = recomendar_gpt(prompt)
                    st.markdown(f"**Recomendación para elemento {idx+1}:** {respuesta}")
            st.session_state.f1_recomendado = True

    if st.session_state.get("f1_recomendado"):
        st.subheader("📋 Información final tras sesión ICE")
        acuerdos = st.text_area("🤝 Acuerdos finales de la sesión ICE")
        estado = st.selectbox("✅ Estado general del elemento", ["", "Aprobado", "Observado", "Por Corregir"])
        duracion = st.text_input("⏱️ Duración total de la sesión ICE (minutos)")
        responsable = st.text_input("👤 Responsable de validación")
        fecha_proxima = st.date_input("📅 Fecha de próxima revisión")

        if st.button("📄 Generar resumen y recomendación final"):
            for idx, elem in enumerate(st.session_state.elementos):
                prompt = f"Elemento: {elem['descripcion']} ({elem['especialidad']}). Observación: {elem['observacion']}. Proyecto: {st.session_state.proyecto_f1}. Sugiere una recomendación breve para debatir en próxima sesión ICE (NTP o ISO9001, máximo 3 líneas)."
                final = recomendar_gpt(prompt)
                st.markdown(f"**Recomendación final para elemento {idx+1}:** {final}")

            st.markdown("---")
            st.subheader("📑 Resumen final del usuario")
            st.markdown(f"**Proyecto:** {st.session_state.proyecto_f1}")
            st.markdown(f"**Duración:** {duracion} minutos")
            st.markdown(f"**Validado por:** {responsable}")
            st.markdown(f"**Fecha próxima revisión:** {fecha_proxima}")
            st.markdown(f"**Estado general:** {estado}")
            st.markdown(f"**Acuerdos:** {acuerdos}")
            st.success("Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión del Formato 2.")

# --- FORMATO 2 ---
elif formato == "Completar acta de sesión ICE (Formato 2)":
    st.header("📄 Completar acta de sesión ICE Técnica")

    if "temas" not in st.session_state:
        st.session_state.temas = []

    with st.form("form_ice_1"):
        proyecto = st.text_input("🛠 Proyecto")
        fecha = st.date_input("📅 Fecha de sesión")
        lider = st.text_input("👨‍💼 Líder de sesión")
        participantes = st.text_area("👥 Participantes")
        tema = st.text_input("📂 Tema abordado")
        problema = st.text_area("⚠️ Problema abordado (dejar vacío si no hubo)")
        agregar_tema = st.form_submit_button("➕ Agregar tema")

        if agregar_tema and tema:
            st.session_state.temas.append({
                "tema": tema,
                "problema": problema
            })
            st.session_state.proyecto_f2 = proyecto
            st.session_state.fecha_f2 = fecha
            st.session_state.lider_f2 = lider
            st.session_state.participantes_f2 = participantes
            st.success("Tema agregado correctamente.")

    if st.session_state.temas:
        st.subheader("📌 Temas registrados:")
        for idx, t in enumerate(st.session_state.temas):
            st.markdown(f"**{idx+1}.** {t['tema']}")

        if st.button("💡 Generar sugerencias por tema"):
            for idx, t in enumerate(st.session_state.temas):
                if t["problema"]:
                    prompt = f"Tema: {t['tema']}. Problema: {t['problema']}. Sugiere una acción inmediata o recomendación corta según norma peruana NTP o ISO 9001 (2 líneas máximo)."
                    respuesta = recomendar_gpt(prompt)
                    st.markdown(f"**Recomendación para tema {idx+1}:** {respuesta}")
            st.session_state.f2_recomendado = True

    if st.session_state.get("f2_recomendado"):
        st.subheader("📋 Información final")
        acuerdos_ice = st.text_area("🤝 Acuerdos finales en sesión ICE")
        duracion = st.text_input("⏱️ Duración total de la sesión ICE (minutos)")
        responsable = st.text_input("👤 Responsable de validación")

        if st.button("📄 Generar conclusión final"):
            prompt = f"Proyecto: {st.session_state.proyecto_f2}. Acuerdos: {acuerdos_ice}. Duración: {duracion}. Sugiere una conclusión técnica breve para mejorar futuras sesiones ICE."
            final = recomendar_gpt(prompt)
            st.markdown(f"**Conclusión técnica:** {final}")

            st.markdown("---")
            st.subheader("📑 Resumen final del usuario")
            st.markdown(f"**Proyecto:** {st.session_state.proyecto_f2}")
            st.markdown(f"**Fecha:** {st.session_state.fecha_f2}")
            st.markdown(f"**Participantes:** {st.session_state.participantes_f2}")
            st.markdown(f"**Validado por:** {responsable}")
            st.markdown(f"**Duración:** {duracion} minutos")
            st.markdown(f"**Acuerdos:** {acuerdos_ice}")
            st.success("Gracias por usar el ChatBOT VDC. Tu sesión ICE ha sido registrada con éxito.")
