import streamlit as st
import openai

# Configurar la clave de API
openai.api_key = st.secrets["openai_api_key"]

# Función para consultar a GPT

def preguntar_a_gpt(prompt):
    respuesta = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes cuando se solicita una recomendación técnica bajo normativa peruana NTP o ISO 9001. Responde con máximo 3 líneas."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content

# Estado inicial
if "elementos" not in st.session_state:
    st.session_state.elementos = []
    st.session_state.etapa = "registro"

# Título principal y selector de formato
st.title("\U0001F9E0 ChatBot VDC - DOSSIER DE CALIDAD")
opcion = st.radio("", ["\u2705 Registrar elementos observados (Formato 1)", "○ Completar acta de sesión ICE (Formato 2)"])

if opcion == "\u2705 Registrar elementos observados (Formato 1)":
    if st.session_state.etapa == "registro":
        with st.form("form_elemento"):
            descripcion = st.text_input("\U0001F528 Descripción del elemento")
            especialidad = st.selectbox("\U0001F3F7\uFE0F Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
            enlace = st.selectbox("\U0001F517 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
            evidencia = st.text_input("\U0001F4C8 Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
            observacion = st.text_area("\u26A0\uFE0F Observación técnica detectada (requerida para generar recomendación)")
            generar = st.form_submit_button("\U0001F4A1 Generar recomendación")

        if generar:
            if descripcion and especialidad and observacion.strip():
                prompt = f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
                recomendacion = preguntar_a_gpt(prompt)
                st.success("\U0001F4A1 Recomendación técnica generada:")
                st.markdown(f"**{recomendacion}**")

                st.session_state.elementos.append({
                    "descripcion": descripcion,
                    "especialidad": especialidad,
                    "observacion": observacion,
                    "recomendacion": recomendacion
                })
            else:
                st.warning("Por favor completa descripción, especialidad y observación para generar recomendación.")

        if st.button("\U0001F504 Finalizar revisión de elementos"):
            st.session_state.etapa = "resumen"

    elif st.session_state.etapa == "resumen":
        st.subheader("\U0001F4DD Resumen de revisión técnica")
        for i, el in enumerate(st.session_state.elementos):
            st.markdown(f"**{i+1}.** {el['especialidad']}: {el['descripcion']}\n- \U0001F4AC Observación: {el['observacion']}\n- \U0001F4A1 Recomendación: {el['recomendacion']}")

        st.divider()
        st.subheader("\U0001F4CB Datos de cierre de sesión")
        comentarios = st.text_area("\U0001F5E3\uFE0F Comentarios finales en sesión ICE")
        acuerdos = st.text_area("\U0001F91D Acuerdos tomados")
        estado = st.selectbox("\u2705 Estado general de los elementos", ["Aprobado", "Observado", "Por Corregir"])
        duracion = st.text_input("\u23F1 Duración de la sesión ICE (ej. 45 minutos)")

        if st.button("\U0001F91D Generar cierre y despedida"):
            resumen = "\n".join([f"- {el['especialidad']}: {el['descripcion']} → {el['observacion']}" for el in st.session_state.elementos])
            prompt = f"Con base en los siguientes elementos observados:\n{resumen}. Redacta una recomendación técnica breve por elemento para debatir en la próxima sesión ICE, bajo normativa peruana NTP. Máximo 3 líneas por recomendación."
            respuesta = preguntar_a_gpt(prompt)

            st.success("\U0001F4C6 Recomendaciones para próxima sesión ICE:")
            st.markdown(respuesta)
            st.markdown(f"\n\n**Duración de la sesión:** {duracion}")
            st.markdown("\n\n**Gracias por usar el ChatBOT VDC. Nos vemos en la próxima revisión (Formato 2).**")
