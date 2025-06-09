import streamlit as st
import openai

# Configura tu API Key (desde secrets)
openai.api_key = st.secrets["openai_api_key"]

# Función GPT para generar respuestas técnicas

def recomendar_gpt(prompt):
    respuesta = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes cuando se solicita una sugerencia técnica bajo normativa NTP o ISO 9001. Responde de forma clara y breve, máximo 3 líneas."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content

st.set_page_config(page_title="ChatBot VDC - Revisión Técnica", layout="centered")
st.title("\U0001F9E0 ChatBot VDC - DOSSIER DE CALIDAD")

formato = st.radio("\U0001F4CC Selecciona un formato:", ["Registrar elementos observados (Formato 1)", "Completar acta de sesión ICE (Formato 2)"])

# -----------------------------------
# FORMATO 1 - Revisión por Elemento
# -----------------------------------
if formato == "Registrar elementos observados (Formato 1)":
    st.header("Completa la información Técnica del elemento observado")
    with st.form("formato_1"):
        desc = st.text_input("\U0001F528 Descripción del elemento")
        esp = st.selectbox("\U0001F58A Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("\U0001F517 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("⚖ Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        obs = st.text_area("\u26A0 Observación técnica detectada (dejar vacío si no hay)")
        generar = st.form_submit_button("\U0001F4A1 Generar recomendación")

    if generar and desc and esp:
        if obs.strip():
            prompt = f"Elemento: {desc} ({esp}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {obs}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
            recomendacion = recomendar_gpt(prompt)
            st.success("\U0001F4A1 Recomendación técnica:")
            st.markdown(f"**{recomendacion}**")

            with st.form("cierre_elemento"):
                comentarios = st.text_area("\U0001F5E3 Comentarios finales en sesión ICE")
                acuerdos = st.text_area("\U0001F91D Acuerdos tomados")
                estado = st.selectbox("\u2705 Estado del elemento", ["Aprobado", "Observado", "Por Corregir"])
                duracion = st.text_input("\u23F1 Duración total de la sesión ICE")
                responsable = st.text_input("\U0001F464 Responsable de validación")
                fecha_prox = st.date_input("\U0001F4C5 Fecha de próxima revisión")
                cerrar = st.form_submit_button("\u274C Finalizar elemento")

            if cerrar:
                resumen = f"Elemento: {desc}\nEspecialidad: {esp}\nObservación: {obs}\nComentarios: {comentarios}\nAcuerdos: {acuerdos}\nEstado: {estado}\nDuración: {duracion}\nValida: {responsable}\nPróxima Revisión: {fecha_prox}"
                st.markdown("---")
                resumen_final = f"Para el elemento '{desc}', redacta una recomendación técnica muy breve para debatir en la próxima sesión ICE, según NTP o ISO9001."
                cierre_gpt = recomendar_gpt(resumen_final)
                st.success("\U0001F4DD Recomendación para siguiente sesión:")
                st.markdown(f"**{cierre_gpt}**")
                st.markdown("---")
                st.info(f"**Resumen registrado:**\n\n{resumen}")
                st.success("\u2705 Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión del Formato 2.")

# -----------------------------------
# FORMATO 2 - Acta de sesión ICE
# -----------------------------------
elif formato == "Completar acta de sesión ICE (Formato 2)":
    st.header("\U0001F4D3 Completar acta de sesión ICE Técnica")
    with st.form("formato_2"):
        proyecto = st.text_input("\U0001F3E0 Proyecto")
        fecha_sesion = st.date_input("\U0001F4C5 Fecha de sesión")
        lider = st.text_input("\U0001F464 Líder de sesión")
        participantes = st.text_area("\U0001F465 Participantes")
        duracion_ice = st.text_input("\u23F0 Duración de la sesión ICE")
        tema = st.text_input("\U0001F4C4 Tema abordado")
        problema = st.text_area("\u26A0 Problema abordado (dejar vacío si no hubo)")
        generar2 = st.form_submit_button("\U0001F4A1 Generar sugerencia por tema")

    if generar2:
        if problema.strip():
            prompt2 = f"Tema: {tema}. Problema: {problema}. Sugiere una acción técnica breve que el usuario pueda proponer en sesión ICE. Norma NTP o ISO9001."
            sugerencia = recomendar_gpt(prompt2)
            st.success("\U0001F4A1 Recomendación técnica por problema:")
            st.markdown(f"**{sugerencia}**")

            with st.form("cierre_acta"):
                acuerdos_ice = st.text_area("\U0001F91D Acuerdos finales tomados")
                validador = st.text_input("\U0001F464 Responsable de validación")
                cerrar_acta = st.form_submit_button("\U0001F4CB Finalizar Acta ICE")

            if cerrar_acta:
                acta = f"Proyecto: {proyecto}\nLíder: {lider}\nParticipantes: {participantes}\nDuración: {duracion_ice}\nTema: {tema}\nProblema: {problema}\nAcuerdos: {acuerdos_ice}\nValidado por: {validador}"
                cierre2 = f"Acta para proyecto '{proyecto}', acuerdos sobre tema '{tema}'. Redacta una conclusión técnica breve para mejorar futuras sesiones ICE."
                conclusion = recomendar_gpt(cierre2)
                st.success("\U0001F4AC Conclusión de la sesión ICE:")
                st.markdown(f"**{conclusion}**")
                st.markdown("---")
                st.info(f"**Resumen registrado:**\n\n{acta}")
                st.success("\u2705 Gracias por usar el ChatBOT VDC. Revisión finalizada.")
