import json
from datetime import datetime, timedelta
import openai
import pandas as pd
import requests
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURACIÓN E INTEGRACIÓN
# ==============================================================================
st.set_page_config(page_title="ChatBot VDC - Gestión de NCRs", layout="wide")

client = openai.OpenAI(api_key=st.secrets["openai_api_key"])
conn = st.connection("gsheets", type=GSheetsConnection)

# 🔗 URL de tu Web App de Google Apps Script
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbySzCKsLidENfNjIFbDWPTxnETmUX8u6vfUdNLIROgFmdcDj9yQMBFH9yqB9zA_F44Z/exec"

CONTRATISTAS_LISTA = [
    "OBRA CIVIL", "PINTURA", "PAPEL TAPIZ", "MELAMINE", "LAMINADO/PARQUET",
    "ENCHAPE/CERÁMICO", "PUERTAS Y VENTANAS", "MAMPARAS/CRISTALERÍA",
    "II.SS (SANITARIAS)", "II.EE (ELÉCTRICAS)", "II.GG (GAS)",
    "ALBAÑILERÍA", "GRANITO/MÁRMOL", "DACI/AACI", "TODISTA / CUADRILLA INTERNA"
]

ESTADOS_CERRADOS = ["Levantada"]


def empty_db():
    return pd.DataFrame()


def load_db():
    """Carga la base de datos respetando exactamente las columnas de la hoja de Google Sheets."""
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty:
            return empty_db()
        
        # Limpieza general de textos y NaN
        df = df.fillna("")
        for col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "").replace("None", "").str.strip()
            
        return df
    except Exception as e:
        st.session_state.load_error = str(e)
        return empty_db()


if "db_ncrs" not in st.session_state:
    st.session_state.db_ncrs = load_db()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_json_list(value, default=None):
    if default is None:
        default = []
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
            return default.copy()
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, list) else default.copy()
    except Exception:
        return default.copy()


def obtener_valor_columna(row, nombres_posibles, default=""):
    """Busca en la fila el valor probando distintos nombres de columnas equivalentes."""
    for col in nombres_posibles:
        if col in row and str(row[col]).strip() != "":
            return str(row[col]).strip()
    return default


def calcular_metricas(df):
    if df.empty:
        return {
            "total": 0, "cerradas": 0, "pendientes": 0,
            "tnc": None, "pnc": None, "pnco": None,
            "n_validas_tnc": 0, "n_oportunas": 0, "n_cerradas_con_plazo": 0
        }

    total = len(df)
    cerradas = int(df["estado_ncr"].isin(ESTADOS_CERRADOS).sum())
    pendientes = total - cerradas

    tiempos = pd.to_numeric(df["tiempo_calculado_dias"], errors="coerce")
    validos = tiempos.notna() & (tiempos >= 0)

    tnc = float(tiempos[validos].mean()) if validos.any() else None
    pnc = (pendientes / total * 100) if total else None

    plazos = pd.to_numeric(df["plazo_num"], errors="coerce")
    oportunidad = validos & plazos.notna() & (plazos > 0) & (tiempos <= plazos)
    n_cerradas_con_plazo = int((validos & plazos.notna() & (plazos > 0)).sum())
    n_oportunas = int(oportunidad.sum())
    pnco = (n_oportunas / n_cerradas_con_plazo * 100) if n_cerradas_con_plazo else None

    return {
        "total": total,
        "cerradas": cerradas,
        "pendientes": pendientes,
        "tnc": tnc,
        "pnc": pnc,
        "pnco": pnco,
        "n_validas_tnc": int(validos.sum()),
        "n_oportunas": n_oportunas,
        "n_cerradas_con_plazo": n_cerradas_con_plazo,
    }


def preparar_df_indicadores(df):
    out = df.copy()
    
    # Mapeo dinámico para soportar variaciones en nombres de columnas de la hoja
    out["fecha_reg_str"] = out.apply(lambda r: obtener_valor_columna(r, ["fecha_registro", "fecha_hora_registro", "fecha"]), axis=1)
    out["fecha_lev_str"] = out.apply(lambda r: obtener_valor_columna(r, ["fecha_cierre", "fecha_aprobacion", "fecha_hora_levantamiento"]), axis=1)
    
    out["fecha_reg_dt"] = pd.to_datetime(out["fecha_reg_str"], errors="coerce")
    out["fecha_lev_dt"] = pd.to_datetime(out["fecha_lev_str"], errors="coerce")
    
    # Cálculo del tiempo transcurrido en días si no estuviese ya calculado
    dias_calc = (out["fecha_lev_dt"] - out["fecha_reg_dt"]).dt.total_seconds() / 86400
    dias_directos = pd.to_numeric(out.apply(lambda r: obtener_valor_columna(r, ["tiempo_levantamiento_dias", "fecha_inspeccion"]), axis=1), errors="coerce")
    
    out["tiempo_calculado_dias"] = dias_directos.fillna(dias_calc)
    out["plazo_num"] = pd.to_numeric(out.apply(lambda r: obtener_valor_columna(r, ["plazo_objetivo_dias", "fecha_ejecucion"], default="3"), axis=1), errors="coerce").fillna(3)
    
    return out


def procesar_ncr_gpt(ncr_num, descripcion, contratista_causa, tipo_res, fecha_inicio_str, observacion_previa=""):
    try:
        fecha_base = datetime.strptime(str(fecha_inicio_str), "%Y-%m-%d")
    except Exception:
        fecha_base = datetime.now()

    f_p1 = fecha_base.strftime("%Y-%m-%d")
    f_p2 = (fecha_base + timedelta(days=1)).strftime("%Y-%m-%d")
    f_p4 = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")

    if tipo_res == "Solución Directa Todista / Criterio de Supervisión":
        prompt = f"""
Actúa como asistente de ingeniería de calidad y planificación VDC para una obra de edificación en Perú.
Analiza la NCR {ncr_num}. Descripción y ubicación: '{descripcion}'.
Especialidad principal: {contratista_causa}. Criterio o hipótesis del usuario: '{observacion_previa}'.
Fecha base para el plan: {f_p1}.
Contratistas disponibles en el proyecto: {", ".join(CONTRATISTAS_LISTA)}.

Devuelve ÚNICAMENTE JSON válido con esta estructura exacta:
{{
  "causa_raiz_analisis": "Análisis de causa raíz...",
  "complejidad": "BAJA | MEDIA | ALTA",
  "estrategia_recomendada": "SOLUCION_DIRECTA | SOLUCION_DIRECTA_CON_APOYO | RECONSTRUCCION_LOOKAHEAD",
  "justificacion_no_retrabajo": "Sustento para evitar retrabajo invasivo...",
  "propuesta_mitigacion": "Propuesta técnica...",
  "verificaciones_previas": ["Verificación 1", "Verificación 2"],
  "referencias_por_verificar": ["Plano E.T. aplicable"],
  "correo_supervision": "Texto de propuesta para la Supervisión...",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f_p1}", "contratista": "TODISTA / CUADRILLA INTERNA", "actividad": "Ejecución de sello o resane", "horas": 2}}
  ]
}}
"""
    else:
        prompt = f"""
Analiza la No Conformidad {ncr_num}: '{descripcion}'.
Especialidad involucrada: {contratista_causa}.

Diseña una secuencia preliminar de reingreso interpartidas Lookahead.

Devuelve JSON estricto:
{{
  "causa_raiz_analisis": "Análisis de causa raíz e interferencias",
  "justificacion_no_retrabajo": "No aplica: se plantea reconstrucción/reingreso",
  "propuesta_mitigacion": "Secuencia preliminar Lookahead",
  "correo_supervision": "",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f_p1}", "contratista": "{contratista_causa}", "actividad": "Desmontaje o retiro del elemento afectado", "horas": 2}},
    {{"paso": 2, "fecha_prog": "{f_p2}", "contratista": "OBRA CIVIL", "actividad": "Resane, nivelación y preparación de base", "horas": 4}},
    {{"paso": 3, "fecha_prog": "{f_p2}", "contratista": "PINTURA", "actividad": "Restitución de acabado", "horas": 4}},
    {{"paso": 4, "fecha_prog": "{f_p4}", "contratista": "{contratista_causa}", "actividad": "Instalación/montaje final", "horas": 2}}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def generar_cierre_gpt(ncr, descripcion, supervisor, observaciones):
    prompt = f"""
La No Conformidad {ncr} ({descripcion}) fue ejecutada y APROBADA en campo por la Supervisión ({supervisor}).
Observaciones: '{observaciones}'.
Redacta un borrador de conclusión técnica final de máximo 3 líneas para un Acta de Cierre Técnico (ISO 9001).
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# ==============================================================================
# ENCABEZADO Y NAVEGACIÓN
# ==============================================================================
st.title("🧠 ChatBot VDC - Gestión e Interferencias de No Conformidades")
st.caption("Registro, planificación, seguimiento y medición de indicadores de NCR para partidas de acabados.")

formato = st.radio(
    "📌 Selecciona el módulo:",
    [
        "📊 Dashboard de Indicadores",
        "Formato 1: Registro e ICE (Oficina)",
        "Formato 2: Monitoreo en Campo (Tiempo Real)"
    ],
    horizontal=True
)

if getattr(st.session_state, "load_error", ""):
    st.warning(f"Aviso de lectura de Google Sheets: {st.session_state.load_error}")

# ==============================================================================
# 📊 DASHBOARD DE INDICADORES
# ==============================================================================
if formato == "📊 Dashboard de Indicadores":
    st.header("📊 Panel de Indicadores de Gestión de NCR")

    df_raw = st.session_state.db_ncrs.copy()

    if df_raw.empty or "ncr" not in df_raw.columns or df_raw["ncr"].dropna().empty:
        st.info("Aún no existen NCR registradas. Registra NCR desde el Formato 1 para activar el panel.")
    else:
        df_calc = preparar_df_indicadores(df_raw)

        f1, f2 = st.columns(2)
        proyectos = sorted([str(x) for x in df_raw["proyecto"].dropna().unique() if str(x).strip()])
        contratistas = sorted([str(x) for x in df_raw["causa_raiz"].dropna().unique() if str(x).strip()])

        with f1:
            proyecto_sel = st.multiselect("Proyecto", proyectos)
        with f2:
            contratista_sel = st.multiselect("Especialidad", contratistas)

        mask = pd.Series(True, index=df_calc.index)
        if proyecto_sel:
            mask &= df_calc["proyecto"].isin(proyecto_sel)
        if contratista_sel:
            mask &= df_calc["causa_raiz"].isin(contratista_sel)

        df_f = df_calc.loc[mask].copy()
        m = calcular_metricas(df_f)

        st.markdown("### Indicadores Clave")
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("TNC — Tiempo promedio de levantamiento", "—" if m["tnc"] is None else f"{m['tnc']:.2f} días")
            st.caption(f"NCR válidas: {m['n_validas_tnc']}")
        with k2:
            st.metric("PNC — NCR pendientes de cierre", "—" if m["pnc"] is None else f"{m['pnc']:.1f}%")
            st.caption(f"Pendientes: {m['pendientes']} de {m['total']} NCR")
        with k3:
            st.metric("PNCO — NCR levantadas oportunamente", "—" if m["pnco"] is None else f"{m['pnco']:.1f}%")
            st.caption(f"Oportunas: {m['n_oportunas']} de {m['n_cerradas_con_plazo']} con plazo")

        st.markdown("### Trazabilidad Individual")
        
        # Mapeo de columnas para la tabla limpia
        tabla = pd.DataFrame()
        tabla["ncr"] = df_f["ncr"]
        tabla["proyecto"] = df_f["proyecto"]
        tabla["fecha_hora_registro"] = df_f["fecha_reg_str"]
        tabla["fecha_hora_levantamiento"] = df_f["fecha_lev_str"]
        tabla["estado_ncr"] = df_f["estado_ncr"]
        tabla["plazo_objetivo_dias"] = df_f["plazo_num"]
        tabla["tiempo_calculado_dias"] = df_f["tiempo_calculado_dias"].round(2)
        tabla["causa_raiz"] = df_f["causa_raiz"]
        tabla["empresa"] = df_f["empresa"]

        st.dataframe(tabla, use_container_width=True, hide_index=True)

# ==============================================================================
# 📋 FORMATO 1: REGISTRO E ICE
# ==============================================================================
elif formato == "Formato 1: Registro e ICE (Oficina)":
    st.header("📋 Formato 1: Registro de NCR y Planificación de Subsanación")

    with st.form("form_ncr"):
        col1, col2, col3 = st.columns([1, 2, 1])
        ncr_num = col1.text_input("🔢 N° de NCR / Observación", placeholder="Ej: NCR-001")
        proyecto = col2.text_input("🏗️ Proyecto", placeholder="Ej: ALTO BELLAVISTA II")
        fecha_reg = col3.date_input("📅 Fecha de identificación", datetime.now())

        descripcion = st.text_area(
            "⚠️ Ubicación y descripción de la falla / observación",
            placeholder="Ingrese piso, ambiente, eje y detalle técnico..."
        )

        col_a, col_b, col_c = st.columns([2, 2, 1])
        contratista_causa = col_a.selectbox("👷 Especialidad involucrada", CONTRATISTAS_LISTA)
        subcontratista = col_b.text_input("🏢 Empresa subcontratista / cuadrilla", placeholder="Nombre de empresa responsable")
        plazo_objetivo = col_c.number_input("⏱️ Plazo objetivo (días)", min_value=1, max_value=60, value=3)

        tipo_resolucion = st.radio(
            "🛠 Modalidad de subsanación:",
            [
                "Reingreso Interpartidas (Secuencia Lookahead)",
                "Solución Directa Todista / Criterio de Supervisión"
            ]
        )

        obs_adicional = ""
        if tipo_resolucion == "Solución Directa Todista / Criterio de Supervisión":
            obs_adicional = st.text_input("💬 Criterio de campo deseado (opcional)", placeholder="Ej: colocar sello gris...")

        btn_analizar = st.form_submit_button("🔍 Generar propuesta con ChatBot VDC")

    if btn_analizar and descripcion and ncr_num:
        try:
            with st.spinner("Procesando análisis de restricciones con IA..."):
                res_json = json.loads(procesar_ncr_gpt(
                    ncr_num, descripcion, contratista_causa, tipo_resolucion, str(fecha_reg), obs_adicional
                ))
                st.session_state.temp_ncr = {
                    "num": ncr_num, "proyecto": proyecto, "fecha": str(fecha_reg),
                    "descripcion": descripcion, "causa": contratista_causa, "empresa": subcontratista,
                    "tipo_res": tipo_resolucion, "fase_estudio": "Implementación (Después)",
                    "plazo_objetivo": plazo_objetivo,
                    "analisis": res_json.get("causa_raiz_analisis", ""),
                    "justificacion": res_json.get("justificacion_no_retrabajo", ""),
                    "propuesta": res_json.get("propuesta_mitigacion", ""),
                    "correo": res_json.get("correo_supervision", ""),
                    "secuencia": res_json.get("secuencia_propuesta", [])
                }
        except Exception as e:
            st.error(f"No se pudo generar la propuesta con IA: {e}")

    if "temp_ncr" in st.session_state:
        data = st.session_state.temp_ncr
        st.markdown("---")
        st.info(f"**Análisis técnico:** {data['analisis']}")

        if data["tipo_res"] == "Solución Directa Todista / Criterio de Supervisión":
            st.subheader("🛡 Evaluación de alternativa sin retrabajo invasivo")
            st.warning(data["justificacion"])
            propuesta_edit = st.text_area("Ajusta la propuesta antes de enviarla a Supervisión:", value=data["propuesta"], height=100)
            st.session_state.temp_ncr["propuesta"] = propuesta_edit

            correo_edit = st.text_area("Borrador para validación de Supervisión:", value=data["correo"], height=150)
            st.session_state.temp_ncr["correo"] = correo_edit

        st.subheader("⏳ Matriz de subsanación / Lookahead")
        df_secuencia = pd.DataFrame(data["secuencia"])
        if df_secuencia.empty:
            df_secuencia = pd.DataFrame([{"paso": 1, "fecha_prog": data["fecha"], "contratista": data["causa"], "actividad": "Definir actividad", "horas": 1}])
        if "fecha_prog" in df_secuencia.columns:
            df_secuencia["fecha_prog"] = pd.to_datetime(df_secuencia["fecha_prog"], errors="coerce").dt.date

        df_edit = st.data_editor(
            df_secuencia,
            num_rows="dynamic",
            column_config={
                "paso": st.column_config.NumberColumn("Paso", min_value=1, step=1),
                "fecha_prog": st.column_config.DateColumn("📅 Fecha programada", format="YYYY-MM-DD", required=True),
                "contratista": st.column_config.SelectboxColumn("Contratista", options=CONTRATISTAS_LISTA, required=True),
                "actividad": st.column_config.TextColumn("Actividad de subsanación", width="large", required=True),
                "horas": st.column_config.NumberColumn("⏱️ Horas", min_value=1, max_value=48, required=True)
            },
            hide_index=True
        )

        if st.button("💾 Guardar NCR en Google Sheets"):
            if "ncr" in st.session_state.db_ncrs.columns and ncr_num in st.session_state.db_ncrs["ncr"].astype(str).tolist():
                st.error(f"La NCR {ncr_num} ya existe. Evita duplicar registros.")
            else:
                df_guardar = df_edit.copy()
                df_guardar["fecha_prog"] = df_guardar["fecha_prog"].astype(str)
                registro_ts = f"{data['fecha']} {datetime.now().strftime('%H:%M:%S')}"
                estado_ini = (
                    "Pendiente Validación Supervisión"
                    if data["tipo_res"] == "Solución Directa Todista / Criterio de Supervisión"
                    else "Abierta"
                )

                # Construir la fila completa coincidiendo con la estructura actual de la hoja
                col_headers = list(st.session_state.db_ncrs.columns)
                row_dict = {col: "" for col in col_headers}
                
                row_dict["ncr"] = data["num"]
                row_dict["proyecto"] = data["proyecto"]
                row_dict["fecha"] = data["fecha"]
                row_dict["descripcion"] = data["descripcion"]
                row_dict["causa_raiz"] = data["causa"]
                row_dict["empresa"] = data["empresa"]
                row_dict["tipo_resolucion"] = data["tipo_res"]
                row_dict["estado_ncr"] = estado_ini
                row_dict["plan_json"] = json.dumps(df_guardar.to_dict(orient="records"), ensure_ascii=False)
                row_dict["cumplimiento_json"] = json.dumps(["NO Cumplió"] * len(df_guardar), ensure_ascii=False)
                row_dict["observaciones_json"] = json.dumps(["Pendiente de validación/ejecución"] * len(df_guardar), ensure_ascii=False)
                row_dict["fecha_registro"] = registro_ts
                if "fecha_hora_registro" in row_dict:
                    row_dict["fecha_hora_registro"] = registro_ts
                if "plazo_objetivo_dias" in row_dict:
                    row_dict["plazo_objetivo_dias"] = int(data["plazo_objetivo"])
                if "fecha_ejecucion" in row_dict:
                    row_dict["fecha_ejecucion"] = int(data["plazo_objetivo"])
                if "fase_estudio" in row_dict:
                    row_dict["fase_estudio"] = "Implementación (Después)"
                if "causa_raiz_analisis" in row_dict:
                    row_dict["causa_raiz_analisis"] = data["analisis"]
                if "propuesta_mitigacion" in row_dict:
                    row_dict["propuesta_mitigacion"] = data["propuesta"]
                if "correo_supervision" in row_dict:
                    row_dict["correo_supervision"] = data["correo"]

                fila_datos = [row_dict.get(c, "") for c in col_headers]

                try:
                    with st.spinner("Guardando registro en Google Sheets..."):
                        res = requests.post(URL_WEB_APP, json={"row": fila_datos})
                    if "OK" in res.text:
                        st.success(f"✅ NCR {data['num']} guardada correctamente en Google Sheets.")
                        st.session_state.pop("temp_ncr", None)
                        st.session_state.db_ncrs = load_db()
                        st.rerun()
                    else:
                        st.error(f"Ocurrió un error al guardar: {res.text}")
                except Exception as e:
                    st.error(f"Error de conexión al guardar: {e}")

# ==============================================================================
# 📱 FORMATO 2: MONITOREO EN CAMPO
# ==============================================================================
else:
    st.header("📱 Formato 2: Monitoreo en Campo y Liberación por Supervisión")

    df_bd = st.session_state.db_ncrs
    if df_bd.empty or "ncr" not in df_bd.columns or df_bd["ncr"].dropna().empty:
        st.warning("No hay No Conformidades registradas.")
    else:
        lista_ncrs = df_bd["ncr"].dropna().astype(str).tolist()
        ncr_sel = st.selectbox("📌 Selecciona la NCR a revisar", lista_ncrs)
        idx_fila = df_bd[df_bd["ncr"].astype(str) == ncr_sel].index[0]
        fila_ncr = df_bd.loc[idx_fila].copy()

        st.markdown(f"**Proyecto:** {fila_ncr.get('proyecto','')} | **Estado:** `{fila_ncr.get('estado_ncr','')}`")
        st.markdown(f"**Ubicación y falla:** {fila_ncr.get('descripcion','')}")
        st.markdown("---")

        historial = parse_json_list(fila_ncr.get("historial_json", "[]"), [])
        if historial:
            with st.expander("🕘 Historial de eventos de la NCR"):
                st.dataframe(pd.DataFrame(historial), use_container_width=True, hide_index=True)

        estado_actual = str(fila_ncr.get("estado_ncr", ""))

        # CASO 1: YA LEVANTADA Y CERRADA
        if estado_actual == "Levantada":
            st.success(f"✅ {ncr_sel} se encuentra levantada y liberada por Supervisión.")
            st.subheader("📜 Acta de Cierre Técnico")
            st.info(fila_ncr.get("acta_cierre", ""))

        # CASO 2: PENDIENTE DE VALIDACIÓN POR SUPERVISIÓN
        elif estado_actual == "Pendiente Validación Supervisión":
            st.warning("🔒 Esta propuesta se encuentra PENDIENTE DE VALIDACIÓN POR SUPERVISIÓN. El checklist de ejecución se activará una vez aprobada la propuesta.")

            col_v1, col_v2 = st.columns(2)
            sup_nombre = col_v1.text_input("👤 Nombre del Inspector/Supervisor", value=str(fila_ncr.get("supervisor", "")))
            dictamen_sup = col_v2.radio(
                "📌 Dictamen de Supervisión:",
                [
                    "✅ APROBADO (Ejecutar propuesta ligera con Todistas)",
                    "2. RECHAZADO (Reiterar sustento / Proponer nuevo ajuste)",
                    "🚨 RECHAZADO DEFINITIVO (Asumir reconstrucción total con Lookahead)"
                ]
            )

            objecion_inspector = ""
            if "RECHAZADO" in dictamen_sup:
                objecion_inspector = st.text_area(
                    "🗣️ Razón o motivo del rechazo del Inspector",
                    value=str(fila_ncr.get("objecion_supervision", "")),
                    placeholder="Escribe la objeción técnica..."
                )

            if st.button("📝 Registrar Dictamen de Supervisión"):
                if not sup_nombre.strip():
                    st.warning("Ingrese el nombre del supervisor antes de registrar el dictamen.")
                else:
                    st.session_state.db_ncrs.at[idx_fila, "supervisor"] = str(sup_nombre)
                    if "dictamen_supervision" in st.session_state.db_ncrs.columns:
                        st.session_state.db_ncrs.at[idx_fila, "dictamen_supervision"] = str(dictamen_sup)
                    if "objecion_supervision" in st.session_state.db_ncrs.columns:
                        st.session_state.db_ncrs.at[idx_fila, "objecion_supervision"] = str(objecion_inspector)

                    if "APROBADO" in dictamen_sup:
                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (Aprobada por Supervisión)"
                    elif "RECHAZADO DEFINITIVO" in dictamen_sup:
                        st.session_state.db_ncrs.at[idx_fila, "tipo_resolucion"] = "Reingreso Interpartidas (Secuencia Lookahead)"
                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (En Reconstrucción Lookahead)"

                    fila_actualizada = st.session_state.db_ncrs.loc[idx_fila].fillna("").astype(str).tolist()
                    requests.post(URL_WEB_APP, json={"row": fila_actualizada})
                    st.success("Dictamen guardado correctamente.")
                    st.session_state.db_ncrs = load_db()
                    st.rerun()

        # CASO 3: APROBADA O ABIERTA (MOSTRAR CHECKLIST DE CAMPO)
        else:
            plan = parse_json_list(fila_ncr.get("plan_json", "[]"), [])
            estado_pasos = parse_json_list(fila_ncr.get("cumplimiento_json", "[]"), [])
            obs_pasos = parse_json_list(fila_ncr.get("observaciones_json", "[]"), [])

            if not plan:
                st.warning("Esta NCR no tiene una secuencia registrada.")
            else:
                st.subheader("📋 Checklist de ejecución de contratistas")
                nuevos_estados = []
                nuevas_obs = []

                for idx, paso in enumerate(plan):
                    col_c1, col_c2 = st.columns([3, 4])
                    with col_c1:
                        estado_previo = idx < len(estado_pasos) and estado_pasos[idx] == "Cumplió"
                        chk = st.checkbox(
                            f"Paso {paso.get('paso', idx + 1)}: {paso.get('contratista', '')} - {paso.get('actividad', '')}",
                            value=estado_previo,
                            key=f"chk_{ncr_sel}_{idx}"
                        )
                        nuevos_estados.append("Cumplió" if chk else "NO Cumplió")
                    with col_c2:
                        val_obs = obs_pasos[idx] if idx < len(obs_pasos) else ""
                        txt_obs = st.text_input(f"Observación paso {idx + 1}", value=val_obs, key=f"txt_{ncr_sel}_{idx}")
                        nuevas_obs.append(txt_obs)

                if st.button("🔄 Guardar avance de checklist"):
                    st.session_state.db_ncrs.at[idx_fila, "cumplimiento_json"] = json.dumps(nuevos_estados, ensure_ascii=False)
                    st.session_state.db_ncrs.at[idx_fila, "observaciones_json"] = json.dumps(nuevas_obs, ensure_ascii=False)

                    fila_actualizada = st.session_state.db_ncrs.loc[idx_fila].fillna("").astype(str).tolist()
                    requests.post(URL_WEB_APP, json={"row": fila_actualizada})
                    st.success("Avance del checklist guardado correctamente.")
                    st.session_state.db_ncrs = load_db()
                    st.rerun()

                todos_ejecutados = len(nuevos_estados) > 0 and all(e == "Cumplió" for e in nuevos_estados)

                # INSPECCIÓN FINAL Y CIERRE TÉCNICO
                if todos_ejecutados:
                    st.markdown("---")
                    st.subheader("🕵️‍♂️ Inspección y Cierre Técnico por Supervisión")

                    col_sup1, col_sup2 = st.columns(2)
                    supervisor = col_sup1.text_input("👤 Inspector / Supervisor de Calidad", value=str(fila_ncr.get("supervisor", "")))
                    fecha_cierre_manual = col_sup2.date_input("📅 Fecha de Levantamiento / Cierre en campo", value=datetime.now())

                    obs_supervision = st.text_area("💬 Comentarios de la inspección final")

                    if st.button("🔒 Confirmar inspección y registrar cierre"):
                        if not supervisor.strip():
                            st.warning("Ingrese el nombre del supervisor antes de cerrar.")
                        else:
                            try:
                                with st.spinner("Generando borrador de Acta de Cierre Técnico y guardando..."):
                                    resp_cierre = generar_cierre_gpt(
                                        ncr_sel, fila_ncr.get("descripcion",""), supervisor, obs_supervision
                                    )

                                str_fecha_cierre = f"{fecha_cierre_manual.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M:%S')}"

                                # Garantizamos lectura de fecha de registro original probando varios campos posibles de la hoja
                                fecha_reg_raw = obtener_valor_columna(fila_ncr, ["fecha_registro", "fecha_hora_registro", "fecha"])
                                if not fecha_reg_raw:
                                    fecha_reg_raw = f"{str_fecha_cierre[:10]} 08:00:00"

                                try:
                                    f_inicio = pd.to_datetime(fecha_reg_raw)
                                    f_fin = pd.to_datetime(str_fecha_cierre)
                                    dias_calc = round(max(0.1, (f_fin - f_inicio).total_seconds() / 86400), 2)
                                except Exception:
                                    dias_calc = 1.0

                                texto_acta = f"Acta de Cierre Técnico - NCR {ncr_sel}\nAprobado por: {supervisor}\nFecha Cierre: {str_fecha_cierre}\nTiempo Levantamiento: {dias_calc} días\n\n{resp_cierre}"

                                st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Levantada"
                                
                                # Guardar en campos correspondientes de la hoja
                                for c_lev in ["fecha_aprobacion", "fecha_cierre", "fecha_hora_levantamiento"]:
                                    if c_lev in st.session_state.db_ncrs.columns:
                                        st.session_state.db_ncrs.at[idx_fila, c_lev] = str(str_fecha_cierre)

                                for c_t in ["fecha_inspeccion", "tiempo_levantamiento_dias"]:
                                    if c_t in st.session_state.db_ncrs.columns:
                                        st.session_state.db_ncrs.at[idx_fila, c_t] = str(dias_calc)

                                if "acta_cierre" in st.session_state.db_ncrs.columns:
                                    st.session_state.db_ncrs.at[idx_fila, "acta_cierre"] = str(texto_acta)

                                fila_actualizada = st.session_state.db_ncrs.loc[idx_fila].fillna("").astype(str).tolist()
                                res = requests.post(URL_WEB_APP, json={"row": fila_actualizada})

                                if "OK" in res.text:
                                    st.success(f"✅ {ncr_sel} liberada y cerrada correctamente. Tiempo levantamiento registrado: {dias_calc} días.")
                                    st.session_state.db_ncrs = load_db()
                                    st.rerun()
                                else:
                                    st.error(f"Respuesta inesperada al guardar cierre: {res.text}")
                            except Exception as e:
                                st.error(f"Error al cerrar la NCR: {e}")
