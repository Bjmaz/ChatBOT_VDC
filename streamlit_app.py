import streamlit as st
import openai

# Configura tu clave de API (se obtiene de los secrets del deploy)
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
st.title("\U0001F9E0 ChatBot VDC - DOSSIER DE CALIDAD")

formato = st.radio("\U0001F4CC Selecciona un formato:", ["Registrar elementos observados (Formato 1)", "Completar acta de sesión ICE (Formato 2)"])

if formato == "Registrar elementos observados (Formato 1)":
    st.header("Completa la información Técnica del elemento observado")

    elementos = st.session_state.get("elementos", [])

    with st.form("form_elemento"):
        proyecto = st.text_input("🏗️ Proyecto")
        descripcion = st.text_input("🛠️ Descripción del elemento (Ejm. Tubería Agua fría)")
        especialidad = st.selectbox("✍️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("⚙️ Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("⚠️ Observación técnica detectada")
        agregar = st.form_submit_button("➕ Agregar elemento")

        if agregar and descripcion and especialidad:
            elementos.append({
                "descripcion": descripcion,
                "especialidad": especialidad,
                "enlace": enlace,
                "evidencia": evidencia,
                "observacion": observacion
            })
            st.session_state.elementos = elementos
            st.success("Elemento agregado con éxito.")

    if elementos:
        st.subheader("Elementos registrados:")
        for idx, elem in enumerate(elementos):
            st.markdown(f"**{idx+1}.** {elem['descripcion']} ({elem['especialidad']})")

        if st.button("🔹 Generar recomendaciones"):
            for idx, elem in enumerate(elementos):
                if elem['observacion']:
                    prompt = f"Elemento: {elem['descripcion']} ({elem['especialidad']}). Enlace: {elem['enlace']}. Evidencia: {elem['evidencia']}. Observación: {elem['observacion']}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
                    respuesta = recomendar_gpt(prompt)
                    st.markdown(f"**Recomendación para elemento {idx+1}:** {respuesta}")

            st.session_state.generado = True

    if st.session_state.get("generado"):
        st.header("✅ Información final de sesión ICE")
        comentarios = st.text_area("🗣️ Comentarios en sesión ICE")
        acuerdos = st.text_area("👍 Acuerdos tomados")
        estado = st.selectbox("✅ Estado del elemento", ["", "Aprobado", "Observado", "Por Corregir"])
        duracion = st.text_input("⏱️ Duración total de la sesión ICE (minutos)")
        responsable = st.text_input("👨‍💼 Responsable de validación")
        fecha_proxima = st.date_input("🗓️ Fecha de próxima revisión")

        if st.button("🔹 Generar resumen final y recomendación"):
            for idx, elem in enumerate(elementos):
                prompt = f"Elemento: {elem['descripcion']} ({elem['especialidad']}). Observación: {elem['observacion']}. Proyecto: {proyecto}. Sugiere una recomendación breve para debatir en próxima sesión ICE (NTP o ISO9001, máximo 3 líneas)."
                resultado = recomendar_gpt(prompt)
                st.markdown(f"**Recomendación final para elemento {idx+1}:** {resultado}")

            st.markdown("---")
            st.subheader("🔢 Resumen final ingresado por el usuario")
            st.markdown(f"**Proyecto:** {proyecto}")
            st.markdown(f"**Duración:** {duracion} minutos")
            st.markdown(f"**Responsable validación:** {responsable}")
            st.markdown(f"**Fecha próxima revisión:** {fecha_proxima}")
            st.markdown(f"**Estado del elemento:** {estado}")
            st.markdown(f"**Comentarios:** {comentarios}")
            st.markdown(f"**Acuerdos:** {acuerdos}")

            st.success("Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión del Formato 2.")

elif formato == "Completar acta de sesión ICE (Formato 2)":
    st.header("📄 Completar acta de sesión ICE Técnica")
    with st.form("form_ice"):
        proyecto = st.text_input("🛠 Proyecto")
        fecha = st.date_input("📅 Fecha de sesión")
        lider = st.text_input("🧑‍💼 Líder de sesión")
        participantes = st.text_area("👥 Participantes")
        tema = st.text_input("📂 Tema abordado")
        problema = st.text_area("⚠️ Problema abordado (dejar vacío si no hubo)")
        enviar = st.form_submit_button("💡 Generar sugerencia técnica")

        if enviar and problema:
            prompt = f"Tema: {tema}. Problema: {problema}. Sugiere una acción inmediata o recomendación corta según norma peruana NTP o ISO 9001 (3 líneas máximo)."
            respuesta = recomendar_gpt(prompt)
            st.success(f"Recomendación técnica: {respuesta}")
            st.session_state.tema_listo = True

    if st.session_state.get("tema_listo"):
        st.subheader("✅ Finaliza el acta técnica")
        acuerdos_ice = st.text_area("🤝 Acuerdos finales en sesión ICE")
        duracion = st.text_input("⏱️ Duración total de la sesión ICE (minutos)")
        responsable = st.text_input("👤 Responsable de validación")

        if st.button("📄 Generar conclusión final"):
            prompt = f"Proyecto: {proyecto}. Tema: {tema}. Problema: {problema}. Acuerdos: {acuerdos_ice}. Duración: {duracion}. Sugiere una conclusión final para mejorar futuras sesiones ICE."
            final = recomendar_gpt(prompt)
            st.markdown(f"**Conclusión técnica:** {final}")

            st.markdown("---")
            st.subheader("🧾 Resumen final del usuario")
            st.markdown(f"**Proyecto:** {proyecto}")
            st.markdown(f"**Fecha:** {fecha}")
            st.markdown(f"**Participantes:** {participantes}")
            st.markdown(f"**Tema:** {tema}")
            st.markdown(f"**Problema:** {problema}")
            st.markdown(f"**Acuerdos:** {acuerdos_ice}")
            st.markdown(f"**Duración:** {duracion} minutos")
            st.markdown(f"**Validado por:** {responsable}")

            st.success("Gracias por usar el ChatBOT VDC. Tu sesión ICE ha sido registrada con éxito.")
