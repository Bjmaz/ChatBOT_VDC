¡Tienes toda la razón! En el bloque anterior faltó colocar explícitamente el encabezado de las librerías al inicio.

Aquí tienes el archivo streamlit_app.py completo, que empieza con todas las importaciones necesarias (import streamlit as st, import openai, etc.) y contiene el desarrollo completo de los 3 módulos:

Python
import streamlit as st
import openai
from datetime import datetime, timedelta
import pandas as pd
import json
import requests
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURACIÓN E INTEGRACIÓN
# ==============================================================================
st.set_page_config(page_title="ChatBot VDC - Gestión de NCRs", layout="wide")

client = openai.OpenAI(api_key=st.secrets["openai_api_key"])
conn = st.connection("gsheets", type=GSheetsConnection)

# 🔗 URL de tu Web App de Google Apps Script
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbzL25onMtSFb2VYdBBdWKbg9qqoj_9y_7kB8qbPy7olqXUhIx3h_F2A3MPeH_Hw7N29/exec"

CONTRATISTAS_LISTA = [
    "OBRA CIVIL", "PINTURA", "PAPEL TAPIZ", "MELAMINE", "LAMINADO/PARQUET",
    "ENCHAPE/CERÁMICO", "PUERTAS Y VENTANAS", "MAMPARAS/CRISTALERÍA",
    "II.SS (SANITARIAS)", "II.EE (ELÉCTRICAS)", "II.GG (GAS)",
    "ALBAÑILERÍA", "GRANITO/MÁRMOL", "DACI/AACI", "TODISTA / CUADRILLA INTERNA"
]

ESTADOS_CERRADOS = ["Levantada"]

BASE_COLUMNS = [
    "ncr", "proyecto", "fecha", "descripcion", "causa_raiz", "empresa",
    "tipo_resolucion", "estado_ncr", "plan_json", "cumplimiento_json",
    "observaciones_json", "acta_cierre",
    "fecha_hora_registro", "fecha_hora_levantamiento", "plazo_objetivo_dias",
    "tiempo_levantamiento_dias", "levantada_oportunamente", "fase_estudio",
    "fecha_hora_ultima_actualizacion", "supervisor", "dictamen_supervision",
    "objecion_supervision", "version_resolucion", "historial_json",
    "causa_raiz_analisis", "propuesta_mitigacion", "correo_supervision"
]


def empty_db():
    return pd.DataFrame(columns=BASE_COLUMNS)


def load_db():
    """Carga la base de datos de lectura desde Google Sheets."""
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty:
            return empty_db()
        if "ncr" not in df.columns:
            return empty_db()

        for col in BASE_COLUMNS:
            if col not in df.columns:
                if col in ["plan_json", "cumplimiento_json", "observaciones_json", "historial_json"]:
                    default = "[]"
                elif col == "plazo_objetivo_dias":
                    default = 3
                elif col == "version_resolucion":
                    default = 1
                elif col in ["causa_raiz_analisis", "propuesta_mitigacion", "correo_supervision"]:
                    default = ""
                else:
                    default = ""
                df[col] = default

        extras = [c for c in df.columns if c not in BASE_COLUMNS]
        df = df[BASE_COLUMNS + extras]
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


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def calcular_metricas(df):
    """Calcula los indicadores sobre el conjunto filtrado."""
    if df.empty:
        return {
            "total": 0, "cerradas": 0, "pendientes": 0,
            "tnc": None, "pnc": None, "pnco": None,
            "n_validas_tnc": 0, "n_oportunas": 0, "n_cerradas_con_plazo": 0
        }

    total = len(df)
    cerradas = int(df["estado_ncr"].isin(ESTADOS_CERRADOS).sum())
    pendientes = total - cerradas

    fecha_reg = pd.to_datetime(df["fecha_hora_registro"], errors="coerce")
    fecha_fin = pd.to_datetime(df["fecha_hora_levantamiento"], errors="coerce")
    tiempos = (fecha_fin - fecha_reg).dt.total_seconds() / 86400
    validos = tiempos.notna() & (tiempos >= 0)

    tnc = float(tiempos[validos].mean()) if validos.any() else None
    pnc = (pendientes / total * 100) if total else None

    plazos = pd.to_numeric(df["plazo_objetivo_dias"], errors="coerce")
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
    out["fecha_reg_dt"] = pd.to_datetime(out["fecha_hora_registro"], errors="coerce")
    out["fecha_lev_dt"] = pd.to_datetime(out["fecha_hora_levantamiento"], errors="coerce")
    out["tiempo_calculado_dias"] = (
        out["fecha_lev_dt"] - out["fecha_reg_dt"]
    ).dt.total_seconds() / 86400
    out["plazo_num"] = pd.to_numeric(out["plazo_objetivo_dias"], errors="coerce")
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

    if df_raw.empty or df_raw["ncr"].dropna().empty:
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
        tabla = df_f[[
            "ncr", "proyecto", "fecha_hora_registro", "fecha_hora_levantamiento",
            "estado_ncr", "plazo_objetivo_dias", "tiempo_calculado_dias", "causa_raiz", "empresa"
        ]].copy()
        tabla["tiempo_calculado_dias"] = tabla["tiempo_calculado_dias"].round(2)
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
            if ncr_num in st.session_state.db_ncrs["ncr"].astype(str).tolist():
                st.error(f"La NCR {ncr_num} ya existe. Evita duplicar registros.")
            else:
                df_guardar = df_edit.copy()
                df_guardar["fecha_prog"] = df_guardar["fecha_prog"].astype(str)
                registro_ts = f"{str(fecha_reg)} {datetime.now().strftime('%H:%M:%S')}"
                estado_ini = (
                    "Pendiente Validación Supervisión"
                    if data["tipo_res"] == "Solución Directa Todista / Criterio de Supervisión"
                    else "Abierta"
                )

                fila_datos = [
                    data["num"],
                    data["proyecto"],
                    data["fecha"],
                    data["descripcion"],
                    data["causa"],
                    data["empresa"],
                    data["tipo_res"],
                    estado_ini,
                    json.dumps(df_guardar.to_dict(orient="records"), ensure_ascii=False),
                    json.dumps(["NO Cumplió"] * len(df_guardar), ensure_ascii=False),
                    json.dumps(["Pendiente de validación/ejecución"] * len(df_guardar), ensure_ascii=False),
                    "",  # acta_cierre
                    registro_ts,
                    "",  # fecha_hora_levantamiento
                    int(data["plazo_objetivo"]),
                    "",  # tiempo_levantamiento_dias
                    "",  # levantada_oportunamente,
                    "Implementación (Después)",
                    now_str(),
                    "",  # supervisor
                    "",  # dictamen_supervision
                    "",  # objecion_supervision
                    1,   # version_resolucion
                    json.dumps([{
                        "fecha_hora": registro_ts,
                        "evento": "NCR registrada",
                        "detalle": "Registro inicial y generación de propuesta IA",
                        "estado": estado_ini
                    }], ensure_ascii=False),
                    data["analisis"],
                    data["propuesta"],
                    data["correo"]
                ]

                try:
                    with st.spinner("Guardando registro en Google Sheets..."):
                        res = requests.post(URL_WEB_APP, json={"row": fila_datos})
                    if res.text == "OK":
                        st.success(f"✅ NCR {data['num']} guardada correctamente en Google Sheets.")
                        st.session_state.pop("temp_ncr", None)
                        st.session_state.db_ncrs = load_db()
                        st.rerun()
                    else:
                        st.error(f"Ocurrió un error al guardar: {res.text}")
                except Exception as e:
                    st.error(f"Error de conexión al guardar: {e}")

# ==============================================================================
# 📱 FORMATO 2: MONITOREO EN CAMPO (COMPLETO)
# ==============================================================================
else:
    st.header("📱 Formato 2: Monitoreo en Campo y Liberación por Supervisión")

    df_bd = st.session_state.db_ncrs
    if df_bd.empty or df_bd["ncr"].dropna().empty:
        st.warning("No hay No Conformidades registradas.")
    else:
        lista_ncrs = df_bd["ncr"].dropna().astype(str).tolist()
        ncr_sel = st.selectbox("📌 Selecciona la NCR a revisar", lista_ncrs)
        idx_fila = df_bd[df_bd["ncr"].astype(str) == ncr_sel].index[0]
        fila_ncr = df_bd.loc[idx_fila].copy()

        st.markdown(f"**Proyecto:** {fila_ncr['proyecto']} | **Estado:** `{fila_ncr['estado_ncr']}`")
        st.markdown(f"**Ubicación y falla:** {fila_ncr['descripcion']}")
        st.markdown("---")

        historial = parse_json_list(fila_ncr.get("historial_json", "[]"), [])
        if historial:
            with st.expander("🕘 Historial de eventos de la NCR"):
                st.dataframe(pd.DataFrame(historial), use_container_width=True, hide_index=True)

        if fila_ncr["estado_ncr"] == "Levantada":
            st.success(f"✅ {ncr_sel} se encuentra levantada y liberada por Supervisión.")
            st.subheader("📜 Acta de Cierre Técnico")
            st.info(fila_ncr.get("acta_cierre", ""))

        else:
            # NEGOCIACIÓN / VALIDACIÓN DE SUPERVISIÓN
            if fila_ncr["estado_ncr"] == "Pendiente Validación Supervisión":
                st.warning("Esta propuesta se encuentra pendiente de validación de Supervisión.")

                col_v1, col_v2 = st.columns(2)
                sup_nombre = col_v1.text_input("👤 Nombre del Inspector/Supervisor", value=fila_ncr.get("supervisor", ""))
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
                        value=fila_ncr.get("objecion_supervision", ""),
                        placeholder="Escribe la objeción técnica..."
                    )

                if st.button("📝 Registrar Dictamen de Supervisión"):
                    st.session_state.db_ncrs.at[idx_fila, "supervisor"] = sup_nombre
                    st.session_state.db_ncrs.at[idx_fila, "dictamen_supervision"] = dictamen_sup
                    st.session_state.db_ncrs.at[idx_fila, "objecion_supervision"] = objecion_inspector
                    st.session_state.db_ncrs.at[idx_fila, "fecha_hora_ultima_actualizacion"] = now_str()

                    if "APROBADO" in dictamen_sup:
                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (Aprobada por Supervisión)"
                        st.success("Propuesta aprobada. Se habilitó el checklist.")
                        st.rerun()

                    elif "RECHAZADO (Reiterar" in dictamen_sup:
                        if not objecion_inspector:
                            st.warning("Ingrese la objeción del inspector para generar la refutación.")
                        else:
                            try:
                                with st.spinner("Generando borrador de respuesta técnica..."):
                                    prompt_reiterar = f"""
La Supervisión ({sup_nombre}) rechazó la propuesta inicial para {ncr_sel}: '{fila_ncr['descripcion']}'.
Objeción del Inspector: '{objecion_inspector}'.
Genera un borrador de respuesta técnica formal que responda a la objeción sin inventar normas.
"""
                                    nuevo_correo = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[{"role": "user", "content": prompt_reiterar}]
                                    ).choices[0].message.content
                                st.session_state[f"refutacion_{ncr_sel}"] = nuevo_correo
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error generando refutación: {e}")

                    elif "RECHAZADO DEFINITIVO" in dictamen_sup:
                        st.session_state.db_ncrs.at[idx_fila, "tipo_resolucion"] = "Reingreso Interpartidas (Secuencia Lookahead)"
                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (En Reconstrucción Lookahead)"
                        st.success("Reestructurado a secuencia Lookahead.")
                        st.rerun()

            if f"refutacion_{ncr_sel}" in st.session_state:
                st.markdown("---")
                st.info("💡 BORRADOR DE RESPUESTA TÉCNICA")
                st.text_area("Texto para responder al Inspector:", value=st.session_state[f"refutacion_{ncr_sel}"], height=200)

            # CHECKLIST DE PASOS
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

                todos_ejecutados = len(nuevos_estados) > 0 and all(e == "Cumplió" for e in nuevos_estados)

                # INSPECCIÓN FINAL Y CIERRE
                if todos_ejecutados:
                    st.markdown("---")
                    st.subheader("🕵️‍♂️ Inspección y liberación por Supervisión")
                    supervisor = st.text_input("👤 Inspector / Supervisor de Calidad", value=fila_ncr.get("supervisor", ""))
                    obs_supervision = st.text_area("💬 Comentarios de la inspección")

                    if st.button("🔒 Confirmar inspección y registrar cierre"):
                        if not supervisor.strip():
                            st.warning("Ingrese el nombre del supervisor antes de cerrar.")
                        else:
                            try:
                                with st.spinner("Generando borrador de Acta de Cierre Técnico..."):
                                    resp_cierre = generar_cierre_gpt(
                                        ncr_sel, fila_ncr["descripcion"], supervisor, obs_supervision
                                    )

                                fecha_cierre = now_str()
                                fecha_inicio = pd.to_datetime(fila_ncr.get("fecha_hora_registro"), errors="coerce")
                                fecha_fin = pd.to_datetime(fecha_cierre, errors="coerce")
                                dias = round((fecha_fin - fecha_inicio).total_seconds() / 86400, 2) if pd.notna(fecha_inicio) else ""

                                st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Levantada"
                                st.session_state.db_ncrs.at[idx_fila, "fecha_hora_levantamiento"] = fecha_cierre
                                st.session_state.db_ncrs.at[idx_fila, "tiempo_levantamiento_dias"] = dias
                                st.session_state.db_ncrs.at[idx_fila, "acta_cierre"] = (
                                    f"Acta de Cierre Técnico - NCR {ncr_sel}\nAprobado por: {supervisor}\nFecha: {fecha_cierre}\n\n{resp_cierre}"
                                )
                                st.success(f"✅ {ncr_sel} liberada y cerrada correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al cerrar la NCR: {e}")
