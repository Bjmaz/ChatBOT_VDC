import streamlit as st
import openai

# Configura tu API Key (se carga desde los secrets del deploy)
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

formato = st.radio("\u2705 Selecciona un formato:", ["Registrar elementos observados (Formato 1)", "Completar acta de sesión ICE (Formato 2)"])

# FORMATO 1
if formato == "Registrar elementos observados (Formato 1)":
    st.markdown("Completa la información del elemento observado. GPT solo actuará si hay observación técnica.")

    with st.form("formato1"):
        descripcion = st.text_input("\ud83d\udd27 Descripción del elemento")
        especialidad = st.selectbox("\ud83c\udff7\ufe0f Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("\ud83d\udd17 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("\ud83d\udcc2 Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("\u26a0\ufe0f Observación técnica detectada (dejar vacío si no hay)")
        generar = st.form_submit_button("\ud83d\udd1d Generar recomendación")

    if generar and descripcion and especialidad:
        st.subheader("\ud83c\udf10 Resultado")
        if observacion.strip():
            prompt = f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere acción correctiva inmediata y buena práctica futura (máximo 3 líneas, bajo normativa NTP o ISO 9001)."
            recomendacion = recomendar_gpt(prompt)
            st.success("\ud83d\udca1 Recomendación técnica:")
            st.markdown(f"**{recomendacion}**")

            with st.expander("\ud83d\udcc4 Completar cierre de sesión por elemento"):
                comentarios = st.text_area("\ud83d\udde3\ufe0f Comentarios en sesión ICE")
                acuerdos = st.text_area("\ud83d\udc4d Acuerdos tomados")
                estado = st.selectbox("\u2705 Estado del elemento", ["Aprobado", "Observado", "Por Corregir"])
                duracion = st.text_input("\u23f1\ufe0f Duración total de la sesión ICE (min)")

                if st.button("\ud83d\uddc4\ufe0f Finalizar revisión de elemento"):
                    st.info("\ud83d\udcca Resumen de elemento:")
                    st.markdown(f"- **Elemento**: {descripcion}\n- **Especialidad**: {especialidad}\n- **Observación**: {observacion}\n- **Recomendación**: {recomendacion}\n- **Estado**: {estado}\n- **Duración de sesión**: {duracion} minutos")

                    resumen_prompt = f"Elemento: {descripcion}, observación: {observacion}. Redacta recomendación corta para debatir en la próxima sesión ICE bajo norma peruana NTP. Máximo 3 líneas."
                    cierre = recomendar_gpt(resumen_prompt)
                    st.success("\ud83d\udcc6 Recomendación final para próxima ICE:")
                    st.markdown(f"**{cierre}**")
                    st.markdown("\n\u2728 Gracias por usar el ChatBOT VDC. ¡Nos vemos en la próxima revisión del Formato 2!")
        else:
            st.info("No se ingresó observación técnica. GPT no generará recomendación.")

# FORMATO 2
else:
    st.markdown("Completa el acta técnica de sesión ICE. Se generarán recomendaciones solo si hay problemas registrados.")

    with st.form("formato2"):
        proyecto = st.text_input("\ud83c\udfe0 Proyecto")
        fecha = st.text_input("\ud83d\uddd3\ufe0f Fecha de sesión")
        lider = st.text_input("\ud83d\udc64 Líder de sesión")
        participantes = st.text_area("\ud83d\udc65 Participantes")

        tema = st.text_input("\ud83d\udcc2 Tema abordado")
        problema = st.text_area("\u26a0\ufe0f Problema del tema (dejar vacío si no hay)")
        generar_tema = st.form_submit_button("\ud83d\udcda Generar recomendación del tema")

    if generar_tema:
        if problema.strip():
            prompt_tema = f"Tema: {tema}. Problema detectado: {problema}. Redacta una recomendación breve para proponer durante la sesión ICE. Máximo 3 líneas."
            recomendacion_tema = recomendar_gpt(prompt_tema)
            st.success("\ud83d\udcda Recomendación para el tema:")
            st.markdown(f"**{recomendacion_tema}**")

        with st.expander("\ud83d\udd1d Completar cierre de sesión ICE"):
            acuerdos_finales = st.text_area("\ud83d\udccd Acuerdos finales")
            duracion_sesion = st.text_input("\u23f1\ufe0f Duración de la sesión (min)")
            if st.button("\ud83d\uddc4\ufe0f Finalizar Acta ICE"):
                st.info("\ud83d\udcca Resumen del acta:")
                st.markdown(f"- **Proyecto**: {proyecto}\n- **Fecha**: {fecha}\n- **Líder**: {lider}\n- **Tema**: {tema}\n- **Problema**: {problema if problema else 'Sin problema'}\n- **Duración**: {duracion_sesion} min")
                cierre_ice = f"Tema: {tema}, acuerdos: {acuerdos_finales}. Redacta conclusión técnica breve para mejorar futuras sesiones ICE. Máximo 3 líneas."
                conclusion = recomendar_gpt(cierre_ice)
                st.success("\ud83d\udd2c Conclusión final:")
                st.markdown(f"**{conclusion}**")
                st.markdown("\n\u2728 Gracias por usar el ChatBOT VDC. ¡Tu revisión colaborativa ha sido registrada!")
