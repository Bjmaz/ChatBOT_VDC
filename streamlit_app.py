import streamlit as st
import openai

# Configura tu clave API desde el entorno de Streamlit
openai.api_key = st.secrets["openai_api_key"]

# Función para preguntar a GPT

def preguntar_a_gpt(prompt):
    respuesta = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo das recomendaciones técnicas cuando hay observaciones o problemas, según normativa NTP e ISO 9001. Tus respuestas deben ser breves (hasta 3 líneas)."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content

# Título
st.set_page_config(page_title="ChatBot VDC", layout="centered")
st.title("\U0001F9E0 ChatBot VDC - DOSSIER DE CALIDAD")

st.markdown("Selecciona el tipo de formato que deseas completar.")
opcion_formato = st.radio("Selecciona una opción:", ["Formato 1: Revisión de Elemento", "Formato 2: Acta de sesión ICE"])

# FORMATO 1: Revisión por elemento
if opcion_formato == "Formato 1: Revisión de Elemento":
    st.subheader("Revisión técnica por elemento")
    with st.form("form_elemento"):
        descripcion = st.text_input("\U0001F527 Descripción del elemento")
        especialidad = st.selectbox("\U0001F3F7️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("\U0001F517 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("\U0001F4CE Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("\u26A0️ Observación técnica detectada (dejar vacío si no hay)")
        comentarios = st.text_area("\U0001F5E3️ Comentarios en sesión ICE")
        acuerdos = st.text_area("\U0001F91D Acuerdos tomados")
        estado = st.selectbox("\u2705 Estado del elemento", ["", "Aprobado", "Observado", "Por Corregir"])
        tiempo_sesion = st.text_input("\u23F0 Duración de la sesión ICE (minutos)")
        generar = st.form_submit_button("\U0001F4A1 Generar recomendación")

    if generar:
        if descripcion and especialidad:
            if observacion.strip():
                prompt = f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere una acción correctiva inmediata y una buena práctica futura (máx 3 líneas, bajo normativa NTP o ISO 9001)."
                respuesta = preguntar_a_gpt(prompt)
                st.success("\U0001F4A1 Recomendación técnica generada:")
                st.markdown(f"**{respuesta}**")
            else:
                st.info("No se ingresó observación. GPT no intervendrá.")

            st.markdown("---")
            st.subheader("\U0001F4CB Resumen del elemento revisado")
            st.markdown(f"**Descripción**: {descripcion}")
            st.markdown(f"**Especialidad**: {especialidad}")
            st.markdown(f"**Evidencia**: {evidencia}")
            st.markdown(f"**Estado**: {estado}")
            st.markdown(f"**Tiempo de sesión**: {tiempo_sesion} minutos")
            st.markdown(f"**Comentarios ICE**: {comentarios}")
            st.markdown(f"**Acuerdos tomados**: {acuerdos}")

            if observacion.strip():
                resumen_ice = f"Elemento: {descripcion}. Observación: {observacion}. Sugiere una recomendación para la próxima sesión ICE. (máx. 3 líneas, NTP)"
                recomendacion = preguntar_a_gpt(resumen_ice)
                st.success("\U0001F4CB Recomendación para próxima sesión ICE:")
                st.markdown(f"**{recomendacion}**")
        else:
            st.warning("Completa al menos descripción y especialidad.")

    st.markdown("---")
    st.caption("Gracias por usar el ChatBOT VDC. Nos vemos en la próxima sesión ICE.")

# FORMATO 2: Acta ICE
if opcion_formato == "Formato 2: Acta de sesión ICE":
    st.subheader("Acta de sesión ICE")
    with st.form("form_ice"):
        proyecto = st.text_input("\U0001F3D7️ Proyecto")
        fecha = st.date_input("\U0001F4C5 Fecha de sesión")
        lider = st.text_input("\U0001F464 Líder de sesión")
        participantes = st.text_area("\U0001F465 Participantes")
        tiempo_sesion = st.text_input("\u23F0 Duración total de la sesión (minutos)")
        temas = st.text_area("\U0001F4DA Temas abordados (y problema si aplica)")
        acuerdos = st.text_area("\U0001F91D Acuerdos finales de sesión")
        generar_acta = st.form_submit_button("\U0001F4A1 Finalizar y generar cierre")

    if generar_acta:
        st.markdown("---")
        st.markdown(f"**Proyecto**: {proyecto}")
        st.markdown(f"**Fecha**: {fecha}")
        st.markdown(f"**Líder**: {lider}")
        st.markdown(f"**Participantes**: {participantes}")
        st.markdown(f"**Duración total**: {tiempo_sesion} minutos")
        st.markdown(f"**Temas abordados**: {temas}")
        st.markdown(f"**Acuerdos**: {acuerdos}")

        if temas.strip():
            resumen_final = f"Temas tratados: {temas}. Redacta una conclusión técnica final para mejorar futuras sesiones ICE. Máx 3 líneas."
            conclusion = preguntar_a_gpt(resumen_final)
            st.success("\U0001F4C6 Conclusión final:")
            st.markdown(f"**{conclusion}**")

        st.markdown("---")
        st.caption("Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión.")

