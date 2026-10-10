import streamlit as st
import openai
from datetime import datetime, timedelta
import pandas as pd
import json
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
st.set_page_config(page_title="ChatBot VDC - Gestión de NCRs", layout="wide")

client = openai.OpenAI(api_key=st.secrets["openai_api_key"])
conn = st.connection("gsheets", type=GSheetsConnection)

CONTRATISTAS_LISTA = [
    "OBRA CIVIL", "PINTURA", "PAPEL TAPIZ", "MELAMINE", "LAMINADO/PARQUET",
    "ENCHAPE/CERÁMICO", "PUERTAS Y VENTANAS", "MAMPARAS/CRISTALERÍA",
    "II.SS (SANITARIAS)", "II.EE (ELÉCTRICAS)", "II.GG (GAS)",
    "ALBAÑILERÍA", "GRANITO/MÁRMOL", "DACI/AACI", "TODISTA / CUADRILLA INTERNA"
]

ESTADOS_CERRADOS = ["Levantada"]
FASES_ESTUDIO = ["Línea base (Antes)", "Implementación (Después)"]

BASE_COLUMNS = [
    "ncr", "proyecto", "fecha", "descripcion", "causa_raiz", "empresa",
    "tipo_resolucion", "estado_ncr", "plan_json", "cumplimiento_json",
    "observaciones_json", "acta_cierre",
    # Nuevos campos para medición de tesis
    "fecha_hora_registro", "fecha_hora_levantamiento", "plazo_objetivo_dias",
    "tiempo_levantamiento_dias", "levantada_oportunamente", "fase_estudio",
    "fecha_hora_ultima_actualizacion", "supervisor", "dictamen_supervision",
    "objecion_supervision", "version_resolucion", "historial_json",
    "causa_raiz_analisis", "propuesta_mitigacion", "correo_supervision"
]


def empty_db():
    return pd.DataFrame(columns=BASE_COLUMNS)


def load_db():
    """Carga Google Sheets y adapta hojas antiguas al nuevo esquema."""
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
                elif col in ["levantada_oportunamente"]:
                    default = ""
                elif col == "fase_estudio":
                    default = ""
                elif col in ["causa_raiz_analisis", "propuesta_mitigacion", "correo_supervision"]:
                    default = ""
                else:
                    default = ""
                df[col] = default

        # Asegura columnas en un orden estable. No elimina columnas adicionales existentes.
        extras = [c for c in df.columns if c not in BASE_COLUMNS]
        df = df[BASE_COLUMNS + extras]
        return df
    except Exception as e:
        st.session_state.load_error = str(e)
        return empty_db()


if "db_ncrs" not in st.session_state:
    st.session_state.db_ncrs = load_db()


def save_db():
    """Guarda la base y reporta errores; nunca oculta una falla de persistencia."""
    try:
        st.session_state.db_ncrs = st.session_state.db_ncrs.copy()
        conn.update(data=st.session_state.db_ncrs)
        return True, ""
    except Exception as e:
        return False, str(e)


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
    """Calcula los tres indicadores de la tesis sobre el conjunto filtrado."""
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
    """Agrega campos calculados sin modificar la base persistida."""
    out = df.copy()
    out["fecha_reg_dt"] = pd.to_datetime(out["fecha_hora_registro"], errors="coerce")
    out["fecha_lev_dt"] = pd.to_datetime(out["fecha_hora_levantamiento"], errors="coerce")
    out["tiempo_calculado_dias"] = (
        out["fecha_lev_dt"] - out["fecha_reg_dt"]
    ).dt.total_seconds() / 86400
    out["plazo_num"] = pd.to_numeric(out["plazo_objetivo_dias"], errors="coerce")
    out["oportuna_calculada"] = (
        out["estado_ncr"].isin(ESTADOS_CERRADOS)
        & out["tiempo_calculado_dias"].notna()
        & out["plazo_num"].notna()
        & (out["plazo_num"] > 0)
        & (out["tiempo_calculado_dias"] <= out["plazo_num"])
    )
    return out


def registrar_historial(row, evento, detalle=""):
    historial = parse_json_list(row.get("historial_json", "[]"), [])
    historial.append({
        "fecha_hora": now_str(),
        "evento": evento,
        "detalle": detalle,
        "estado": row.get("estado_ncr", "")
    })
    return json.dumps(historial, ensure_ascii=False)


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

OBJETIVO: proponer una solución técnicamente defendible para presentar a Supervisión y generar una matriz
Lookahead editable por el usuario antes de guardar la NCR. No debes favorecer la solución directa por defecto.

RAZONAMIENTO REQUERIDO:
1. Explica la falla, las posibles causas y las interferencias. Separa hechos conocidos de hipótesis por verificar.
2. Evalúa si una mitigación localizada es viable o si puede ocultar una falla, comprometer la durabilidad,
   la seguridad, la funcionalidad, la impermeabilidad, la garantía o el criterio de aceptación del acabado.
3. Considera la normativa técnica peruana aplicable únicamente si puede identificarse con confianza; señala
   qué plano, especificación técnica (E.T.), ficha técnica del fabricante, tolerancia del proyecto o requisito
   del RNE debe comprobarse. No inventes artículos, numerales, tolerancias ni citas normativas.
4. Usa ISO 9001 como marco de gestión de no conformidades, corrección, verificación y registro; no la presentes
   como norma que prescribe una solución constructiva concreta.
5. Clasifica la complejidad como BAJA, MEDIA o ALTA y recomienda una estrategia: SOLUCION_DIRECTA,
   SOLUCION_DIRECTA_CON_APOYO o RECONSTRUCCION_LOOKAHEAD.
6. Si es BAJA, plantea una secuencia principalmente con TODISTA / CUADRILLA INTERNA. Si es MEDIA, agrega
   únicamente las especialidades necesarias y explica por qué. Si es ALTA o la mitigación no es justificable,
   recomienda reconstrucción y ordena las especialidades según sus dependencias. Las fechas son propuestas
   preliminares y las horas son estimaciones que el equipo debe revisar.
7. Para un encuentro/junta visible junto a un mueble bajo y piso terminado, puedes evaluar como hipótesis
   un sellador compatible, del color adecuado y aprobado por fabricante/Supervisión; no lo declares aceptable
   sin comprobar compatibilidad, ancho/profundidad de junta, adherencia, acabado, limpieza y criterio del proyecto.
8. Redacta un borrador de correo que solicite evaluación/aprobación, sin afirmar que la Supervisión ya aprobó.

Devuelve ÚNICAMENTE JSON válido con esta estructura exacta:
{{
  "causa_raiz_analisis": "...",
  "complejidad": "BAJA | MEDIA | ALTA",
  "estrategia_recomendada": "SOLUCION_DIRECTA | SOLUCION_DIRECTA_CON_APOYO | RECONSTRUCCION_LOOKAHEAD",
  "justificacion_no_retrabajo": "...",
  "propuesta_mitigacion": "...",
  "verificaciones_previas": ["..."],
  "referencias_por_verificar": ["RNE/E.T./plano/ficha técnica aplicable, sin inventar numerales"],
  "correo_supervision": "...",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f_p1}", "contratista": "TODISTA / CUADRILLA INTERNA", "actividad": "Actividad concreta y verificable", "horas": 2}}
  ]
}}
La secuencia debe tener de 1 a 6 pasos, en orden lógico, con contratistas seleccionados de la lista disponible.
Si faltan datos críticos, indícalos en verificaciones_previas y redacta una propuesta condicionada, no una certeza.
"""
    else:
        prompt = f"""
Analiza la No Conformidad {ncr_num}: '{descripcion}'.
Especialidad involucrada: {contratista_causa}.

Diseña una secuencia preliminar de reingreso interpartidas. Identifica dependencias constructivas,
contratistas y actividades necesarias. No inventes requisitos normativos específicos.

Devuelve un JSON estricto con:
{{
  "causa_raiz_analisis": "Análisis breve de causa raíz e interferencias",
  "justificacion_no_retrabajo": "No aplica: se plantea reconstrucción/reingreso",
  "propuesta_mitigacion": "Secuencia preliminar Lookahead",
  "correo_supervision": "",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f_p1}", "contratista": "{contratista_causa}", "actividad": "Desmontaje o retiro del elemento afectado", "horas": 2}},
    {{"paso": 2, "fecha_prog": "{f_p2}", "contratista": "OBRA CIVIL", "actividad": "Resane, nivelación y preparación de base", "horas": 4}},
    {{"paso": 3, "fecha_prog": "{f_p2}", "contratista": "PINTURA", "actividad": "Preparación y restitución de acabado", "horas": 4}},
    {{"paso": 4, "fecha_prog": "{f_p4}", "contratista": "{contratista_causa}", "actividad": "Instalación/montaje final y entrega", "horas": 2}}
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
Observaciones del supervisor: '{observaciones}'.
Redacta un borrador de conclusión técnica final de máximo 3 líneas para un Acta de Cierre Técnico.
No afirmes una certificación normativa ni una firma digital. La aprobación pertenece al supervisor.
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
    st.warning(f"No se pudo leer Google Sheets al iniciar: {st.session_state.load_error}")

# ==============================================================================
# DASHBOARD DE INDICADORES
# ==============================================================================
if formato == "📊 Dashboard de Indicadores":
    st.header("📊 Panel de Indicadores de Gestión de NCR")
    st.write("Los indicadores se calculan sobre las NCR filtradas. El indicador 3 considera únicamente NCR cerradas con plazo objetivo registrado.")

    df_raw = st.session_state.db_ncrs.copy()

    if df_raw.empty or df_raw["ncr"].dropna().empty:
        st.info("Aún no existen NCR registradas. Registra NCR desde el Formato 1 para activar el panel.")
    else:
        df_calc = preparar_df_indicadores(df_raw)

        # Filtros
        f1, f2, f3 = st.columns(3)
        proyectos = sorted([str(x) for x in df_raw["proyecto"].dropna().unique() if str(x).strip()])
        fases = [x for x in FASES_ESTUDIO if x in set(df_raw["fase_estudio"].astype(str))]
        contratistas = sorted([str(x) for x in df_raw["causa_raiz"].dropna().unique() if str(x).strip()])

        with f1:
            proyecto_sel = st.multiselect("Proyecto", proyectos)
        with f2:
            fase_sel = st.multiselect("Fase del estudio", fases)
        with f3:
            contratista_sel = st.multiselect("Especialidad", contratistas)

        f4, f5 = st.columns(2)
        fecha_min = pd.to_datetime(df_calc["fecha_reg_dt"], errors="coerce").min()
        fecha_max = pd.to_datetime(df_calc["fecha_reg_dt"], errors="coerce").max()
        fecha_min_d = fecha_min.date() if pd.notna(fecha_min) else datetime.now().date()
        fecha_max_d = fecha_max.date() if pd.notna(fecha_max) else datetime.now().date()

        with f4:
            rango = st.date_input("Periodo de registro", value=(fecha_min_d, fecha_max_d))
        with f5:
            estados = st.multiselect("Estado", sorted(df_raw["estado_ncr"].dropna().astype(str).unique()))

        if isinstance(rango, tuple) and len(rango) == 2:
            inicio, fin = rango
        else:
            inicio = fin = rango

        mask = pd.Series(True, index=df_calc.index)
        if proyecto_sel:
            mask &= df_calc["proyecto"].isin(proyecto_sel)
        if fase_sel:
            mask &= df_calc["fase_estudio"].isin(fase_sel)
        if contratista_sel:
            mask &= df_calc["causa_raiz"].isin(contratista_sel)
        if estados:
            mask &= df_calc["estado_ncr"].isin(estados)
        if inicio and fin:
            mask &= df_calc["fecha_reg_dt"].dt.date.between(inicio, fin)

        df_f = df_calc.loc[mask].copy()
        m = calcular_metricas(df_f)

        st.markdown("### Indicadores de la tesis")
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("TNC — Tiempo promedio de levantamiento", "—" if m["tnc"] is None else f"{m['tnc']:.2f} días")
            st.caption(f"NCR con fecha de registro y levantamiento válidas: {m['n_validas_tnc']}")
        with k2:
            st.metric("PNC — NCR pendientes de cierre", "—" if m["pnc"] is None else f"{m['pnc']:.1f}%")
            st.caption(f"Pendientes: {m['pendientes']} de {m['total']} NCR")
        with k3:
            st.metric("PNCO — NCR levantadas oportunamente", "—" if m["pnco"] is None else f"{m['pnco']:.1f}%")
            st.caption(f"Oportunas: {m['n_oportunas']} de {m['n_cerradas_con_plazo']} NCR cerradas con plazo")

        st.markdown("### Lectura rápida del proceso")
        a, b, c, d = st.columns(4)
        a.metric("NCR registradas", m["total"])
        b.metric("NCR levantadas", m["cerradas"])
        c.metric("NCR pendientes", m["pendientes"])
        mediana = df_f["tiempo_calculado_dias"].dropna().median() if not df_f.empty else None
        d.metric("Mediana de levantamiento", "—" if pd.isna(mediana) else f"{mediana:.2f} días")

        # Comparación Antes vs Después para la tesis
        if set(df_f["fase_estudio"].dropna().astype(str)) >= set(FASES_ESTUDIO):
            st.markdown("### Comparación para evaluación de la mejora")
            filas = []
            for fase in FASES_ESTUDIO:
                sub = df_f[df_f["fase_estudio"] == fase]
                mm = calcular_metricas(sub)
                filas.append({
                    "Fase": fase,
                    "NCR registradas": mm["total"],
                    "TNC (días)": None if mm["tnc"] is None else round(mm["tnc"], 2),
                    "PNC (%)": None if mm["pnc"] is None else round(mm["pnc"], 1),
                    "PNCO (%)": None if mm["pnco"] is None else round(mm["pnco"], 1),
                })
            comp = pd.DataFrame(filas)
            st.dataframe(comp, use_container_width=True, hide_index=True)

            antes = comp.iloc[0]
            despues = comp.iloc[1]
            if pd.notna(antes["TNC (días)"]) and pd.notna(despues["TNC (días)"]) and antes["TNC (días)"] != 0:
                reduccion = (antes["TNC (días)"] - despues["TNC (días)"]) / antes["TNC (días)"] * 100
                st.success(f"Reducción relativa del tiempo promedio de levantamiento: {reduccion:.1f}%.")

        # Tendencia mensual
        st.markdown("### Evolución mensual del tiempo de levantamiento")
        cerradas = df_f[df_f["tiempo_calculado_dias"].notna()].copy()
        if not cerradas.empty:
            cerradas["mes"] = cerradas["fecha_lev_dt"].dt.to_period("M").astype(str)
            tendencia = cerradas.groupby("mes")["tiempo_calculado_dias"].mean().reset_index()
            tendencia.columns = ["Mes", "TNC promedio (días)"]
            st.line_chart(tendencia.set_index("Mes"))
        else:
            st.info("Aún no hay NCR cerradas con fechas suficientes para mostrar una tendencia.")

        # Estado de NCR
        st.markdown("### Distribución del estado de las NCR")
        estados_df = df_f["estado_ncr"].value_counts().rename_axis("Estado").reset_index(name="NCR")
        st.bar_chart(estados_df.set_index("Estado"))

        # Tabla de control individual
        st.markdown("### Trazabilidad individual de NCR")
        tabla = df_f[[
            "ncr", "proyecto", "fase_estudio", "fecha_hora_registro", "fecha_hora_levantamiento",
            "estado_ncr", "plazo_objetivo_dias", "tiempo_calculado_dias", "oportuna_calculada",
            "causa_raiz", "empresa", "version_resolucion"
        ]].copy()
        tabla.rename(columns={
            "ncr": "NCR", "proyecto": "Proyecto", "fase_estudio": "Fase",
            "fecha_hora_registro": "Registro", "fecha_hora_levantamiento": "Levantamiento",
            "estado_ncr": "Estado", "plazo_objetivo_dias": "Plazo objetivo (días)",
            "tiempo_calculado_dias": "Tiempo (días)", "oportuna_calculada": "Oportuna",
            "causa_raiz": "Especialidad", "empresa": "Empresa", "version_resolucion": "Versión"
        }, inplace=True)
        tabla["Tiempo (días)"] = tabla["Tiempo (días)"].round(2)
        st.dataframe(tabla, use_container_width=True, hide_index=True)

        csv = tabla.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Descargar tabla de indicadores (CSV)", csv, "indicadores_ncr.csv", "text/csv")

# ==============================================================================
# FORMATO 1
# ==============================================================================
elif formato == "Formato 1: Registro e ICE (Oficina)":
    st.header("📋 Formato 1: Registro de NCR y Planificación de Subsanación")

    with st.form("form_ncr"):
        col1, col2, col3 = st.columns([1, 2, 1])
        ncr_num = col1.text_input("🔢 N° de NCR / Observación", placeholder="Ej: NCR-001 o OBS-042")
        proyecto = col2.text_input("🏗️ Proyecto", placeholder="Ej: Alto Bellavista II")
        fecha_reg = col3.date_input("📅 Fecha de identificación / registro", datetime.now())

        descripcion = st.text_area(
            "⚠️ Ubicación y descripción de la falla / observación RI-RF",
            placeholder="Ingrese piso, ambiente, eje y detalle técnico de la observación..."
        )

        col_a, col_b = st.columns(2)
        contratista_causa = col_a.selectbox("👷 Especialidad involucrada", CONTRATISTAS_LISTA)
        subcontratista = col_b.text_input("🏢 Empresa subcontratista / cuadrilla", placeholder="Nombre de empresa responsable")

        col_c, col_d = st.columns(2)
        fase_estudio = col_c.selectbox("📚 Fase del estudio", FASES_ESTUDIO)
        plazo_objetivo = col_d.number_input(
            "⏱️ Plazo objetivo de levantamiento (días)", min_value=1, max_value=60, value=3,
            help="Define el plazo contra el cual se calculará PNCO. Ajusta este valor al estándar o criterio establecido para tu proyecto."
        )

        tipo_resolucion = st.radio(
            "🛠 Modalidad de subsanación:",
            [
                "Reingreso Interpartidas (Secuencia Lookahead)",
                "Solución Directa Todista / Criterio de Supervisión"
            ]
        )

        obs_adicional = ""
        if tipo_resolucion == "Solución Directa Todista / Criterio de Supervisión":
            obs_adicional = st.text_input(
                "💬 Criterio de campo deseado (opcional)",
                placeholder="Ejemplo: colocar sellador gris sin retirar mueble ni romper enchape."
            )

        btn_analizar = st.form_submit_button("🔍 Generar propuesta con ChatBot VDC")

    if btn_analizar and descripcion and ncr_num:
        try:
            with st.spinner("Procesando análisis de restricciones e interferencias con IA..."):
                res_json = json.loads(procesar_ncr_gpt(
                    ncr_num, descripcion, contratista_causa, tipo_resolucion, str(fecha_reg), obs_adicional
                ))
                st.session_state.temp_ncr = {
                    "num": ncr_num, "proyecto": proyecto, "fecha": str(fecha_reg),
                    "descripcion": descripcion, "causa": contratista_causa, "empresa": subcontratista,
                    "tipo_res": tipo_resolucion, "fase_estudio": fase_estudio,
                    "plazo_objetivo": plazo_objetivo,
                    "analisis": res_json.get("causa_raiz_analisis", ""),
                    "justificacion": res_json.get("justificacion_no_retrabajo", ""),
                    "complejidad": res_json.get("complejidad", "No determinada"),
                    "estrategia_recomendada": res_json.get("estrategia_recomendada", ""),
                    "verificaciones_previas": res_json.get("verificaciones_previas", []),
                    "referencias_por_verificar": res_json.get("referencias_por_verificar", []),
                    "propuesta": res_json.get("propuesta_mitigacion", ""),
                    "correo": res_json.get("correo_supervision", ""),
                    "secuencia": res_json.get("secuencia_propuesta", [])
                }
        except Exception as e:
            st.error(f"No se pudo generar la propuesta con IA: {e}")
    elif btn_analizar:
        st.warning("Ingrese el N° de NCR y la descripción antes de generar el análisis.")

    if "temp_ncr" in st.session_state:
        data = st.session_state.temp_ncr
        st.markdown("---")

        st.info(f"**Análisis técnico:** {data['analisis']}")

        if data["tipo_res"] == "Solución Directa Todista / Criterio de Supervisión":
            st.subheader("🛡 Evaluación de alternativa sin retrabajo invasivo")
            st.warning(data["justificacion"])
            c1, c2 = st.columns(2)
            c1.metric("Complejidad estimada por IA", data.get("complejidad", "No determinada"))
            c2.write("**Estrategia recomendada por IA:**")
            c2.write(data.get("estrategia_recomendada", "Pendiente de evaluación"))
            if data.get("verificaciones_previas"):
                with st.expander("Verificaciones técnicas antes de presentar a Supervisión", expanded=True):
                    for item in data["verificaciones_previas"]:
                        st.markdown(f"- {item}")
            if data.get("referencias_por_verificar"):
                with st.expander("Documentos y referencias normativas que deben comprobarse"):
                    for item in data["referencias_por_verificar"]:
                        st.markdown(f"- {item}")
            if data.get("estrategia_recomendada") == "RECONSTRUCCION_LOOKAHEAD":
                st.error("La IA considera que la solución directa podría no ser suficiente. Revisa la recomendación y cambia la modalidad a Reingreso Interpartidas si corresponde antes de guardar.")
            elif data.get("estrategia_recomendada") == "SOLUCION_DIRECTA_CON_APOYO":
                st.info("La IA propone una solución directa con apoyo de otra especialidad. Revisa los contratistas y la secuencia editable antes de guardar.")

            st.subheader("🛠️ Propuesta de mitigación")
            propuesta_edit = st.text_area("Ajusta la propuesta antes de enviarla a Supervisión:", value=data["propuesta"], height=100)
            st.session_state.temp_ncr["propuesta"] = propuesta_edit

            st.subheader("✉️ Borrador para validación de Supervisión")
            correo_edit = st.text_area("Texto para correo/WhatsApp:", value=data["correo"], height=180)
            st.session_state.temp_ncr["correo"] = correo_edit

        st.subheader("⏳ Matriz de subsanación programada")
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
                "horas": st.column_config.NumberColumn("⏱️ Horas estimadas", min_value=1, max_value=48, required=True)
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

                nueva = {
                    "ncr": data["num"],
                    "proyecto": data["proyecto"],
                    "fecha": data["fecha"],
                    "descripcion": data["descripcion"],
                    "causa_raiz": data["causa"],
                    "empresa": data["empresa"],
                    "tipo_resolucion": data["tipo_res"],
                    "estado_ncr": estado_ini,
                    "plan_json": json.dumps(df_guardar.to_dict(orient="records"), ensure_ascii=False),
                    "cumplimiento_json": json.dumps(["NO Cumplió"] * len(df_guardar), ensure_ascii=False),
                    "observaciones_json": json.dumps(["Pendiente de validación/ejecución"] * len(df_guardar), ensure_ascii=False),
                    "acta_cierre": "",
                    "fecha_hora_registro": registro_ts,
                    "fecha_hora_levantamiento": "",
                    "plazo_objetivo_dias": int(data["plazo_objetivo"]),
                    "tiempo_levantamiento_dias": "",
                    "levantada_oportunamente": "",
                    "fase_estudio": data["fase_estudio"],
                    "fecha_hora_ultima_actualizacion": now_str(),
                    "supervisor": "",
                    "dictamen_supervision": "",
                    "objecion_supervision": "",
                    "version_resolucion": 1,
                    "historial_json": json.dumps([{
                        "fecha_hora": registro_ts,
                        "evento": "NCR registrada",
                        "detalle": "Registro inicial y generación de propuesta IA",
                        "estado": estado_ini
                    }], ensure_ascii=False),
                    "causa_raiz_analisis": data["analisis"],
                    "propuesta_mitigacion": data["propuesta"],
                    "correo_supervision": data["correo"]
                }

                st.session_state.db_ncrs = pd.concat([st.session_state.db_ncrs, pd.DataFrame([nueva])], ignore_index=True)
                ok, err = save_db()
                if ok:
                    st.success(f"{data['num']} guardada correctamente. Ya puedes continuar en Formato 2 y revisar los indicadores.")
                    st.session_state.pop("temp_ncr", None)
                else:
                    st.error(f"No se pudo guardar la NCR en Google Sheets: {err}")
                    if "Public Spreadsheet cannot be written" in str(err) or "Service Account" in str(err):
                        st.markdown("""
**Configuración necesaria para habilitar el guardado:**
1. Configura una cuenta de servicio de Google y habilita Google Sheets API y Google Drive API en Google Cloud.
2. Comparte la hoja con el valor `client_email` de esa cuenta y otórgale permiso de **Editor**.
3. En `.streamlit/secrets.toml` configura `[connections.gsheets]` con `type = "service_account"` y las credenciales de la cuenta.
4. Reinicia la aplicación y verifica que `spreadsheet` apunte a la hoja correcta y `worksheet` al nombre de la pestaña.

No pegues la clave privada en el código ni en el chat. La NCR no quedó persistida en Google Sheets hasta corregir esta configuración.
""")

# ==============================================================================
# FORMATO 2
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

        st.markdown(
            f"**Proyecto:** {fila_ncr['proyecto']} | **Fase:** `{fila_ncr.get('fase_estudio', '')}` | "
            f"**Estado:** `{fila_ncr['estado_ncr']}` | **Plazo objetivo:** `{fila_ncr.get('plazo_objetivo_dias', '')}` días"
        )
        st.markdown(f"**Ubicación y falla:** {fila_ncr['descripcion']}")
        st.markdown("---")

        # Historial resumido
        historial = parse_json_list(fila_ncr.get("historial_json", "[]"), [])
        if historial:
            with st.expander("🕘 Historial de eventos de la NCR"):
                st.dataframe(pd.DataFrame(historial), use_container_width=True, hide_index=True)

        if fila_ncr["estado_ncr"] == "Levantada":
            st.success(f"✅ {ncr_sel} se encuentra levantada y liberada por Supervisión.")
            st.subheader("📜 Acta de Cierre Técnico")
            st.info(fila_ncr.get("acta_cierre", ""))
            st.caption("El texto es generado por IA como borrador de cierre; la aprobación corresponde al supervisor registrado.")

        else:
            # ------------------------------------------------------------------
            # NEGOCIACIÓN CON SUPERVISIÓN
            # ------------------------------------------------------------------
            if fila_ncr["estado_ncr"] == "Pendiente Validación Supervisión":
                st.warning("Esta propuesta se encuentra pendiente de validación de Supervisión.")

                col_v1, col_v2 = st.columns(2)
                sup_nombre = col_v1.text_input("👤 Nombre de quien revisa", value=fila_ncr.get("supervisor", ""))
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
                        placeholder="Escribe la objeción técnica concreta."
                    )

                if st.button("📝 Registrar Dictamen de Supervisión"):
                    st.session_state.db_ncrs.at[idx_fila, "supervisor"] = sup_nombre
                    st.session_state.db_ncrs.at[idx_fila, "dictamen_supervision"] = dictamen_sup
                    st.session_state.db_ncrs.at[idx_fila, "objecion_supervision"] = objecion_inspector
                    st.session_state.db_ncrs.at[idx_fila, "fecha_hora_ultima_actualizacion"] = now_str()

                    if "APROBADO" in dictamen_sup:
                        st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (Aprobada por Supervisión)"
                        row_dict = st.session_state.db_ncrs.loc[idx_fila].to_dict()
                        st.session_state.db_ncrs.at[idx_fila, "historial_json"] = registrar_historial(
                            row_dict, "Propuesta aprobada por Supervisión", f"Supervisor: {sup_nombre}"
                        )
                        ok, err = save_db()
                        if ok:
                            st.success("Propuesta aprobada. Se habilitó el checklist.")
                            st.rerun()
                        else:
                            st.error(f"No se pudo guardar el dictamen: {err}")

                    elif "RECHAZADO (Reiterar" in dictamen_sup:
                        if not objecion_inspector:
                            st.warning("Ingrese la objeción del inspector para generar la refutación.")
                        else:
                            try:
                                with st.spinner("Generando borrador de respuesta técnica..."):
                                    prompt_reiterar = f"""
La Supervisión ({sup_nombre}) rechazó la propuesta inicial para {ncr_sel}: '{fila_ncr['descripcion']}'.
Objeción del Inspector: '{objecion_inspector}'.

Genera un borrador de respuesta técnica formal que responda punto por punto a la objeción.
No inventes numerales de ISO 9001, RNE o especificaciones técnicas. Si no se proporcionó la fuente,
indica que el criterio debe ser validado con la E.T., plano, ficha técnica o norma aplicable.
Propón una alternativa técnica que pueda ser revisada por Supervisión.
"""
                                    nuevo_correo = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[{"role": "user", "content": prompt_reiterar}]
                                    ).choices[0].message.content
                                st.session_state[f"refutacion_{ncr_sel}"] = nuevo_correo
                                st.session_state.db_ncrs.at[idx_fila, "version_resolucion"] = safe_float(fila_ncr.get("version_resolucion", 1), 1) + 1
                                row_dict = st.session_state.db_ncrs.loc[idx_fila].to_dict()
                                st.session_state.db_ncrs.at[idx_fila, "historial_json"] = registrar_historial(
                                    row_dict, "Supervisión rechazó propuesta; se generó refutación IA", objecion_inspector
                                )
                                ok, err = save_db()
                                if not ok:
                                    st.error(f"La refutación se generó, pero no pudo guardarse el historial: {err}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo generar la refutación: {e}")

                    elif "RECHAZADO DEFINITIVO" in dictamen_sup:
                        try:
                            with st.spinner("Generando secuencia Lookahead de reconstrucción..."):
                                hoy = datetime.now()
                                f1 = hoy.strftime("%Y-%m-%d")
                                f2 = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
                                f3 = (hoy + timedelta(days=2)).strftime("%Y-%m-%d")
                                f4 = (hoy + timedelta(days=3)).strftime("%Y-%m-%d")

                                prompt_lookahead_real = f"""
La Supervisión rechazó definitivamente la propuesta ligera para {ncr_sel}: '{fila_ncr['descripcion']}'.
Motivo del Inspector: '{objecion_inspector}'.
Especialidad inicialmente involucrada: {fila_ncr['causa_raiz']}.

Como apoyo de planificación VDC, diseña una secuencia constructiva preliminar de retrabajo/reconstrucción.
Identifica contratistas, dependencias y actividades. No inventes requisitos normativos específicos.

Devuelve JSON estricto:
{{
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f1}", "contratista": "{fila_ncr['causa_raiz']}", "actividad": "Desmontaje y retiro del elemento afectado", "horas": 2}},
    {{"paso": 2, "fecha_prog": "{f1}", "contratista": "ENCHAPE/CERÁMICO", "actividad": "Retiro del acabado afectado si corresponde", "horas": 3}},
    {{"paso": 3, "fecha_prog": "{f2}", "contratista": "OBRA CIVIL", "actividad": "Resane y nivelación de base", "horas": 4}},
    {{"paso": 4, "fecha_prog": "{f3}", "contratista": "ENCHAPE/CERÁMICO", "actividad": "Reposición del acabado y tratamiento de juntas", "horas": 4}},
    {{"paso": 5, "fecha_prog": "{f4}", "contratista": "{fila_ncr['causa_raiz']}", "actividad": "Reinstalación y verificación final", "horas": 3}}
  ]
}}
"""
                                res_lk = json.loads(client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    response_format={"type": "json_object"},
                                    messages=[{"role": "user", "content": prompt_lookahead_real}]
                                ).choices[0].message.content)

                                secuencia_nueva = res_lk.get("secuencia_propuesta", [])
                                st.session_state.db_ncrs.at[idx_fila, "tipo_resolucion"] = "Reingreso Interpartidas (Secuencia Lookahead)"
                                st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Abierta (En Reconstrucción Lookahead)"
                                st.session_state.db_ncrs.at[idx_fila, "plan_json"] = json.dumps(secuencia_nueva, ensure_ascii=False)
                                st.session_state.db_ncrs.at[idx_fila, "cumplimiento_json"] = json.dumps(["NO Cumplió"] * len(secuencia_nueva))
                                st.session_state.db_ncrs.at[idx_fila, "observaciones_json"] = json.dumps(["Pendiente de reconstrucción"] * len(secuencia_nueva), ensure_ascii=False)
                                st.session_state.db_ncrs.at[idx_fila, "version_resolucion"] = safe_float(fila_ncr.get("version_resolucion", 1), 1) + 1
                                st.session_state.db_ncrs.at[idx_fila, "fecha_hora_ultima_actualizacion"] = now_str()
                                row_dict = st.session_state.db_ncrs.loc[idx_fila].to_dict()
                                st.session_state.db_ncrs.at[idx_fila, "historial_json"] = registrar_historial(
                                    row_dict, "Reconstrucción Lookahead generada", objecion_inspector
                                )
                                st.session_state.pop(f"refutacion_{ncr_sel}", None)
                                ok, err = save_db()
                                if ok:
                                    st.success("NCR reestructurada a una secuencia Lookahead multi-contratista.")
                                    st.rerun()
                                else:
                                    st.error(f"No se pudo guardar la nueva secuencia: {err}")
                        except Exception as e:
                            st.error(f"No se pudo generar la secuencia Lookahead: {e}")

            # ------------------------------------------------------------------
            # BORRADOR DE REFUTACIÓN
            # ------------------------------------------------------------------
            if f"refutacion_{ncr_sel}" in st.session_state:
                st.markdown("---")
                st.info("💡 BORRADOR DE RESPUESTA TÉCNICA")
                st.text_area(
                    "Texto para responder al Inspector:",
                    value=st.session_state[f"refutacion_{ncr_sel}"],
                    height=220
                )

            # ------------------------------------------------------------------
            # CHECKLIST
            # ------------------------------------------------------------------
            plan = parse_json_list(fila_ncr.get("plan_json", "[]"), [])
            estado_pasos = parse_json_list(fila_ncr.get("cumplimiento_json", "[]"), [])
            obs_pasos = parse_json_list(fila_ncr.get("observaciones_json", "[]"), [])

            if not plan:
                st.warning("Esta NCR no tiene una secuencia registrada.")
            else:
                st.subheader("📋 1. Checklist de ejecución de contratistas")
                nuevos_estados = []
                nuevas_obs = []

                for idx, paso in enumerate(plan):
                    fecha_str = paso.get("fecha_prog", "S/F")
                    col_c1, col_c2, col_c3 = st.columns([2.5, 3, 3])

                    with col_c1:
                        estado_previo = idx < len(estado_pasos) and estado_pasos[idx] == "Cumplió"
                        chk = st.checkbox(
                            f"Paso {paso.get('paso', idx + 1)}: {paso.get('contratista', '')}",
                            value=estado_previo,
                            key=f"chk_{ncr_sel}_{idx}"
                        )
                        nuevos_estados.append("Cumplió" if chk else "NO Cumplió")

                    with col_c2:
                        st.write(f"📅 **{fecha_str}** | **{paso.get('actividad', '')}** ({paso.get('horas', 0)}h)")

                    with col_c3:
                        val_obs = obs_pasos[idx] if idx < len(obs_pasos) else ""
                        txt_obs = st.text_input(
                            f"Observación paso {paso.get('paso', idx + 1)}",
                            value=val_obs,
                            key=f"txt_{ncr_sel}_{idx}"
                        )
                        nuevas_obs.append(txt_obs)

                st.markdown("---")
                if st.button("🔄 Guardar avance de ejecución"):
                    st.session_state.db_ncrs.at[idx_fila, "cumplimiento_json"] = json.dumps(nuevos_estados, ensure_ascii=False)
                    st.session_state.db_ncrs.at[idx_fila, "observaciones_json"] = json.dumps(nuevas_obs, ensure_ascii=False)
                    st.session_state.db_ncrs.at[idx_fila, "fecha_hora_ultima_actualizacion"] = now_str()
                    row_dict = st.session_state.db_ncrs.loc[idx_fila].to_dict()
                    st.session_state.db_ncrs.at[idx_fila, "historial_json"] = registrar_historial(
                        row_dict, "Avance de ejecución actualizado", "Checklist guardado"
                    )
                    ok, err = save_db()
                    if ok:
                        st.success("Avances actualizados correctamente.")
                        st.rerun()
                    else:
                        st.error(f"No se pudieron guardar los avances: {err}")

                todos_ejecutados = len(nuevos_estados) > 0 and all(e == "Cumplió" for e in nuevos_estados)

                # ------------------------------------------------------------------
                # INSPECCIÓN Y CIERRE
                # ------------------------------------------------------------------
                if todos_ejecutados:
                    st.subheader("🕵️‍♂️ 2. Inspección y liberación por Supervisión")
                    st.info("Todos los trabajos figuran como ejecutados. Registra el dictamen de calidad para cerrar la NCR.")

                    col_sup1, col_sup2 = st.columns(2)
                    supervisor = col_sup1.text_input("👤 Inspector / Supervisor de Calidad", value=fila_ncr.get("supervisor", ""))
                    dictamen = col_sup2.radio(
                        "📌 Dictamen final de campo:",
                        ["APROBADO (Aplica Cierre)", "RECHAZADO / CON OBSERVACIONES"]
                    )
                    obs_supervision = st.text_area(
                        "💬 Comentarios de la inspección",
                        placeholder="Ejemplo: Trabajos verificados en sitio y conformes para liberación RI/RF."
                    )

                    if st.button("🔒 Confirmar inspección y registrar cierre"):
                        st.session_state.db_ncrs.at[idx_fila, "supervisor"] = supervisor
                        st.session_state.db_ncrs.at[idx_fila, "dictamen_supervision"] = dictamen
                        st.session_state.db_ncrs.at[idx_fila, "fecha_hora_ultima_actualizacion"] = now_str()

                        if dictamen == "APROBADO (Aplica Cierre)":
                            if not supervisor.strip():
                                st.warning("Ingrese el nombre del supervisor antes de cerrar la NCR.")
                            else:
                                try:
                                    with st.spinner("Generando borrador de Acta de Cierre Técnico..."):
                                        resp_cierre = generar_cierre_gpt(
                                            ncr_sel, fila_ncr["descripcion"], supervisor, obs_supervision
                                        )

                                    fecha_cierre = now_str()
                                    fecha_inicio = pd.to_datetime(
                                        st.session_state.db_ncrs.at[idx_fila, "fecha_hora_registro"], errors="coerce"
                                    )
                                    fecha_fin = pd.to_datetime(fecha_cierre, errors="coerce")
                                    dias = None
                                    if pd.notna(fecha_inicio) and pd.notna(fecha_fin):
                                        dias = round((fecha_fin - fecha_inicio).total_seconds() / 86400, 4)

                                    plazo = safe_float(st.session_state.db_ncrs.at[idx_fila, "plazo_objetivo_dias"], 0)
                                    oportuna = "SÍ" if dias is not None and plazo > 0 and dias <= plazo else "NO"

                                    st.session_state.db_ncrs.at[idx_fila, "estado_ncr"] = "Levantada"
                                    st.session_state.db_ncrs.at[idx_fila, "fecha_hora_levantamiento"] = fecha_cierre
                                    st.session_state.db_ncrs.at[idx_fila, "tiempo_levantamiento_dias"] = dias if dias is not None else ""
                                    st.session_state.db_ncrs.at[idx_fila, "levantada_oportunamente"] = oportuna
                                    st.session_state.db_ncrs.at[idx_fila, "acta_cierre"] = (
                                        f"Borrador de Acta de Cierre Técnico\n"
                                        f"NCR: {ncr_sel}\n"
                                        f"Aprobado por: {supervisor}\n"
                                        f"Fecha/hora de liberación: {fecha_cierre}\n"
                                        f"Tiempo de levantamiento: {dias if dias is not None else 'N/D'} días\n\n"
                                        f"{resp_cierre}"
                                    )
                                    row_dict = st.session_state.db_ncrs.loc[idx_fila].to_dict()
                                    st.session_state.db_ncrs.at[idx_fila, "historial_json"] = registrar_historial(
                                        row_dict, "NCR levantada", f"Aprobada por {supervisor}. {obs_supervision}"
                                    )
                                    ok, err = save_db()
                                    if ok:
                                        st.success(f"{ncr_sel} fue liberada y cerrada. El tiempo de levantamiento quedó registrado para los indicadores.")
                                        st.rerun()
                                    else:
                                        st.error(f"El cierre se generó en la sesión, pero no pudo guardarse en Google Sheets: {err}")
                                except Exception as e:
                                    st.error(f"No se pudo generar el cierre: {e}")
                        else:
                            st.session_state.db_ncrs.at[idx_fila, "objecion_supervision"] = obs_supervision
                            row_dict = st.session_state.db_ncrs.loc[idx_fila].to_dict()
                            st.session_state.db_ncrs.at[idx_fila, "historial_json"] = registrar_historial(
                                row_dict, "Inspección rechazada", obs_supervision
                            )
                            ok, err = save_db()
                            if ok:
                                st.warning("La NCR no fue aprobada. Se registró la observación para una nueva corrección.")
                                st.rerun()
                            else:
                                st.error(f"No se pudo guardar el rechazo: {err}")

