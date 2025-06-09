import streamlit as st
import openai

st.set_page_config(page_title="ChatBot VDC - Formato 1", layout="centered")
st.title("📋 Formato 1 - Evaluación Técnica por Elemento")

# Configura tu clave API
openai.api_key = st.secrets["openai_api_key"]

# Almacenamiento en sesión
if "elementos" not in st.session_state:
    st.session_state.elementos = []
if "mostrar_campos_finales" not in st.session_state:
    st.session_state.mostrar_campos_finales = False

# Formulario de ingreso por elemento
st.subheader("🔧 Registro de Elemento Observado")
nombre_proyecto = st.text_input("🏗️ Nombre del proyecto", key="nombre_proyecto")
descripcion = st.text_input("Descripción del elemento")
especialidad = st.selectbox("Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
enlace = st.selectbox("Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
evidencia = st.text_input("Tipo de evidencia visual")
observacion = st.text_area("Observación técnica detectada (obligatoria si desea recomendación)")

if st.button("➕ Agregar elemento"):
    if descripcion and especialidad:
        st.session_state.elementos.append({
            "descripcion": descripcion,
            "especialidad": especialidad,
            "enlace": enlace,
            "evidencia": evidencia,
            "observacion": observacion
        })
        st.success("Elemento agregado correctamente.")
    else:
        st.warning("Debe completar al menos la descripción y especialidad para agregar el elemento.")

# Mostrar elementos agregados
if st.session_state.elementos:
    st.subheader("🧾 Elementos registrados")
    for idx, elem in enumerate(st.session_state.elementos, 1):
        st.markdown(f"**Elemento {idx}:** {elem['descripcion']} ({elem['especialidad']})")

    # Botón para generar recomendaciones por elemento
    if st.button("💡 Generar recomendaciones técnicas"):
        recomendaciones = []
        for elem in st.session_state.elementos:
            if elem['observacion'].strip():
                prompt = f"Elemento: {elem['descripcion']} ({elem['especialidad']}). Enlace: {elem['enlace']}. Evidencia: {elem['evidencia']}. Observación: {elem['observacion']}. Sugiere una acción correctiva inmediata (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
                respuesta = openai.chat.completions.create(
                    model="gpt-4-1106-preview",
                    messages=[
                        {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes con recomendaciones técnicas bajo normativa NTP o ISO 9001, de forma clara, breve y precisa en máximo 3 líneas."},
                        {"role": "user", "content": prompt}
                    ]
                )
                recomendaciones.append(respuesta.choices[0].message.content)
            else:
                recomendaciones.append("No se ingresó observación técnica. GPT no interviene.")

        st.subheader("📌 Recomendaciones por elemento")
        for i, rec in enumerate(recomendaciones, 1):
            st.markdown(f"**Elemento {i}:** {rec}")

        st.session_state.mostrar_campos_finales = True

# Campos adicionales finales (habilitados luego de generar recomendaciones)
if st.session_state.mostrar_campos_finales:
    st.subheader("📝 Información Final de la Sesión ICE")
    acuerdos = st.text_area("📍 Acuerdos finales de sesión ICE (por cada elemento, indicar acuerdos logrados)")
    estado = st.selectbox("📊 Estado del elemento", ["Aprobado", "Observado", "Por corregir"])
    duracion = st.text_input("⏱️ Duración total de la sesión ICE (minutos)")
    responsable = st.text_input("👤 Nombre del responsable de validación")
    fecha_revision = st.date_input("📅 Fecha de próxima revisión técnica")

    if st.button("🧠 Generar síntesis final y cerrar"):
        resumen_final = "\n".join([
            f"Elemento {i+1}: {el['descripcion']} ({el['especialidad']})\nAcción: {recomendaciones[i]}"
            for i, el in enumerate(st.session_state.elementos)
        ])
        prompt_final = f"Basado en los siguientes elementos observados y acuerdos finales: {resumen_final}. Redacta una recomendación técnica súper breve para debatir en la próxima sesión ICE, según NTP o ISO 9001."

        recomendacion_final = openai.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": "Eres un asistente técnico VDC. Solo das recomendaciones muy breves según normativa técnica peruana e ISO 9001 para futura sesión ICE."},
                {"role": "user", "content": prompt_final}
            ]
        )

        st.subheader("✅ Recomendación técnica para próxima sesión")
        st.markdown(f"**{recomendacion_final.choices[0].message.content}**")

        st.subheader("🧾 Resumen del formulario completado")
        st.markdown(f"**Proyecto:** {nombre_proyecto}")
        for i, el in enumerate(st.session_state.elementos, 1):
            st.markdown(f"- Elemento {i}: {el['descripcion']} ({el['especialidad']})")
        st.markdown(f"**Acuerdos finales:** {acuerdos}")
        st.markdown(f"**Estado del elemento:** {estado}")
        st.markdown(f"**Duración sesión ICE:** {duracion} minutos")
        st.markdown(f"**Responsable:** {responsable}")
        st.markdown(f"**Próxima revisión:** {fecha_revision}")

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
