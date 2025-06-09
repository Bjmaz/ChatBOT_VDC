# chatbot_vdc_app.py
import streamlit as st
import openai

# Configura tu clave secreta (colócala en secrets en la nube de Streamlit)
openai.api_key = st.secrets["openai_api_key"]

# Función de recomendación GPT (solo si hay observación)
def preguntar_a_gpt(prompt):
    respuesta = openai.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "Eres un asistente técnico VDC. Solo respondes cuando se solicita una sugerencia técnica bajo normativa NTP o ISO 9001. Sé breve: máximo 3 líneas."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content

# Página
st.set_page_config(page_title="ChatBot VDC", layout="centered")
st.title("🧠 ChatBot VDC - DOSSIER DE CALIDAD")
st.markdown("---")

# Selección inicial
formato = st.radio("Selecciona una opción:", ["Registrar elementos observados (Formato 1)", "Completar acta de sesión ICE (Formato 2)"])

# FORMATO 1 ----------------------------------------------------------------------
if formato == "Registrar elementos observados (Formato 1)":
    st.subheader("📋 Completa la información del elemento observado. GPT solo actuará si hay observación técnica.")
    
    elementos = []
    continuar = True

    while continuar:
        with st.form(key=f"form_{len(elementos)}"):
            descripcion = st.text_input("🔧 Descripción del elemento", key=f"desc_{len(elementos)}")
            especialidad = st.selectbox("🏷️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"], key=f"esp_{len(elementos)}")
            enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"], key=f"enl_{len(elementos)}")
            evidencia = st.text_input("📎 Tipo de evidencia visual (ej. captura, ficha técnica, otro)", key=f"evi_{len(elementos)}")
            observacion = st.text_area("⚠️ Observación técnica detectada (dejar vacío si no hay)", key=f"obs_{len(elementos)}")
            generar = st.form_submit_button("💡 Generar recomendación")

        if generar and descripcion and especialidad:
            if observacion.strip():
                prompt = f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere una acción correctiva inmediata y una buena práctica futura (máximo 3 líneas, según norma técnica peruana NTP o ISO 9001)."
                recomendacion = preguntar_a_gpt(prompt)
                st.success(f"💡 Recomendación: {recomendacion}")
            else:
                st.info("✅ No se ingresó observación. GPT no intervendrá.")

            # Recolección de datos posteriores a la sesión
            comentarios = st.text_area("🗣️ Comentarios en sesión ICE", key=f"com_{len(elementos)}")
            acuerdos = st.text_area("🤝 Acuerdos tomados", key=f"acu_{len(elementos)}")
            estado = st.selectbox("✅ Estado del elemento", ["Aprobado", "Observado", "Por Corregir"], key=f"est_{len(elementos)}")
            elementos.append({
                "descripcion": descripcion,
                "especialidad": especialidad,
                "observacion": observacion,
                "recomendacion": recomendacion if observacion.strip() else "-",
                "comentarios": comentarios,
                "acuerdos": acuerdos,
                "estado": estado
            })
            continuar = st.radio("¿Deseas registrar otro elemento?", ["Sí", "No"], key=f"cont_{len(elementos)}") == "Sí"

    if elementos:
        st.subheader("📅 Finalizar revisión técnica")
        duracion = st.text_input("⏱️ Duración de la sesión ICE (en minutos)")

        st.markdown("---")
        st.subheader("📋 Recomendaciones para próxima sesión ICE")
        for e in elementos:
            if e["observacion"].strip():
                resumen = f"{e['especialidad']}: {e['descripcion']} → {e['observacion']}"
                recomendacion = preguntar_a_gpt(f"Con base en este elemento: {resumen}, redacta una recomendación breve para debatir en la próxima sesión ICE, según normativa peruana NTP. Máximo 3 líneas.")
                st.markdown(f"- 🔧 **{resumen}**\n\n📌 **{recomendacion}**")

        st.success("Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión del Formato 2.")

# FORMATO 2 ----------------------------------------------------------------------
elif formato == "Completar acta de sesión ICE (Formato 2)":
    st.subheader("📄 Llenado manual del Acta de Sesión ICE")
    proyecto = st.text_input("🏗️ Proyecto")
    fecha = st.date_input("📅 Fecha de sesión")
    lider = st.text_input("👤 Líder de sesión")
    participantes = st.text_area("👥 Participantes")
    duracion = st.text_input("⏱️ Duración total de la sesión (en minutos)")

    temas = []
    continuar = True

    while continuar:
        with st.form(key=f"tema_{len(temas)}"):
            tema = st.text_input("🗂️ Tema abordado", key=f"tema_a_{len(temas)}")
            problema = st.text_area("⚠️ Problema asociado (dejar vacío si no hay)", key=f"prob_{len(temas)}")
            generar = st.form_submit_button("💡 Generar recomendación por tema")

        if generar and tema:
            recomendacion = ""
            if problema.strip():
                recomendacion = preguntar_a_gpt(f"Tema: {tema}. Problema: {problema}. Redacta una recomendación breve de acuerdo a normativa técnica peruana para proponer durante la sesión ICE. Máximo 3 líneas.")
                st.success(f"📌 Recomendación: {recomendacion}")

            temas.append({"tema": tema, "problema": problema, "recomendacion": recomendacion})
            continuar = st.radio("¿Deseas registrar otro tema?", ["Sí", "No"], key=f"cont_tema_{len(temas)}") == "Sí"

    if temas:
        st.subheader("🤝 Acuerdos finales en la sesión ICE")
        acuerdos = st.text_area("📄 Acuerdos finales tomados")

        st.markdown("---")
        st.subheader("📌 Resumen de la sesión:")
        for t in temas:
            st.markdown(f"- Tema: **{t['tema']}**\n  - Problema: {t['problema'] or 'Ninguno'}\n  - Recomendación: {t['recomendacion'] or 'No aplica'}")

        cierre = preguntar_a_gpt(f"Se abordaron estos temas: {[t['tema'] for t in temas]}. Con duración total de {duracion} minutos y acuerdos: {acuerdos}. Redacta una conclusión técnica breve para mejorar futuras sesiones ICE. Máximo 3 líneas.")
        st.success("📌 Conclusión final:")
        st.markdown(f"**{cierre}**")
        st.success("Gracias por usar el ChatBOT VDC. Tu sesión ha sido registrada.")
