# streamlit_app.py
import streamlit as st
import openai

# Configura tu API Key desde los secrets
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

formato = st.radio("\U0001F4CB Selecciona un formato:", ["Registrar elementos observados (Formato 1)", "Completar acta de sesión ICE (Formato 2)"])

# FORMATO 1
if formato == "Registrar elementos observados (Formato 1)":
    st.subheader("Completa la información Técnica de los elementos observados")

    elementos = []
    with st.form("elemento_form"):
        proyecto = st.text_input("🏗️ Nombre del Proyecto")
        descripcion = st.text_input("🔧 Descripción del elemento")
        especialidad = st.selectbox("🏷️ Especialidad", ["", "Arquitectura", "Estructuras", "Eléctricas", "Sanitarias"])
        enlace = st.selectbox("🔗 Tipo de enlace al modelo", ["", "Autodesk BIM 360 / ACC", "Navisworks", "Revit + Envío local", "QR impreso"])
        evidencia = st.text_input("📎 Tipo de evidencia visual (ej. captura, ficha técnica, otro)")
        observacion = st.text_area("⚠️ Observación técnica detectada (dejar vacío si no hay)")
        agregar = st.form_submit_button("➕ Agregar elemento")

        if agregar and descripcion and especialidad and observacion:
            recomendacion = recomendar_gpt(f"Elemento: {descripcion} ({especialidad}). Enlace: {enlace}. Evidencia: {evidencia}. Observación: {observacion}. Sugiere una acción correctiva inmediata y una buena práctica futura. (3 líneas, según NTP o ISO 9001).")
            st.session_state.setdefault("elementos", []).append({
                "descripcion": descripcion,
                "especialidad": especialidad,
                "observacion": observacion,
                "recomendacion": recomendacion
            })
            st.success("Elemento registrado. Puedes agregar otro si es necesario.")

    if "elementos" in st.session_state:
        st.subheader("\U0001F5E3 Recomendaciones por elemento")
        for i, el in enumerate(st.session_state["elementos"], 1):
            st.markdown(f"**{i}.** {el['descripcion']} ({el['especialidad']}) → {el['observacion']}")
            st.markdown(f"\- \U0001F4A1 *{el['recomendacion']}*")

        with st.form("final_formato1"):
            comentarios = st.text_area("\U0001F5E3 Comentarios finales de sesión ICE")
            acuerdos = st.text_area("\U0001F91D Acuerdos finales")
            estado = st.selectbox("✅ Estado final del elemento", ["Aprobado", "Observado", "Por Corregir"])
            duracion = st.text_input("⏱️ Duración total de la sesión ICE")
            validador = st.text_input("🧑‍💼 Responsable de validación")
            fecha_proxima = st.date_input("📅 Fecha de próxima revisión")
            generar_final = st.form_submit_button("✅ Finalizar revisión")

            if generar_final:
                st.subheader("\U0001F4DD Resumen del registro")
                for el in st.session_state["elementos"]:
                    st.markdown(f"- {el['descripcion']} ({el['especialidad']}): {el['observacion']}")

                resumen_prompt = "\n".join([f"{el['descripcion']} ({el['especialidad']}): {el['observacion']}" for el in st.session_state["elementos"]])
                resumen_reco = recomendar_gpt(f"Con base en estas observaciones:\n{resumen_prompt}. Redacta recomendaciones técnicas muy breves por elemento para debatir en la próxima sesión ICE, según NTP o ISO 9001.")
                st.markdown(f"\n\U0001F4A1 **Recomendaciones para próxima sesión ICE:**\n{resumen_reco}")

                st.success("✅ Gracias por usar el ChatBOT VDC. Nos vemos en la siguiente revisión del Formato 2.")

# FORMATO 2
elif formato == "Completar acta de sesión ICE (Formato 2)":
    st.subheader("Completar acta de sesión ICE Técnica")

    temas = []
    with st.form("formato2_inicio"):
        proyecto = st.text_input("🏗️ Proyecto")
        fecha = st.date_input("📅 Fecha de sesión")
        lider = st.text_input("👤 Líder de sesión")
        participantes = st.text_area("👥 Participantes")
        tema = st.text_input("📂 Tema abordado")
        problema = st.text_area("⚠️ Problema abordado (dejar vacío si no hubo)")
        agregar_tema = st.form_submit_button("➕ Agregar tema")

        if agregar_tema:
            if problema:
                recomendacion = recomendar_gpt(f"Tema: {tema}, Problema: {problema}. Sugiere una acción técnica inmediata (máx 3 líneas) según NTP o ISO 9001.")
                st.session_state.setdefault("temas", []).append({"tema": tema, "problema": problema, "reco": recomendacion})
                st.success("Tema agregado con recomendación.")
            else:
                st.session_state.setdefault("temas", []).append({"tema": tema, "problema": "Sin problema detectado.", "reco": "No se requiere intervención técnica."})
                st.info("Tema agregado sin problema. No se generará recomendación GPT.")

    if "temas" in st.session_state:
        st.subheader("\U0001F4C4 Recomendaciones por tema")
        for t in st.session_state["temas"]:
            st.markdown(f"- **{t['tema']}**: {t['problema']}\n\- \U0001F4A1 {t['reco']}")

        with st.form("final_formato2"):
            acuerdos_ice = st.text_area("🤝 Acuerdos finales de sesión ICE")
            duracion_ice = st.text_input("⏱️ Duración total de la sesión ICE")
            responsable = st.text_input("👨‍💼 Responsable de validación")
            enviar_acta = st.form_submit_button("✅ Finalizar acta")

            if enviar_acta:
                resumen_temas = "\n".join([f"{t['tema']}: {t['problema']}" for t in st.session_state["temas"]])
                conclusion = recomendar_gpt(f"Con base en los temas:\n{resumen_temas}\n y acuerdos: {acuerdos_ice}, redacta una conclusión técnica breve para mejorar futuras sesiones ICE.")
                st.subheader("\U0001F4DD Conclusión de sesión")
                st.markdown(conclusion)

                st.success("✅ Gracias por usar el ChatBOT VDC. Tu sesión ha sido registrada con éxito.")
