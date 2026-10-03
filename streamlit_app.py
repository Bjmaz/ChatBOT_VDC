import streamlit as st
import openai
from datetime import datetime, timedelta
import pandas as pd
import json
from streamlit_gsheets import GSheetsConnection

# ------------------------------------------------------------------------------
# CONFIGURACIÓN E INICIALIZACIÓN DE ESTADO
# ------------------------------------------------------------------------------
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])
conn = st.connection("gsheets", type=GSheetsConnection)

if "db_ncrs" not in st.session_state:
    try:
        df_drive = conn.read(ttl=0)
        if not df_drive.empty and "ncr" in df_drive.columns:
            st.session_state.db_ncrs = df_drive
        else:
            st.session_state.db_ncrs = pd.DataFrame(columns=[
                "ncr", "proyecto", "fecha", "descripcion", "causa_raiz", "empresa",
                "tipo_resolucion", "estado_ncr", "plan_json", "cumplimiento_json",
                "observaciones_json", "acta_cierre"
            ])
    except Exception:
        st.session_state.db_ncrs = pd.DataFrame(columns=[
            "ncr", "proyecto", "fecha", "descripcion", "causa_raiz", "empresa",
            "tipo_resolucion", "estado_ncr", "plan_json", "cumplimiento_json",
            "observaciones_json", "acta_cierre"
        ])

CONTRATISTAS_LISTA = [
    "OBRA CIVIL", "PINTURA", "PAPEL TAPIZ", "MELAMINE", "LAMINADO/PARQUET", 
    "ENCHAPE/CERÁMICO", "PUERTAS Y VENTANAS", "MAMPARAS/CRISTALERÍA", 
    "II.SS (SANITARIAS)", "II.EE (ELÉCTRICAS)", "II.GG (GAS)", 
    "ALBAÑILERÍA", "GRANITO/MÁRMOL", "DACI/AACI", "TODISTA / CUADRILLA INTERNA"
]

def procesar_ncr_gpt(ncr_num, descripcion, contratista_causa, tipo_res, fecha_inicio_str, observacion_previa=""):
    try:
        fecha_base = datetime.strptime(str(fecha_inicio_str), "%Y-%m-%d")
    except Exception:
        fecha_base = datetime.now()
        
    f_p1 = (fecha_base + timedelta(days=0)).strftime("%Y-%m-%d")
    f_p2 = (fecha_base + timedelta(days=1)).strftime("%Y-%m-%d")
    f_p4 = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")

    if tipo_res == "Solución Directa Todista / Criterio de Supervisión":
        prompt = f"""
        Analiza la No Conformidad / Observación de Recepción {ncr_num}: '{descripcion}'.
        Especialidad involucrada: {contratista_causa}.
        Notas / Contexto del usuario: '{observacion_previa}'.

        El objetivo es EVITAR EL RETRABAJO COMPLEJO (como desmontar muebles, picar enchapes o rehacer acabados) que comprometa los protocolos de entrega (RI / RF) con la Supervisión.
        
        Devuelve un JSON estricto con:
        {{
            "causa_raiz_analisis": "Análisis técnico breve de la interferencia/defecto entre acabados",
            "justificacion_no_retrabajo": "Sustento técnico de por qué NO se recomienda el desmontaje completo (riesgo de daño a partidas limpias, retraso de entregas RI/RF y sobrecosto)",
            "propuesta_mitigacion": "Propuesta de solución alternativa directa y estética para la Supervisión (ej. aplicación de sellador elastomérico neutro en tono gris similar al fragüe, colocación de junquillo/tapajunta de remate, o retoque puntual)",
            "correo_supervision": "Estimada Supervisión,\\n\\nRespecto a la observación {ncr_num} ({descripcion}), con el objetivo de no comprometer la integridad del mueble/acabado ya instalado ni retrasar el cronograma de entregas (RI/RF), proponemos la siguiente solución de mitigación técnica:\\n\\n- Propuesta: [Describir solución limpia, ej: colocación de sellador poliuretano gris según tono de fragüe].\\n\\nAgradeceremos su validación y criterio técnico de aceptación para proceder inmediatamente con la ejecución por parte de nuestra cuadrilla todista.\\n\\nAtentamente,\\nEquipo de Calidad / Obra",
            "secuencia_propuesta": [
                {{"paso": 1, "fecha_prog": "{f_p1}", "contratista": "TODISTA / CUADRILLA INTERNA", "actividad": "Ejecución de solución/saneamiento directo según criterio de Supervisión", "horas": 2}}
            ]
        }}
        """
    else:
        prompt = f"""
        Analiza la No Conformidad {ncr_num}: '{descripcion}'.
        Causa Raíz Principal: {contratista_causa}.
        Devuelve un JSON estricto con la secuencia de reingreso de subcontratas e interferencias:
        {{
            "causa_raiz_analisis": "Análisis breve de causa raíz bajo ISO 9001/RNE",
            "justificacion_no_retrabajo": "No aplica (se requiere reconstrucción/reingreso completo)",
            "propuesta_mitigacion": "Secuencia Lookahead de reingreso interpartidas",
            "correo_supervision": "",
            "secuencia_propuesta": [
                {{"paso": 1, "fecha_prog": "{f_p1}", "contratista": "{contratista_causa}", "actividad": "Desmontaje o retiro de elemento defectuoso", "horas": 2}},
                {{"paso": 2, "fecha_prog": "{f_p2}", "contratista": "OBRA CIVIL", "actividad": "Resane, nivelación y alineamiento de muro/base", "horas": 4}},
                {{"paso": 3, "fecha_prog": "{f_p2}", "contratista": "PINTURA", "actividad": "Empaste, sellado e imprimación de superficie", "horas": 4}},
                {{"paso": 4, "fecha_prog": "{f_p4}", "contratista": "{contratista_causa}", "actividad": "Instalación, montaje final y entrega", "horas": 2}}
            ]
        }}
        """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

st.set_page_config(page_title="ChatBot VDC - Gestión de NCRs", layout="wide")
st.title("🧠 ChatBot VDC - Gestión e Interferencias de No Conformidades")

formato = st.radio("📌 Selecciona el proceso:", ["Formato 1: Registro e ICE (Oficina)", "Formato 2: Monitoreo en Campo (Tiempo Real)"])

# ------------------------------------------------------------------------------
# FORMATO 1: REGISTRO DE NCR Y PLANIFICACIÓN
# ------------------------------------------------------------------------------
if formato == "Formato 1: Registro e ICE (Oficina)":
    st.header("📋 Formato 1: Registro de NCR y Planificación de Subsanación")

    with st.form("form_ncr"):
        col1, col2, col3 = st.columns([1, 2, 1])
        ncr_num = col1.text_input("🔢 N° de NCR / Observación", value="", placeholder="Ej: NCR-001 o OBS-042")
        proyecto = col2.text_input("🏗️ Proyecto", value="", placeholder="Ej: Torre C - Edificio Multifamiliar")
        fecha_reg = col3.date_input("📅 Fecha de Registro / Inicio", datetime.now())

        descripcion = st.text_area(
            "⚠️ Ubicación y Descripción de la Falla / Observación RI-RF", 
            value="", 
            placeholder="Ingrese la ubicación exacta (piso, ambiente, eje) y detalle la observación técnica..."
        )
        
        col_a, col_b = st.columns(2)
        contratista_causa = col_a.selectbox("👷 Contratista / Especialidad Involucrada", CONTRATISTAS_LISTA, index=0)
        subcontratista = col_b.text_input("🏢 Empresa Subcontratista / Cuadrilla", value="", placeholder="Nombre de la empresa responsable")

        tipo_resolucion = st.radio(
            "🛠 Modalidad de Subsanación:",
            [
                "Reingreso Interpartidas (Secuencia Lookahead)", 
                "Solución Directa Todista / Criterio de Supervisión"
            ]
        )

        obs_adicional = ""
        if tipo_resolucion == "Solución Directa Todista / Criterio de Supervisión":
            obs_adicional = st.text_input(
                "💬 Criterio de Campo deseado (Opcional):", 
                placeholder="Ejemplo: Se busca colocar sellador gris sin retirar el mueble bajo ni romper el enchape."
            )

        btn_analizar = st.form_submit_button("🔍 Generar Propuesta con ChatBot VDC")

    if btn_analizar and descripcion and ncr_num:
        with st.spinner("Procesando análisis de restricciones e interferencias con IA..."):
            res_json = json.loads(procesar_ncr_gpt(ncr_num, descripcion, contratista_causa, tipo_resolucion, str(fecha_reg), obs_adicional))
            st.session_state.temp_ncr = {
                "num": ncr_num, "proyecto": proyecto, "fecha": str(fecha_reg),
                "descripcion": descripcion, "causa": contratista_causa, "empresa": subcontratista,
                "tipo_res": tipo_resolucion, 
                "analisis": res_json["causa_raiz_analisis"],
                "justificacion": res_json.get("justificacion_no_retrabajo", ""),
                "propuesta": res_json.get("propuesta_mitigacion", ""),
                "correo": res_json.get("correo_supervision", ""),
                "secuencia": res_json["secuencia_propuesta"]
            }
    elif btn_analizar:
        st.warning("Por favor ingrese el N° de NCR/Observación y la descripción antes de generar el análisis.")

    if "temp_ncr" in st.session_state:
        data = st.session_state.temp_ncr
        st.markdown("---")
        
        if data['tipo_res'] == "Solución Directa Todista / Criterio de Supervisión":
            st.info(f"💡 **Análisis Técnico:** {data['analisis']}")
            
            st.subheader("🛡 Sustento para Evitar Retrabajo Invasivo")
            st.warning(f"**Justificación:** {data['justificacion']}")
            
            st.subheader("🛠️ Propuesta de Mitigación / Criterio de Aceptación")
            propuesta_edit = st.text_area("Puedes ajustar la propuesta antes de enviarla a la Supervisión:", value=data['propuesta'], height=80)
            st.session_state.temp_ncr['propuesta'] = propuesta_edit

            st.subheader("✉️ Borrador para Validación de la Supervisión (R1 / RF)")
            correo_edit = st.text_area("Texto listo para enviar al Inspector por correo/WhatsApp:", value=data['correo'], height=180)
            st.session_state.temp_ncr['correo'] = correo_edit

        else:
            st.info(f"**Análisis de Causa Raíz (IA):** {data['analisis']}")

        st.subheader("⏳ Matriz de Subsanación Programada")
        
        df_secuencia = pd.DataFrame(data['secuencia'])
        if "fecha_prog" in df_secuencia.columns:
            df_secuencia["fecha_prog"] = pd.to_datetime(df_secuencia["fecha_prog"]).dt.date

        df_edit = st.data_editor(
            df_secuencia,
            num_rows="dynamic",
            column_config={
                "paso": st.column_config.NumberColumn("Paso", disabled=False),
                "fecha_prog": st.column_config.DateColumn("📅 Fecha Programada", format="YYYY-MM-DD", required=True),
                "contratista": st.column_config.SelectboxColumn("Contratista", options=CONTRATISTAS_LISTA, required=True),
                "actividad": st.column_config.TextColumn("Actividad de Subsanación", width="large", required=True),
                "horas": st.column_config.NumberColumn("⏱️ Horas Estimadas", min_value=1, max_value=48, required=True)
            },
            hide_index=True
        )

        if st.button("💾 Guardar NCR en Google Sheets"):
            estado_ini = "Pendiente Validación Supervisión" if data['tipo_res'] == "Solución Directa Todista / Criterio de Supervisión" else "Abierta"
            
            df_guardar = df_edit.copy()
            if "fecha_prog" in df_guardar.columns:
                df_guardar["fecha_prog"] = df_guardar["fecha_prog"].astype(str)

            nueva_fila = pd.DataFrame([{
                "ncr": data['num'],
                "proyecto": data['proyecto'],
                "fecha": data['fecha'],
                "descripcion": f"{data['descripcion']} | Solución: {data.get('propuesta', '')}",
                "causa_raiz": data['causa'],
                "empresa": data['empresa'],
                "tipo_resolucion": data['tipo_res'],
                "estado_ncr": estado_ini,
                "plan_json": json.dumps(df_guardar.to_dict(orient="records")),
                "cumplimiento_json": json.dumps(["NO Cumplió"] * len(df_guardar)),
                "observaciones_json": json.dumps(["Pendiente de validación/ejecución"] * len(df_guardar)),
                "acta_cierre": ""
            }])
            
            st.session_state.db_ncrs = pd.concat([st.session_state.db_ncrs, nueva_fila], ignore_index=True)
            
            try:
                conn.update(data=st.session_state.db_ncrs)
            except Exception:
                pass
                
            st.success(f"¡{data['num']} guardada con éxito! Estado: `{estado_ini}`. Puedes revisarla en el Formato 2.")

# ------------------------------------------------------------------------------
# FORMATO 2: SEGUIMIENTO EN CAMPO Y LIBERACIÓN DE SUPERVISIÓN
# ------------------------------------------------------------------------------
elif formato == "Formato 2: Monitoreo en Campo (Tiempo Real)":
    st.header("📱 Formato 2: Checklist de Subsanación y Liberación por Supervisión")

    df_bd = st.session_state.db_ncrs

    if df_bd.empty or "ncr" not in df_bd.columns or df_bd["ncr"].dropna().empty:
        st.warning("No hay No Conformidades registradas en la base de datos.")
    else:
        lista_ncrs = df_bd["ncr"].dropna().tolist()
        ncr_sel = st.selectbox("📌 Selecciona la NCR a revisar:", lista_ncrs)

        fila_ncr = df_bd[df_bd["ncr"] == ncr_sel].iloc[0]

        st.markdown(f"**Proyecto:** {fila_ncr['proyecto']} | **Modalidad:** `{fila_ncr['tipo_resolucion']}` | **Estado:** `{fila_ncr['estado_ncr']}`")
        st.markdown(f"**Ubicación y Falla:** {fila_ncr['descripcion']}")
        st.markdown("---")

        if fila_ncr['estado_ncr'] == "Levantada":
            st.success(f"✅ LA {ncr_sel} SE ENCUENTRA COMPLETAMENTE LEVANTADA Y LIBERADA POR SUPERVISIÓN.")
            st.subheader("📜 Acta de Cierre Técnico y Conformidad")
            st.info(fila_ncr['acta_cierre'])

        else:
            idx_fila = df_bd[df_bd["ncr"] == ncr_sel].index[0]

            # BLOQUE DE NEGOCIACIÓN CON SUPERVISIÓN (OPCIÓN 2)
            if fila_ncr['estado_ncr'] == "Pendiente Validación Supervisión":
                st.warning("⏳ Esta propuesta técnica está en evaluación con la Supervisión para evitar el retrabajo invasivo.")
                
                col_v1, col_v2 = st.columns(2)
                sup_nombre = col_v1.text_input("👤 Nombre de quien revisa (Supervisión):", value="", placeholder="Ej: Ing. Luis Matos")
                dictamen_sup = col_v2.radio(
                    "📌 Respuesta / Dictamen de la Supervisión:", 
                    [
                        "✅ APROBADO (Ejecutar propuesta ligera con Todistas)",
                        "2. RECHAZADO (Reiterar sustento / Proponer nuevo ajuste)",
                        "🚨 RECHAZADO DEFINITIVO (Asumir cambio y reconstruir en cadena)"
                    ]
                )
                
                # Campo condicional para escribir la objeción del inspector
                objecion_inspector = ""
                if "RECHAZADO (Reiterar" in dictamen_sup:
                    objecion_inspector = st.text_area(
                        "🗣️ Copia/Escribe el motivo del rechazo u objeción del Inspector:",
                        placeholder="Ejemplo: El inspector indica que el sellador se va a desprender con la limpieza de la cocina y exige una solución impermeable fija."
                    )

                if st.button("📝 Registrar Dictamen de Supervisión"):
                    if "APROBADO" in dictamen_sup:
                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (Aprobada por Supervisión)"
                        st.session_state.pop(f"refutacion_{ncr_sel}", None)
                        st.success("🎉 Propuesta APROBADA por Supervisión. Habilitado el checklist para ejecución todista.")
                        st.rerun()

                    elif "RECHAZADO (Reiterar" in dictamen_sup:
                        if not objecion_inspector:
                            st.warning("Por favor ingrese el motivo u objeción del inspector para formular la refutación técnica.")
                        else:
                            with st.spinner("Generando borrador de refutación enfocado en rebatir la objeción del inspector..."):
                                prompt_reiterar = f"""
                                La Supervisión ({sup_nombre}) rechazó la propuesta inicial para {ncr_sel}: '{fila_ncr['descripcion']}'.
                                Objeción específica expresada por el Inspector: '{objecion_inspector}'.

                                Genera un correo de refutación técnica formal respondiendo Y REBATIENDO punto por punto la objeción del inspector '{objecion_inspector}'.
                                Sustenta la respuesta usando criterios de calidad (ISO 9001 / Especificaciones Técnicas / durabilidad / elasticidad) y propone un ajuste técnico mejorado (ej. sellador de poliuretano hibrido monocomponente de alto módulo o perfil de remate) para convencer al inspector sin necesidad de desmontar ni picar.
                                """
                                nuevo_correo = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[{"role": "user", "content": prompt_reiterar}]
                                ).choices[0].message.content
                                
                                st.session_state[f"refutacion_{ncr_sel}"] = nuevo_correo
                                st.rerun()

                    elif "RECHAZADO DEFINITIVO" in dictamen_sup:
                        with st.spinner("Transformando a Secuencia Lookahead..."):
                            prompt_lookahead = f"Analiza {ncr_sel}: {fila_ncr['descripcion']}. Causa raíz: {fila_ncr['causa_raiz']}. Genera la secuencia estricta Lookahead de reingreso de subcontratas (desmontar, resanar, pintar, re-instalar) en JSON estricto: {{\"secuencia_propuesta\": [ {{\"paso\": 1, \"fecha_prog\": \"{str(datetime.now().date())}\", \"contratista\": \"{fila_ncr['causa_raiz']}\", \"actividad\": \"Desmontaje o retiro de elemento defectuoso\", \"horas\": 2}}, {{\"paso\": 2, \"fecha_prog\": \"{str((datetime.now() + timedelta(days=1)).date())}\", \"contratista\": \"OBRA CIVIL\", \"actividad\": \"Resane y alineamiento de base\", \"horas\": 4}}, {{\"paso\": 3, \"fecha_prog\": \"{str((datetime.now() + timedelta(days=2)).date())}\", \"contratista\": \"PINTURA\", \"actividad\": \"Empaste y pintura de acabado\", \"horas\": 4}}, {{\"paso\": 4, \"fecha_prog\": \"{str((datetime.now() + timedelta(days=3)).date())}\", \"contratista\": \"{fila_ncr['causa_raiz']}\", \"actividad\": \"Instalación y montaje final\", \"horas\": 2}} ]}}"
                            res_lk = json.loads(client.chat.completions.create(
                                model="gpt-4o-mini",
                                response_format={"type": "json_object"},
                                messages=[{"role": "user", "content": prompt_lookahead}]
                            ).choices[0].message.content)

                            st.session_state.db_ncrs.at[idx_fila, "tipo_resolucion"] = "Reingreso Interpartidas (Secuencia Lookahead)"
                            st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta"
                            st.session_state.db_ncrs.at[idx_fila, "plan_json"] = json.dumps(res_lk["secuencia_propuesta"])
                            st.session_state.db_ncrs.at[idx_fila, "cumplimiento_json"] = json.dumps(["NO Cumplió"] * len(res_lk["secuencia_propuesta"]))
                            st.session_state.db_ncrs.at[idx_fila, "observaciones_json"] = json.dumps(["Pendiente tras rechazo definitivo"] * len(res_lk["secuencia_propuesta"]))
                            st.session_state.pop(f"refutacion_{ncr_sel}", None)
                            
                            st.rerun()

            # Muestra el borrador de refutación si existe
            if f"refutacion_{ncr_sel}" in st.session_state:
                st.markdown("---")
                st.info("💡 **BORRADOR DE REFUTACIÓN TÉCNICA (BASADO EN LA OBJECIÓN DEL INSPECTOR):**")
                st.text_area(
                    "✉️ Copia este texto para responder al Inspector por correo o WhatsApp:", 
                    value=st.session_state[f"refutacion_{ncr_sel}"], 
                    height=250
                )
                st.markdown("---")

            plan = json.loads(fila_ncr['plan_json'])
            estado_pasos = json.loads(fila_ncr['cumplimiento_json'])
            obs_pasos = json.loads(fila_ncr['observaciones_json'])

            st.subheader("📋 1. Checklist de Ejecución de Contratistas")
            
            nuevos_estados = []
            nuevas_obs = []

            for idx, p in enumerate(plan):
                fecha_str = p.get("fecha_prog", "S/F")
                col_c1, col_c2, col_c3 = st.columns([2.5, 2.5, 3])
                
                with col_c1:
                    estado_previo = estado_pasos[idx] == "Cumplió"
                    chk = st.checkbox(f"Paso {p['paso']}: {p['contratista']}", value=estado_previo, key=f"chk_{ncr_sel}_{idx}")
                    nuevos_estados.append("Cumplió" if chk else "NO Cumplió")

                with col_c2:
                    st.write(f"📅 **{fecha_str}** | **{p['actividad']}** ({p['horas']}h)")

                with col_c3:
                    val_obs = obs_pasos[idx] if idx < len(obs_pasos) else ""
                    txt_obs = st.text_input(f"Observación Paso {p['paso']}", value=val_obs, key=f"txt_{ncr_sel}_{idx}")
                    nuevas_obs.append(txt_obs)

            st.markdown("---")
            
            if st.button("🔄 Guardar Avance de Ejecución"):
                st.session_state.db_ncrs.at[idx_fila, "cumplimiento_json"] = json.dumps(nuevos_estados)
                st.session_state.db_ncrs.at[idx_fila, "observaciones_json"] = json.dumps(nuevas_obs)
                try:
                    conn.update(data=st.session_state.db_ncrs)
                except Exception:
                    pass
                st.success("Avances actualizados con éxito.")
                st.rerun()

            todos_ejecutados = all(e == "Cumplió" for e in nuevos_estados)

            if todos_ejecutados:
                st.subheader("🕵️‍♂️ 2. Inspección y Liberación por Supervisión de Calidad")
                st.info("Todos los trabajos fueron ejecutados en campo. Ingrese el dictamen de calidad para la liberación formal RI/RF.")

                col_sup1, col_sup2 = st.columns(2)
                supervisor = col_sup1.text_input("👤 Nombre del Inspector / Supervisor de Calidad", value="", placeholder="Ej: Ing. Luis Matos")
                dictamen = col_sup2.radio("📌 Dictamen Final de Campo:", ["APROBADO (Aplica Cierre)", "RECHAZADO / CON OBSERVACIONES"])
                
                obs_supervision = st.text_area("💬 Comentarios/Observaciones de la Inspección de Calidad", value="", placeholder="Ejemplo: Trabajos verificados en sitio. Cumplen con los criterios de calidad para liberación de protocolo RI/RF.")

                if st.button("🔒 Confirmar Inspección y Emitir Cierre por ChatBot VDC"):
                    if dictamen == "APROBADO (Aplica Cierre)":
                        prompt_cierre = f"""
                        La No Conformidad {ncr_sel} ({fila_ncr['descripcion']}) fue ejecutada y APROBADA en campo por la Supervisión ({supervisor}).
                        Observaciones del supervisor: '{obs_supervision}'.
                        Redacta una conclusión técnica final de 3 líneas declarando la liberación definitiva de la restricción para los protocolos RI/RF bajo norma ISO 9001.
                        """
                        resp_cierre = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt_cierre}]
                        ).choices[0].message.content

                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Levantada"
                        st.session_state.db_ncrs.at[idx_fila, "acta_cierre"] = f"Aprobado por {supervisor}. {resp_cierre}"
                        st.balloons()
                        st.success(f"🎉 ¡{ncr_sel} Liberada y Cerrada Definitivamente por Calidad!")
                    else:
                        st.warning("⚠️ La NCR no fue aprobada por Supervisión. Se requiere corregir las observaciones.")
                        st.session_state.db_ncrs.at[idx_fila, "observaciones_json"] = json.dumps(nuevas_obs + [f"Rechazado por Supervisión: {obs_supervision}"])

                    try:
                        conn.update(data=st.session_state.db_ncrs)
                    except Exception:
                        pass
                    st.rerun()
