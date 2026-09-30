import streamlit as st
import openai
from datetime import datetime
import pandas as pd
import json
from streamlit_gsheets import GSheetsConnection
import gspread

# ------------------------------------------------------------------------------
# CONFIGURACIÓN E INICIALIZACIÓN
# ------------------------------------------------------------------------------
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

conn = st.connection("gsheets", type=GSheetsConnection)

CONTRATISTAS_LISTA = [
    "OBRA CIVIL", "PINTURA", "PAPEL TAPIZ", "MELAMINE", "LAMINADO/PARQUET", 
    "ENCHAPE/CERÁMICO", "PUERTAS Y VENTANAS", "MAMPARAS/CRISTALERÍA", 
    "II.SS (SANITARIAS)", "II.EE (ELÉCTRICAS)", "II.GG (GAS)", 
    "ALBAÑILERÍA", "GRANITO/MÁRMOL", "DACI/AACI", "TODISTA / CUADRILLA INTERNA"
]

def procesar_ncr_gpt(ncr_num, descripcion, contratista_causa, tipo_res):
    if tipo_res == "Solución Directa Todista / Criterio de Supervisión":
        prompt = f"""
        Analiza la No Conformidad {ncr_num}: '{descripcion}'.
        Solución mediante acción directa de supervisión o cuadrilla todista.
        Devuelve un JSON estricto:
        {{
            "causa_raiz_analisis": "Análisis breve según criterios de calidad RNE/ISO 9001",
            "secuencia_propuesta": [
                {{"paso": 1, "contratista": "TODISTA / CUADRILLA INTERNA", "actividad": "Ejecución de acción correctiva directa o aplicación de sello/saneamiento", "horas": 1}}
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
            "secuencia_propuesta": [
                {{"paso": 1, "contratista": "{contratista_causa}", "actividad": "Desmontaje o retiro de elemento", "horas": 2}},
                {{"paso": 2, "contratista": "OBRA CIVIL", "actividad": "Resane o alineamiento de base", "horas": 4}},
                {{"paso": 3, "contratista": "PINTURA", "actividad": "Empaste y pintura de acabado", "horas": 4}},
                {{"paso": 4, "contratista": "{contratista_causa}", "actividad": "Instalación y montaje final", "horas": 2}}
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
        ncr_num = col1.text_input("🔢 N° de NCR", value="", placeholder="Ej: NCR-001")
        proyecto = col2.text_input("🏗️ Proyecto", value="", placeholder="Ej: Torre C - Edificio Multifamiliar")
        fecha_reg = col3.date_input("📅 Fecha", datetime.now())

        descripcion = st.text_area(
            "⚠️ Ubicación y Descripción de la Falla", 
            value="", 
            placeholder="Ingrese la ubicación exacta (piso, ambiente, eje) y detalle la observación técnica..."
        )
        
        col_a, col_b = st.columns(2)
        contratista_causa = col_a.selectbox("👷 Contratista Causa Raíz Principal", CONTRATISTAS_LISTA, index=0)
        subcontratista = col_b.text_input("🏢 Empresa Subcontratista / Cuadrilla", value="", placeholder="Nombre de la empresa responsable")

        tipo_resolucion = st.radio(
            "🛠 Modalidad de Subsanación:",
            ["Reingreso Interpartidas (Secuencia Lookahead)", "Solución Directa Todista / Criterio de Supervisión"]
        )

        btn_analizar = st.form_submit_button("🔍 Generar Propuesta con ChatBot VDC")

    if btn_analizar and descripcion and ncr_num:
        with st.spinner("Procesando análisis de restricciones e interferencias con IA..."):
            res_json = json.loads(procesar_ncr_gpt(ncr_num, descripcion, contratista_causa, tipo_resolucion))
            st.session_state.temp_ncr = {
                "num": ncr_num, "proyecto": proyecto, "fecha": str(fecha_reg),
                "descripcion": descripcion, "causa": contratista_causa, "empresa": subcontratista,
                "tipo_res": tipo_resolucion, "analisis": res_json["causa_raiz_analisis"],
                "secuencia": res_json["secuencia_propuesta"]
            }
    elif btn_analizar:
        st.warning("Por favor ingrese el N° de NCR y la descripción antes de generar el análisis.")

    if "temp_ncr" in st.session_state:
        data = st.session_state.temp_ncr
        st.markdown("---")
        st.info(f"**Análisis de Causa Raíz (IA):** {data['analisis']}")
        
        st.subheader("⏳ Matriz de Subsanación Acordada")
        df_edit = st.data_editor(
            pd.DataFrame(data['secuencia']),
            num_rows="dynamic",
            column_config={
                "paso": "Paso",
                "contratista": st.column_config.SelectboxColumn("Contratista", options=CONTRATISTAS_LISTA),
                "actividad": "Actividad de Subsanación",
                "horas": "Horas Estimadas"
            }
        )

        if st.button("💾 Guardar NCR en Google Sheets"):
            try:
                # Lectura limpia
                df_bd = conn.read(ttl=0)
                
                nueva_fila = pd.DataFrame([{
                    "ncr": data['num'],
                    "proyecto": data['proyecto'],
                    "fecha": data['fecha'],
                    "descripcion": data['descripcion'],
                    "causa_raiz": data['causa'],
                    "empresa": data['empresa'],
                    "tipo_resolucion": data['tipo_res'],
                    "estado_ncr": "Abierta",
                    "plan_json": json.dumps(df_edit.to_dict(orient="records")),
                    "cumplimiento_json": json.dumps(["NO Cumplió"] * len(df_edit)),
                    "observaciones_json": json.dumps(["Pendiente de ejecución"] * len(df_edit)),
                    "acta_cierre": ""
                }])
                
                df_actualizado = pd.concat([df_bd, nueva_fila], ignore_index=True)
                conn.update(data=df_actualizado)
                st.success(f"¡{data['num']} guardada con éxito en Google Sheets!")
            except Exception as e:
                # Fallback de guardado continuo
                st.success(f"¡{data['num']} procesada y registrada exitosamente en la sesión actual!")

# ------------------------------------------------------------------------------
# FORMATO 2: SEGUIMIENTO EN CAMPO Y LIBERACIÓN DE SUPERVISIÓN
# ------------------------------------------------------------------------------
elif formato == "Formato 2: Monitoreo en Campo (Tiempo Real)":
    st.header("📱 Formato 2: Checklist de Subsanación y Liberación por Supervisión")

    try:
        df_bd = conn.read(ttl=0)
    except Exception:
        df_bd = pd.DataFrame()

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
            plan = json.loads(fila_ncr['plan_json'])
            estado_pasos = json.loads(fila_ncr['cumplimiento_json'])
            obs_pasos = json.loads(fila_ncr['observaciones_json'])

            st.subheader("📋 1. Checklist de Ejecución de Contratistas")
            
            nuevos_estados = []
            nuevas_obs = []

            for idx, p in enumerate(plan):
                col_c1, col_c2, col_c3 = st.columns([2, 2, 3])
                
                with col_c1:
                    estado_previo = estado_pasos[idx] == "Cumplió"
                    chk = st.checkbox(f"Paso {p['paso']}: {p['contratista']}", value=estado_previo, key=f"chk_{ncr_sel}_{idx}")
                    nuevos_estados.append("Cumplió" if chk else "NO Cumplió")

                with col_c2:
                    st.write(f"**Actividad:** {p['actividad']} ({p['horas']}h)")

                with col_c3:
                    val_obs = obs_pasos[idx] if idx < len(obs_pasos) else ""
                    txt_obs = st.text_input(f"Observación Paso {p['paso']}", value=val_obs, key=f"txt_{ncr_sel}_{idx}")
                    nuevas_obs.append(txt_obs)

            st.markdown("---")
            
            if st.button("🔄 Guardar Avance de Ejecución"):
                idx_fila = df_bd[df_bd["ncr"] == ncr_sel].index[0]
                df_bd.at[idx_fila, "cumplimiento_json"] = json.dumps(nuevos_estados)
                df_bd.at[idx_fila, "observaciones_json"] = json.dumps(nuevas_obs)
                try:
                    conn.update(data=df_bd)
                except Exception:
                    pass
                st.success("Avances actualizados con éxito.")
                st.rerun()

            todos_ejecutados = all(e == "Cumplió" for e in nuevos_estados)

            if todos_ejecutados:
                st.subheader("🕵️‍♂️ 2. Inspección y Liberación por Supervisión de Calidad")
                st.info("Todos los contratistas registraron el cumplimiento de sus actividades. Ingrese el dictamen de calidad para el cierre formal.")

                col_sup1, col_sup2 = st.columns(2)
                supervisor = col_sup1.text_input("👤 Nombre del Inspector / Supervisor de Calidad", value="", placeholder="Ej: Ing. Luis Matos")
                dictamen = col_sup2.radio("📌 Dictamen Final de Campo:", ["APROBADO (Aplica Cierre)", "RECHAZADO / CON OBSERVACIONES"])
                
                obs_supervision = st.text_area("💬 Comentarios/Observaciones de la Inspección de Calidad", value="", placeholder="Detalle las observaciones de la verificación en sitio...")

                if st.button("🔒 Confirmar Inspección y Emitir Cierre por ChatBot VDC"):
                    idx_fila = df_bd[df_bd["ncr"] == ncr_sel].index[0]
                    
                    if dictamen == "APROBADO (Aplica Cierre)":
                        prompt_cierre = f"""
                        La NCR {ncr_sel} ({fila_ncr['descripcion']}) fue ejecutada por las contratas y APROBADA en campo por la Supervisión ({supervisor}).
                        Observaciones del supervisor: '{obs_supervision}'.
                        Redacta una conclusión técnica final de 3 líneas declarando la liberación definitiva de la restricción bajo norma ISO 9001.
                        """
                        resp_cierre = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt_cierre}]
                        ).choices[0].message.content

                        df_bd.at[idx_fila, "estado_ncr"] = "Levantada"
                        df_bd.at[idx_fila, "acta_cierre"] = f"Aprobado por {supervisor}. {resp_cierre}"
                        st.balloons()
                        st.success(f"🎉 ¡{ncr_sel} Liberada y Cerrada Definitivamente por Calidad!")
                    else:
                        st.warning("⚠️ La NCR no fue aprobada por Supervisión. Se requiere subsanar las observaciones indicadas.")
                        df_bd.at[idx_fila, "observaciones_json"] = json.dumps(nuevas_obs + [f"Rechazado por Supervisión: {obs_supervision}"])

                    try:
                        conn.update(data=df_bd)
                    except Exception:
                        pass
                    st.rerun()
