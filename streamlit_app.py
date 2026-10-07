import streamlit as st
import openai
from datetime import datetime, timedelta
import pandas as pd
import json
import re
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
st.set_page_config(
    page_title="ChatBot VDC - Gestión Inteligente de NCRs",
    page_icon="🧠",
    layout="wide"
)

client = openai.OpenAI(api_key=st.secrets["openai_api_key"])
conn = st.connection("gsheets", type=GSheetsConnection)

CONTRATISTAS_LISTA = [
    "OBRA CIVIL", "PINTURA", "PAPEL TAPIZ", "MELAMINE",
    "LAMINADO/PARQUET", "ENCHAPE/CERÁMICO", "PUERTAS Y VENTANAS",
    "MAMPARAS/CRISTALERÍA", "II.SS (SANITARIAS)", "II.EE (ELÉCTRICAS)",
    "II.GG (GAS)", "ALBAÑILERÍA", "GRANITO/MÁRMOL", "DACI/AACI",
    "TODISTA / CUADRILLA INTERNA"
]

COLUMNAS_DB = [
    "ncr", "proyecto", "fecha", "fecha_analisis", "fecha_aprobacion",
    "fecha_ejecucion", "fecha_inspeccion", "fecha_cierre",
    "descripcion", "causa_raiz", "empresa", "tipo_resolucion",
    "estrategia_ia", "estado_ncr", "plan_json", "cumplimiento_json",
    "observaciones_json", "acta_cierre", "analisis_ia_json",
    "num_iteraciones_ia", "num_rechazos", "especialidades_involucradas"
]


def df_vacio():
    return pd.DataFrame(columns=COLUMNAS_DB)


def normalizar_df(df):
    """Asegura que la base tenga todas las columnas nuevas sin romper datos antiguos."""
    if df is None or df.empty:
        return df_vacio()

    df = df.copy()

    # Compatibilidad con la estructura anterior
    if "fecha" not in df.columns:
        df["fecha"] = datetime.now().strftime("%Y-%m-%d")

    for col in COLUMNAS_DB:
        if col not in df.columns:
            if col in [
                "num_iteraciones_ia", "num_rechazos"
            ]:
                df[col] = 0
            elif col in ["fecha_analisis", "fecha_aprobacion",
                         "fecha_ejecucion", "fecha_inspeccion",
                         "fecha_cierre"]:
                df[col] = ""
            else:
                df[col] = ""

    return df[COLUMNAS_DB]


# ==============================================================================
# CARGA DE BASE DE DATOS
# ==============================================================================
if "db_ncrs" not in st.session_state:
    try:
        df_drive = conn.read(ttl=0)
        if not df_drive.empty and "ncr" in df_drive.columns:
            st.session_state.db_ncrs = normalizar_df(df_drive)
        else:
            st.session_state.db_ncrs = df_vacio()
    except Exception:
        st.session_state.db_ncrs = df_vacio()


def guardar_bd():
    """Guarda la base completa en Google Sheets."""
    try:
        st.session_state.db_ncrs = normalizar_df(st.session_state.db_ncrs)
        conn.update(data=st.session_state.db_ncrs)
        return True
    except Exception as e:
        st.error(f"No se pudo actualizar Google Sheets: {e}")
        return False


# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================
def hoy_str():
    return datetime.now().strftime("%Y-%m-%d")


def agregar_dias(fecha_str, dias):
    try:
        f = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d")
    except Exception:
        f = datetime.now()
    return (f + timedelta(days=dias)).strftime("%Y-%m-%d")


def extraer_json(texto):
    """Intenta recuperar JSON incluso si el modelo devuelve bloques de código."""
    texto = texto.strip()
    texto = re.sub(r"^```json\s*", "", texto, flags=re.I)
    texto = re.sub(r"^```\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)
    try:
        return json.loads(texto)
    except Exception:
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio >= 0 and fin > inicio:
            return json.loads(texto[inicio:fin + 1])
        raise


def lista_especialidades(texto):
    encontradas = []
    texto = str(texto).upper()
    for c in CONTRATISTAS_LISTA:
        if c.upper() in texto:
            encontradas.append(c)
    return list(dict.fromkeys(encontradas))


def calcular_dias(fecha_inicio, fecha_fin):
    try:
        a = datetime.strptime(str(fecha_inicio)[:10], "%Y-%m-%d")
        b = datetime.strptime(str(fecha_fin)[:10], "%Y-%m-%d")
        return max((b - a).days, 0)
    except Exception:
        return None


# ==============================================================================
# IA: ANÁLISIS INICIAL DE NCR
# ==============================================================================
def analizar_ncr_ia(
    ncr_num,
    descripcion,
    contratista_causa,
    empresa,
    fecha_inicio,
    estrategia_usuario,
    contexto=""
):
    f1 = str(fecha_inicio)
    f2 = agregar_dias(f1, 1)
    f3 = agregar_dias(f1, 2)
    f4 = agregar_dias(f1, 3)

    prompt = f"""
Actúa como asistente técnico VDC para la gestión de No Conformidades (NCR)
en un proyecto multifamiliar, especialmente acabados secos y húmedos.

IMPORTANTE:
- No debes reemplazar al ingeniero ni a la Supervisión.
- No inventes normas, tolerancias ni datos que no hayan sido proporcionados.
- Si falta información técnica, indícala expresamente.
- La IA debe comparar alternativas antes de recomendar.
- La estrategia recomendada debe poder ser modificada por el usuario.
- La solución directa NO debe asumirse automáticamente.
- El reingreso interpartidas debe incluir únicamente especialidades realmente
  necesarias según el problema.
- La propuesta final siempre requiere validación humana.

DATOS:
NCR: {ncr_num}
Descripción: {descripcion}
Especialidad inicialmente indicada: {contratista_causa}
Empresa: {empresa}
Fecha de registro: {f1}
Estrategia indicada por usuario: {estrategia_usuario}
Contexto adicional: {contexto}

Analiza:
1. Problema identificado.
2. Causa raíz probable.
3. Especialidades involucradas.
4. Información técnica faltante.
5. Alternativas posibles.
6. Riesgos de cada alternativa.
7. Recomendación de estrategia.
8. Justificación.
9. Secuencia Lookahead si la recomendación es reingreso.
10. Propuesta directa si resulta viable.

Devuelve JSON ESTRICTO:
{{
  "problema_identificado": "...",
  "causa_raiz_analisis": "...",
  "especialidades_involucradas": ["..."],
  "informacion_requerida": ["..."],
  "alternativas": [
    {{
      "nombre": "...",
      "tiempo_estimado_horas": 0,
      "riesgo": "...",
      "impacto_ri_rf": "...",
      "observacion": "..."
    }}
  ],
  "estrategia_recomendada": "Reingreso Interpartidas (Secuencia Lookahead) o Solución Directa Todista / Criterio de Supervisión",
  "nivel_confianza": "Bajo/Medio/Alto",
  "justificacion_recomendacion": "...",
  "justificacion_no_retrabajo": "...",
  "propuesta_mitigacion": "...",
  "correo_supervision": "...",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f1}", "contratista": "...", "actividad": "...", "horas": 2}},
    {{"paso": 2, "fecha_prog": "{f2}", "contratista": "...", "actividad": "...", "horas": 4}}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Responde únicamente con JSON válido. Eres un asistente técnico y no sustituyes la aprobación del ingeniero o supervisor."
            },
            {"role": "user", "content": prompt}
        ]
    )

    return extraer_json(response.choices[0].message.content)


# ==============================================================================
# IA: ANÁLISIS DE OBJECIÓN DE SUPERVISIÓN
# ==============================================================================
def analizar_objecion_ia(descripcion, propuesta, objecion, especialidad):
    prompt = f"""
Analiza una objeción de Supervisión respecto de una propuesta de solución
para una No Conformidad.

NCR:
{descripcion}

Propuesta inicial:
{propuesta}

Especialidad:
{especialidad}

Objeción de Supervisión:
{objecion}

No debes "ganarle" al inspector ni inventar fundamentos.
Determina:
- qué está objetando realmente;
- si la objeción parece afectar la causa raíz;
- qué información técnica falta;
- si es razonable modificar la propuesta;
- una nueva alternativa, si existe;
- o si corresponde pasar a reconstrucción/reingreso.

Devuelve JSON:
{{
  "interpretacion_objecion": "...",
  "fundamento_tecnico": "...",
  "informacion_faltante": ["..."],
  "puede_modificarse": true,
  "nueva_propuesta": "...",
  "correo_supervision": "...",
  "recomendacion_final": "Modificar propuesta / Pasar a reconstrucción",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{hoy_str()}", "contratista": "...", "actividad": "...", "horas": 2}}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Responde únicamente con JSON válido. Mantén una postura técnica neutral."
            },
            {"role": "user", "content": prompt}
        ]
    )
    return extraer_json(response.choices[0].message.content)


# ==============================================================================
# IA: RECONSTRUCCIÓN LOOKAHEAD
# ==============================================================================
def generar_lookahead_reconstruccion(descripcion, objecion, especialidad, fecha_base):
    f1 = str(fecha_base)
    f2 = agregar_dias(f1, 1)
    f3 = agregar_dias(f1, 2)
    f4 = agregar_dias(f1, 3)

    prompt = f"""
La Supervisión rechazó definitivamente una solución directa de una NCR.

NCR:
{descripcion}

Motivo del rechazo:
{objecion}

Especialidad raíz:
{especialidad}

Genera una secuencia constructiva de reconstrucción/reingreso realista.
No agregues especialidades innecesarias. Considera dependencias entre partidas,
liberación de cada actividad y posterior inspección.

Devuelve JSON:
{{
  "justificacion_reconstruccion": "...",
  "secuencia_propuesta": [
    {{"paso": 1, "fecha_prog": "{f1}", "contratista": "...", "actividad": "...", "horas": 2}},
    {{"paso": 2, "fecha_prog": "{f2}", "contratista": "...", "actividad": "...", "horas": 4}},
    {{"paso": 3, "fecha_prog": "{f3}", "contratista": "...", "actividad": "...", "horas": 4}},
    {{"paso": 4, "fecha_prog": "{f4}", "contratista": "...", "actividad": "...", "horas": 2}}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Responde únicamente con JSON válido."
            },
            {"role": "user", "content": prompt}
        ]
    )
    return extraer_json(response.choices[0].message.content)


# ==============================================================================
# IA: ANÁLISIS HISTÓRICO DEL DASHBOARD
# ==============================================================================
def analisis_historico_ia(df):
    if df.empty:
        return "No existen suficientes NCR registradas para realizar un análisis histórico."

    registros = []
    for _, r in df.iterrows():
        registros.append({
            "ncr": str(r.get("ncr", "")),
            "estrategia": str(r.get("tipo_resolucion", "")),
            "estrategia_ia": str(r.get("estrategia_ia", "")),
            "estado": str(r.get("estado_ncr", "")),
            "causa": str(r.get("causa_raiz", "")),
            "especialidades": str(r.get("especialidades_involucradas", "")),
            "iteraciones": r.get("num_iteraciones_ia", 0),
            "rechazos": r.get("num_rechazos", 0),
            "fecha": str(r.get("fecha", "")),
            "fecha_cierre": str(r.get("fecha_cierre", ""))
        })

    prompt = f"""
Analiza el siguiente histórico de No Conformidades de un proyecto multifamiliar.

DATOS:
{json.dumps(registros, ensure_ascii=False)}

Entrega un análisis ejecutivo breve:
1. Patrones relevantes.
2. Posibles fuentes de demora.
3. Diferencias entre Solución Directa y Reingreso Interpartidas.
4. Papel de Supervisión/rechazos.
5. Recomendaciones para priorizar ICE/Lookahead.
6. No inventes valores que no estén en los datos.

Aclara que las recomendaciones son apoyo a la decisión y no sustituyen al equipo técnico.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Analiza datos de gestión de NCR de forma técnica, objetiva y prudente."
            },
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


# ==============================================================================
# TÍTULO Y NAVEGACIÓN
# ==============================================================================
st.title("🧠 ChatBot VDC - Gestión Inteligente de No Conformidades")

formato = st.radio(
    "📌 Selecciona el proceso:",
    [
        "Formato 1: Registro e ICE (Oficina)",
        "Formato 2: Monitoreo en Campo (Tiempo Real)",
        "Formato 3: Dashboard e Indicadores"
    ],
    horizontal=True
)


# ==============================================================================
# FORMATO 1
# ==============================================================================
if formato == "Formato 1: Registro e ICE (Oficina)":

    st.header("📋 Formato 1: Registro de NCR + Análisis IA + Planificación")

    with st.form("form_ncr"):
        col1, col2, col3 = st.columns([1, 2, 1])

        ncr_num = col1.text_input(
            "🔢 N° de NCR / Observación",
            placeholder="Ej: NCR-001"
        )
        proyecto = col2.text_input(
            "🏗️ Proyecto",
            placeholder="Ej: Alto Bellavista II"
        )
        fecha_reg = col3.date_input("📅 Fecha de Registro", datetime.now())

        descripcion = st.text_area(
            "⚠️ Ubicación y descripción de la falla / observación RI-RF",
            placeholder="Ingrese piso, ambiente, eje y detalle técnico..."
        )

        col_a, col_b = st.columns(2)
        contratista_causa = col_a.selectbox(
            "👷 Especialidad inicialmente involucrada",
            CONTRATISTAS_LISTA
        )
        subcontratista = col_b.text_input(
            "🏢 Empresa / Cuadrilla",
            placeholder="Nombre de empresa"
        )

        estrategia_usuario = st.radio(
            "🧠 Estrategia inicial:",
            [
                "Permitir que IA recomiende",
                "Reingreso Interpartidas (Secuencia Lookahead)",
                "Solución Directa Todista / Criterio de Supervisión"
            ]
        )

        contexto = st.text_area(
            "💬 Contexto adicional (opcional)",
            placeholder="Ej: Se busca evitar desmontar un acabado ya liberado..."
        )

        btn_analizar = st.form_submit_button(
            "🔍 Analizar NCR con IA",
            use_container_width=True
        )

    if btn_analizar and descripcion and ncr_num:
        with st.spinner("🧠 La IA está analizando problema, causa, alternativas y estrategia..."):
            try:
                res_json = analizar_ncr_ia(
                    ncr_num,
                    descripcion,
                    contratista_causa,
                    subcontratista,
                    str(fecha_reg),
                    estrategia_usuario,
                    contexto
                )

                estrategia_ia = res_json.get(
                    "estrategia_recomendada",
                    "Reingreso Interpartidas (Secuencia Lookahead)"
                )

                st.session_state.temp_ncr = {
                    "num": ncr_num,
                    "proyecto": proyecto,
                    "fecha": str(fecha_reg),
                    "descripcion": descripcion,
                    "causa": contratista_causa,
                    "empresa": subcontratista,
                    "estrategia_usuario": estrategia_usuario,
                    "estrategia_ia": estrategia_ia,
                    "analisis_json": res_json,
                    "tipo_res": estrategia_ia,
                    "analisis": res_json.get("causa_raiz_analisis", ""),
                    "justificacion": res_json.get("justificacion_no_retrabajo", ""),
                    "propuesta": res_json.get("propuesta_mitigacion", ""),
                    "correo": res_json.get("correo_supervision", ""),
                    "secuencia": res_json.get("secuencia_propuesta", [])
                }
            except Exception as e:
                st.error(f"No se pudo procesar la NCR: {e}")

    elif btn_analizar:
        st.warning("Ingrese el N° de NCR y la descripción antes de analizar.")

    if "temp_ncr" in st.session_state:
        data = st.session_state.temp_ncr
        ai = data["analisis_json"]

        st.markdown("---")
        st.subheader("🧠 Análisis inteligente de la NCR")

        c1, c2 = st.columns(2)

        with c1:
            st.info(f"**Problema identificado:** {ai.get('problema_identificado', '')}")
            st.warning(f"**Causa raíz probable:** {ai.get('causa_raiz_analisis', '')}")

        with c2:
            st.success(
                f"**Estrategia recomendada:** {ai.get('estrategia_recomendada', '')}"
            )
            st.caption(
                f"Nivel de confianza de la recomendación: "
                f"{ai.get('nivel_confianza', 'No indicado')}"
            )

        st.subheader("🔎 Información técnica requerida")
        faltantes = ai.get("informacion_requerida", [])
        if faltantes:
            for item in faltantes:
                st.write(f"• {item}")
        else:
            st.write("No se identificó información adicional.")

        st.subheader("⚖️ Comparación de alternativas")
        alternativas = ai.get("alternativas", [])
        if alternativas:
            df_alt = pd.DataFrame(alternativas)
            st.dataframe(df_alt, use_container_width=True, hide_index=True)

        st.subheader("💡 Justificación de la recomendación")
        st.write(ai.get("justificacion_recomendacion", ""))

        tipo_final = st.radio(
            "✋ Decisión del usuario sobre la estrategia:",
            [
                "Usar recomendación IA",
                "Reingreso Interpartidas (Secuencia Lookahead)",
                "Solución Directa Todista / Criterio de Supervisión"
            ],
            key="estrategia_final_form1"
        )

        if tipo_final == "Usar recomendación IA":
            tipo_final = ai.get(
                "estrategia_recomendada",
                "Reingreso Interpartidas (Secuencia Lookahead)"
            )

        st.session_state.temp_ncr["tipo_res"] = tipo_final

        # ----------------------------------------------------------------------
        # SOLUCIÓN DIRECTA
        # ----------------------------------------------------------------------
        if tipo_final == "Solución Directa Todista / Criterio de Supervisión":
            st.subheader("🛡 Propuesta de solución directa")

            propuesta_edit = st.text_area(
                "Puedes ajustar la propuesta antes de enviarla a Supervisión:",
                value=data["propuesta"],
                height=120,
                key="propuesta_directa"
            )
            st.session_state.temp_ncr["propuesta"] = propuesta_edit

            correo_edit = st.text_area(
                "✉️ Borrador para validación de Supervisión:",
                value=data["correo"],
                height=180,
                key="correo_directo"
            )
            st.session_state.temp_ncr["correo"] = correo_edit

            st.warning(
                "La solución directa no queda aprobada automáticamente. "
                "Debe pasar por validación de Supervisión."
            )

            secuencia = data["secuencia"]

        # ----------------------------------------------------------------------
        # LOOKAHEAD
        # ----------------------------------------------------------------------
        else:
            st.subheader("🔄 Secuencia Lookahead propuesta por IA")
            st.caption(
                "La secuencia es una propuesta inicial. Puede ser ajustada "
                "por el equipo durante ICE."
            )
            secuencia = data["secuencia"]

        if not secuencia:
            secuencia = [{
                "paso": 1,
                "fecha_prog": str(fecha_reg),
                "contratista": contratista_causa,
                "actividad": "Definir actividad de subsanación",
                "horas": 2
            }]

        df_secuencia = pd.DataFrame(secuencia)

        if "fecha_prog" in df_secuencia.columns:
            df_secuencia["fecha_prog"] = pd.to_datetime(
                df_secuencia["fecha_prog"],
                errors="coerce"
            ).dt.date

        st.subheader("⏳ Matriz de Subsanación / Lookahead")

        df_edit = st.data_editor(
            df_secuencia,
            num_rows="dynamic",
            column_config={
                "paso": st.column_config.NumberColumn(
                    "Paso", min_value=1, step=1
                ),
                "fecha_prog": st.column_config.DateColumn(
                    "📅 Fecha Programada",
                    format="YYYY-MM-DD",
                    required=True
                ),
                "contratista": st.column_config.SelectboxColumn(
                    "Contratista",
                    options=CONTRATISTAS_LISTA,
                    required=True
                ),
                "actividad": st.column_config.TextColumn(
                    "Actividad",
                    width="large",
                    required=True
                ),
                "horas": st.column_config.NumberColumn(
                    "⏱️ Horas",
                    min_value=1,
                    max_value=48,
                    required=True
                )
            },
            hide_index=True,
            use_container_width=True
        )

        st.info(
            "📌 La matriz puede ser modificada por el usuario/ICE antes de guardarse."
        )

        if st.button(
            "💾 Guardar NCR en Google Sheets",
            use_container_width=True
        ):
            df_guardar = df_edit.copy()
            if "fecha_prog" in df_guardar.columns:
                df_guardar["fecha_prog"] = df_guardar["fecha_prog"].astype(str)

            tipo_res = data["tipo_res"]

            if tipo_res == "Solución Directa Todista / Criterio de Supervisión":
                estado_ini = "Pendiente Validación Supervisión"
            else:
                estado_ini = "Abierta"

            especialidades = lista_especialidades(
                " ".join(
                    [str(x.get("contratista", "")) for x in data["secuencia"]]
                )
                + " "
                + str(data["descripcion"])
            )

            if contratista_causa not in especialidades:
                especialidades.insert(0, contratista_causa)

            nueva_fila = pd.DataFrame([{
                "ncr": data["num"],
                "proyecto": data["proyecto"],
                "fecha": data["fecha"],
                "fecha_analisis": hoy_str(),
                "fecha_aprobacion": "",
                "fecha_ejecucion": "",
                "fecha_inspeccion": "",
                "fecha_cierre": "",
                "descripcion": data["descripcion"],
                "causa_raiz": data["causa"],
                "empresa": data["empresa"],
                "tipo_resolucion": tipo_res,
                "estrategia_ia": data["estrategia_ia"],
                "estado_ncr": estado_ini,
                "plan_json": json.dumps(
                    df_guardar.to_dict(orient="records"),
                    ensure_ascii=False
                ),
                "cumplimiento_json": json.dumps(
                    ["NO Cumplió"] * len(df_guardar),
                    ensure_ascii=False
                ),
                "observaciones_json": json.dumps(
                    ["Pendiente de validación/ejecución"] * len(df_guardar),
                    ensure_ascii=False
                ),
                "acta_cierre": "",
                "analisis_ia_json": json.dumps(
                    data["analisis_json"],
                    ensure_ascii=False
                ),
                "num_iteraciones_ia": 1,
                "num_rechazos": 0,
                "especialidades_involucradas": ", ".join(especialidades)
            }])

            # Evita duplicar NCR
            db = st.session_state.db_ncrs
            if not db.empty and str(data["num"]) in db["ncr"].astype(str).tolist():
                st.error("Esta NCR ya existe en la base de datos.")
            else:
                st.session_state.db_ncrs = pd.concat(
                    [db, nueva_fila],
                    ignore_index=True
                )

                if guardar_bd():
                    st.success(
                        f"✅ {data['num']} guardada. "
                        f"Estado inicial: {estado_ini}"
                    )
                    st.session_state.pop("temp_ncr", None)
                    st.rerun()


# ==============================================================================
# FORMATO 2
# ==============================================================================
elif formato == "Formato 2: Monitoreo en Campo (Tiempo Real)":

    st.header("📱 Formato 2: Seguimiento, Supervisión y Liberación")

    df_bd = normalizar_df(st.session_state.db_ncrs)

    if df_bd.empty or df_bd["ncr"].dropna().empty:
        st.warning("No hay No Conformidades registradas.")
    else:
        lista_ncrs = df_bd["ncr"].dropna().astype(str).tolist()
        ncr_sel = st.selectbox("📌 Selecciona la NCR:", lista_ncrs)

        idx_fila = df_bd[df_bd["ncr"].astype(str) == str(ncr_sel)].index[0]
        fila_ncr = df_bd.loc[idx_fila]

        st.markdown(
            f"**Proyecto:** {fila_ncr['proyecto']}  |  "
            f"**Modalidad:** `{fila_ncr['tipo_resolucion']}`  |  "
            f"**Estado:** `{fila_ncr['estado_ncr']}`"
        )

        st.markdown(f"**Ubicación / Falla:** {fila_ncr['descripcion']}")
        st.markdown("---")

        # ----------------------------------------------------------------------
        # NCR CERRADA
        # ----------------------------------------------------------------------
        if fila_ncr["estado_ncr"] == "Levantada":
            st.success(
                f"✅ {ncr_sel} SE ENCUENTRA COMPLETAMENTE LEVANTADA Y LIBERADA."
            )

            st.subheader("📜 Acta de Cierre")
            st.info(fila_ncr["acta_cierre"])

        else:
            # ------------------------------------------------------------------
            # VALIDACIÓN DE SOLUCIÓN DIRECTA
            # ------------------------------------------------------------------
            if fila_ncr["estado_ncr"] == "Pendiente Validación Supervisión":

                st.warning(
                    "⏳ La solución directa propuesta está pendiente de "
                    "validación por Supervisión."
                )

                col_v1, col_v2 = st.columns(2)

                sup_nombre = col_v1.text_input(
                    "👤 Supervisor / Inspector",
                    placeholder="Ej: Ing. Luis Matos",
                    key=f"sup_{ncr_sel}"
                )

                dictamen_sup = col_v2.radio(
                    "📌 Dictamen:",
                    [
                        "✅ APROBADO",
                        "2. RECHAZADO - REVISAR OBJECIÓN",
                        "🚨 RECHAZADO DEFINITIVO - RECONSTRUCCIÓN"
                    ],
                    key=f"dictamen_sup_{ncr_sel}"
                )

                objecion_inspector = ""

                if "RECHAZADO" in dictamen_sup:
                    objecion_inspector = st.text_area(
                        "🗣️ Motivo / objeción de Supervisión:",
                        key=f"objecion_{ncr_sel}",
                        placeholder="Escriba exactamente qué objeta Supervisión."
                    )

                if st.button(
                    "📝 Registrar Dictamen de Supervisión",
                    key=f"registrar_dictamen_{ncr_sel}",
                    use_container_width=True
                ):

                    # ----------------------------------------------------------
                    # APROBADO
                    # ----------------------------------------------------------
                    if dictamen_sup == "✅ APROBADO":

                        st.session_state.db_ncrs.at[
                            idx_fila, "estado_ncr"
                        ] = "Abierta (Aprobada por Supervisión)"

                        st.session_state.db_ncrs.at[
                            idx_fila, "fecha_aprobacion"
                        ] = hoy_str()

                        guardar_bd()
                        st.success(
                            "🎉 Propuesta aprobada. La NCR pasa a ejecución."
                        )
                        st.rerun()

                    # ----------------------------------------------------------
                    # RECHAZO CON POSIBILIDAD DE MODIFICACIÓN
                    # ----------------------------------------------------------
                    elif "REVISAR OBJECIÓN" in dictamen_sup:

                        if not objecion_inspector:
                            st.warning(
                                "Ingrese la objeción del inspector."
                            )
                        else:
                            with st.spinner(
                                "🧠 La IA está interpretando la objeción..."
                            ):
                                try:
                                    propuesta_actual = ""
                                    try:
                                        analisis_guardado = extraer_json(
                                            fila_ncr["analisis_ia_json"]
                                        )
                                        propuesta_actual = analisis_guardado.get(
                                            "propuesta_mitigacion", ""
                                        )
                                    except Exception:
                                        propuesta_actual = ""

                                    resultado_obj = analizar_objecion_ia(
                                        fila_ncr["descripcion"],
                                        propuesta_actual,
                                        objecion_inspector,
                                        fila_ncr["causa_raiz"]
                                    )

                                    st.session_state[
                                        f"objecion_ia_{ncr_sel}"
                                    ] = resultado_obj

                                    st.session_state.db_ncrs.at[
                                        idx_fila, "num_rechazos"
                                    ] = int(
                                        pd.to_numeric(
                                            fila_ncr["num_rechazos"],
                                            errors="coerce"
                                        ) or 0
                                    ) + 1

                                    st.session_state.db_ncrs.at[
                                        idx_fila, "num_iteraciones_ia"
                                    ] = int(
                                        pd.to_numeric(
                                            fila_ncr["num_iteraciones_ia"],
                                            errors="coerce"
                                        ) or 0
                                    ) + 1

                                    guardar_bd()
                                    st.rerun()

                                except Exception as e:
                                    st.error(
                                        f"No se pudo analizar la objeción: {e}"
                                    )

            # Mostrar análisis de objeción
            if f"objecion_ia_{ncr_sel}" in st.session_state:

                resultado_obj = st.session_state[
                    f"objecion_ia_{ncr_sel}"
                ]

                st.markdown("---")
                st.subheader("🧠 Interpretación IA de la objeción")

                st.info(
                    f"**Qué está objetando Supervisión:** "
                    f"{resultado_obj.get('interpretacion_objecion', '')}"
                )

                st.write(
                    f"**Fundamento técnico:** "
                    f"{resultado_obj.get('fundamento_tecnico', '')}"
                )

                faltantes = resultado_obj.get(
                    "informacion_faltante", []
                )

                if faltantes:
                    st.write("**Información faltante:**")
                    for x in faltantes:
                        st.write(f"• {x}")

                st.write(
                    f"**¿Puede modificarse la propuesta?:** "
                    f"{'Sí' if resultado_obj.get('puede_modificarse') else 'No'}"
                )

                st.success(
                    f"**Nueva propuesta:** "
                    f"{resultado_obj.get('nueva_propuesta', '')}"
                )

                st.text_area(
                    "✉️ Borrador para Supervisión:",
                    value=resultado_obj.get("correo_supervision", ""),
                    height=180,
                    key=f"correo_obj_{ncr_sel}"
                )

                if st.button(
                    "🔄 Adoptar nueva propuesta de IA",
                    key=f"adoptar_obj_{ncr_sel}"
                ):
                    if resultado_obj.get("puede_modificarse", False):
                        st.session_state.db_ncrs.at[
                            idx_fila, "plan_json"
                        ] = json.dumps(
                            resultado_obj.get(
                                "secuencia_propuesta", []
                            ),
                            ensure_ascii=False
                        )

                        st.session_state.db_ncrs.at[
                            idx_fila, "estado_ncr"
                        ] = "Pendiente Validación Supervisión"

                        guardar_bd()

                        st.success(
                            "Nueva propuesta registrada. "
                            "Debe volver a ser validada por Supervisión."
                        )
                        st.rerun()

            # ------------------------------------------------------------------
            # RECHAZO DEFINITIVO
            # ------------------------------------------------------------------
            if fila_ncr["estado_ncr"] in [
                "Pendiente Validación Supervisión"
            ]:

                # Solo se ofrece si el usuario lo decide.
                st.markdown("---")
                st.subheader("🚨 Si Supervisión exige reconstrucción")

                obj_def = st.text_area(
                    "Motivo del rechazo definitivo:",
                    placeholder="Indique por qué la solución directa no es aceptable.",
                    key=f"obj_def_{ncr_sel}"
                )

                if st.button(
                    "🧠 Generar Reconstrucción Lookahead",
                    key=f"reconstruccion_{ncr_sel}",
                    use_container_width=True
                ):

                    if not obj_def:
                        st.warning("Ingrese el motivo del rechazo.")
                    else:
                        with st.spinner(
                            "Generando secuencia de reconstrucción..."
                        ):
                            try:
                                resultado_lk = generar_lookahead_reconstruccion(
                                    fila_ncr["descripcion"],
                                    obj_def,
                                    fila_ncr["causa_raiz"],
                                    hoy_str()
                                )

                                secuencia_nueva = resultado_lk.get(
                                    "secuencia_propuesta", []
                                )

                                st.session_state.db_ncrs.at[
                                    idx_fila, "tipo_resolucion"
                                ] = "Reingreso Interpartidas (Secuencia Lookahead)"

                                st.session_state.db_ncrs.at[
                                    idx_fila, "estrategia_ia"
                                ] = "Reconstrucción Lookahead por rechazo definitivo"

                                st.session_state.db_ncrs.at[
                                    idx_fila, "estado_ncr"
                                ] = "Abierta (En Reconstrucción Lookahead)"

                                st.session_state.db_ncrs.at[
                                    idx_fila, "fecha_aprobacion"
                                ] = ""

                                st.session_state.db_ncrs.at[
                                    idx_fila, "plan_json"
                                ] = json.dumps(
                                    secuencia_nueva,
                                    ensure_ascii=False
                                )

                                st.session_state.db_ncrs.at[
                                    idx_fila, "cumplimiento_json"
                                ] = json.dumps(
                                    ["NO Cumplió"] * len(secuencia_nueva)
                                )

                                st.session_state.db_ncrs.at[
                                    idx_fila, "observaciones_json"
                                ] = json.dumps(
                                    ["Pendiente de reconstrucción"]
                                    * len(secuencia_nueva)
                                )

                                st.session_state.db_ncrs.at[
                                    idx_fila, "num_rechazos"
                                ] = int(
                                    pd.to_numeric(
                                        fila_ncr["num_rechazos"],
                                        errors="coerce"
                                    ) or 0
                                ) + 1

                                st.session_state.db_ncrs.at[
                                    idx_fila, "num_iteraciones_ia"
                                ] = int(
                                    pd.to_numeric(
                                        fila_ncr["num_iteraciones_ia"],
                                        errors="coerce"
                                    ) or 0
                                ) + 1

                                guardar_bd()

                                st.success(
                                    "🔄 NCR convertida a reconstrucción Lookahead."
                                )
                                st.rerun()

                            except Exception as e:
                                st.error(
                                    f"No se pudo generar el Lookahead: {e}"
                                )

            # ------------------------------------------------------------------
            # CHECKLIST
            # ------------------------------------------------------------------
            try:
                plan = extraer_json(fila_ncr["plan_json"])
            except Exception:
                plan = []

            if not isinstance(plan, list):
                plan = []

            try:
                estado_pasos = extraer_json(
                    fila_ncr["cumplimiento_json"]
                )
            except Exception:
                estado_pasos = ["NO Cumplió"] * len(plan)

            try:
                obs_pasos = extraer_json(
                    fila_ncr["observaciones_json"]
                )
            except Exception:
                obs_pasos = [""] * len(plan)

            if plan:
                st.subheader("📋 Checklist de ejecución")

                nuevos_estados = []
                nuevas_obs = []

                for idx, p in enumerate(plan):

                    fecha_str = p.get("fecha_prog", "S/F")
                    estado_previo = (
                        idx < len(estado_pasos)
                        and estado_pasos[idx] == "Cumplió"
                    )

                    col_c1, col_c2, col_c3 = st.columns(
                        [2.5, 3.5, 3]
                    )

                    with col_c1:
                        chk = st.checkbox(
                            f"Paso {p.get('paso', idx + 1)}: "
                            f"{p.get('contratista', '')}",
                            value=estado_previo,
                            key=f"chk_{ncr_sel}_{idx}"
                        )
                        nuevos_estados.append(
                            "Cumplió" if chk else "NO Cumplió"
                        )

                    with col_c2:
                        st.write(
                            f"📅 **{fecha_str}**  \n"
                            f"**{p.get('actividad', '')}**  \n"
                            f"⏱️ {p.get('horas', 0)} h"
                        )

                    with col_c3:
                        val_obs = (
                            obs_pasos[idx]
                            if idx < len(obs_pasos)
                            else ""
                        )
                        txt_obs = st.text_input(
                            f"Observación Paso {p.get('paso', idx + 1)}",
                            value=val_obs,
                            key=f"txt_{ncr_sel}_{idx}"
                        )
                        nuevas_obs.append(txt_obs)

                if st.button(
                    "🔄 Guardar avance",
                    key=f"guardar_avance_{ncr_sel}",
                    use_container_width=True
                ):
                    st.session_state.db_ncrs.at[
                        idx_fila, "cumplimiento_json"
                    ] = json.dumps(
                        nuevos_estados,
                        ensure_ascii=False
                    )

                    st.session_state.db_ncrs.at[
                        idx_fila, "observaciones_json"
                    ] = json.dumps(
                        nuevas_obs,
                        ensure_ascii=False
                    )

                    if any(
                        x == "Cumplió" for x in nuevos_estados
                    ):
                        st.session_state.db_ncrs.at[
                            idx_fila, "fecha_ejecucion"
                        ] = hoy_str()

                    guardar_bd()
                    st.success("Avance actualizado.")
                    st.rerun()

                todos_ejecutados = (
                    len(nuevos_estados) > 0
                    and all(
                        e == "Cumplió"
                        for e in nuevos_estados
                    )
                )

                # --------------------------------------------------------------
                # INSPECCIÓN
                # --------------------------------------------------------------
                if todos_ejecutados:

                    st.subheader(
                        "🕵️ Inspección y liberación por Supervisión"
                    )

                    supervisor = st.text_input(
                        "👤 Inspector / Supervisor",
                        placeholder="Ej: Ing. Luis Matos",
                        key=f"inspector_{ncr_sel}"
                    )

                    dictamen = st.radio(
                        "📌 Dictamen final:",
                        [
                            "APROBADO - Cerrar NCR",
                            "RECHAZADO - Requiere corrección"
                        ],
                        key=f"dictamen_final_{ncr_sel}"
                    )

                    obs_supervision = st.text_area(
                        "💬 Observaciones de inspección:",
                        key=f"obs_final_{ncr_sel}"
                    )

                    if st.button(
                        "🔒 Confirmar inspección",
                        key=f"confirmar_inspeccion_{ncr_sel}",
                        use_container_width=True
                    ):

                        st.session_state.db_ncrs.at[
                            idx_fila, "fecha_inspeccion"
                        ] = hoy_str()

                        if dictamen == "APROBADO - Cerrar NCR":

                            prompt_cierre = f"""
La NCR {ncr_sel} fue ejecutada y aprobada por Supervisión.
Descripción: {fila_ncr['descripcion']}
Inspector: {supervisor}
Observaciones: {obs_supervision}

Redacta una conclusión técnica breve de cierre de NCR.
No inventes normas específicas. Indica que la liberación corresponde
al criterio de Supervisión y a la verificación realizada en campo.
"""

                            resp_cierre = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": prompt_cierre
                                    }
                                ]
                            ).choices[0].message.content

                            st.session_state.db_ncrs.at[
                                idx_fila, "estado_ncr"
                            ] = "Levantada"

                            st.session_state.db_ncrs.at[
                                idx_fila, "fecha_cierre"
                            ] = hoy_str()

                            st.session_state.db_ncrs.at[
                                idx_fila, "acta_cierre"
                            ] = (
                                f"Aprobado por {supervisor}. "
                                f"{resp_cierre}"
                            )

                            guardar_bd()

                            st.balloons()
                            st.success(
                                f"🎉 {ncr_sel} levantada y cerrada."
                            )
                            st.rerun()

                        else:
                            st.session_state.db_ncrs.at[
                                idx_fila, "estado_ncr"
                            ] = "Abierta (Corrección posterior a inspección)"

                            st.session_state.db_ncrs.at[
                                idx_fila, "observaciones_json"
                            ] = json.dumps(
                                nuevas_obs + [
                                    f"Rechazado por Supervisión: "
                                    f"{obs_supervision}"
                                ],
                                ensure_ascii=False
                            )

                            guardar_bd()

                            st.warning(
                                "⚠️ La NCR no fue liberada. "
                                "Debe corregirse y volver a inspección."
                            )
                            st.rerun()


# ==============================================================================
# FORMATO 3 - DASHBOARD
# ==============================================================================
elif formato == "Formato 3: Dashboard e Indicadores":

    st.header("📊 Formato 3: Dashboard de Gestión de NCR")

    df = normalizar_df(st.session_state.db_ncrs)

    if df.empty:
        st.warning(
            "No existen NCR registradas todavía. "
            "Registra NCR en el Formato 1."
        )
    else:

        # ----------------------------------------------------------------------
        # CÁLCULO DE INDICADORES
        # ----------------------------------------------------------------------
        df["fecha_dt"] = pd.to_datetime(
            df["fecha"],
            errors="coerce"
        )

        df["cierre_dt"] = pd.to_datetime(
            df["fecha_cierre"],
            errors="coerce"
        )

        df["TNC_dias"] = (
            df["cierre_dt"] - df["fecha_dt"]
        ).dt.days

        # TNC solo de NCR levantadas
        tnc_cerradas = df.loc[
            df["estado_ncr"] == "Levantada",
            "TNC_dias"
        ].dropna()

        tnc_promedio = (
            tnc_cerradas.mean()
            if not tnc_cerradas.empty
            else 0
        )

        ncr_total = len(df)
        ncr_levantadas = int(
            (df["estado_ncr"] == "Levantada").sum()
        )
        ncr_pendientes = ncr_total - ncr_levantadas

        # PNC / PNCO
        # Se calcula aquí como proporción de NCR levantadas y no levantadas.
        # Si tu metodología define PNC/PNCO con otra fórmula, se cambia
        # solamente esta parte.
        PNC = (
            (ncr_levantadas / ncr_total) * 100
            if ncr_total > 0 else 0
        )

        PNCO = 100 - PNC

        rechazos = pd.to_numeric(
            df["num_rechazos"],
            errors="coerce"
        ).fillna(0)

        iteraciones = pd.to_numeric(
            df["num_iteraciones_ia"],
            errors="coerce"
        ).fillna(0)

        # ----------------------------------------------------------------------
        # TARJETAS
        # ----------------------------------------------------------------------
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "⏱️ TNC promedio",
            f"{tnc_promedio:.1f} días"
        )

        c2.metric(
            "📈 PNC",
            f"{PNC:.1f}%"
        )

        c3.metric(
            "📉 PNCO",
            f"{PNCO:.1f}%"
        )

        c4.metric(
            "📋 NCR totales",
            ncr_total
        )

        c5, c6, c7 = st.columns(3)

        c5.metric(
            "✅ NCR levantadas",
            ncr_levantadas
        )

        c6.metric(
            "⏳ NCR pendientes",
            ncr_pendientes
        )

        c7.metric(
            "🚨 Rechazos registrados",
            int(rechazos.sum())
        )

        st.markdown("---")

        # ----------------------------------------------------------------------
        # ESTADO DE NCR
        # ----------------------------------------------------------------------
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("📌 Estado de NCR")
            estado_counts = (
                df["estado_ncr"]
                .value_counts()
                .rename_axis("Estado")
                .reset_index(name="Cantidad")
            )
            st.dataframe(
                estado_counts,
                use_container_width=True,
                hide_index=True
            )

        with col_g2:
            st.subheader("🛠️ Estrategia utilizada")
            estrategia_counts = (
                df["tipo_resolucion"]
                .value_counts()
                .rename_axis("Estrategia")
                .reset_index(name="Cantidad")
            )
            st.dataframe(
                estrategia_counts,
                use_container_width=True,
                hide_index=True
            )

        # ----------------------------------------------------------------------
        # COMPARACIÓN DE ESTRATEGIAS
        # ----------------------------------------------------------------------
        st.subheader("⚖️ Comparación de estrategias")

        comparacion = []

        for estrategia in df["tipo_resolucion"].dropna().unique():

            subset = df[
                df["tipo_resolucion"] == estrategia
            ]

            cerradas = subset[
                subset["estado_ncr"] == "Levantada"
            ]["TNC_dias"].dropna()

            comparacion.append({
                "Estrategia": estrategia,
                "NCR": len(subset),
                "NCR levantadas": int(
                    (subset["estado_ncr"] == "Levantada").sum()
                ),
                "TNC promedio (días)": (
                    round(cerradas.mean(), 2)
                    if not cerradas.empty else None
                ),
                "Rechazos": int(
                    pd.to_numeric(
                        subset["num_rechazos"],
                        errors="coerce"
                    ).fillna(0).sum()
                )
            })

        if comparacion:
            st.dataframe(
                pd.DataFrame(comparacion),
                use_container_width=True,
                hide_index=True
            )

        # ----------------------------------------------------------------------
        # NCR CON MAYOR DEMORA
        # ----------------------------------------------------------------------
        st.subheader("⏱️ NCR con mayor tiempo de levantamiento")

        df_demora = df[
            df["TNC_dias"].notna()
        ].copy()

        if not df_demora.empty:
            df_demora = df_demora.sort_values(
                "TNC_dias",
                ascending=False
            )

            st.dataframe(
                df_demora[
                    [
                        "ncr",
                        "proyecto",
                        "tipo_resolucion",
                        "causa_raiz",
                        "TNC_dias",
                        "num_rechazos"
                    ]
                ].rename(
                    columns={
                        "ncr": "NCR",
                        "proyecto": "Proyecto",
                        "tipo_resolucion": "Estrategia",
                        "causa_raiz": "Especialidad",
                        "TNC_dias": "TNC (días)",
                        "num_rechazos": "Rechazos"
                    }
                ).head(10),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(
                "Todavía no existen NCR cerradas suficientes para calcular TNC."
            )

        # ----------------------------------------------------------------------
        # ESPECIALIDADES
        # ----------------------------------------------------------------------
        st.subheader("👷 Especialidades involucradas")

        especialidades = []

        for texto in df["especialidades_involucradas"].fillna(""):
            for esp in str(texto).split(","):
                esp = esp.strip()
                if esp:
                    especialidades.append(esp)

        if especialidades:
            esp_counts = (
                pd.Series(especialidades)
                .value_counts()
                .rename_axis("Especialidad")
                .reset_index(name="NCR")
            )

            st.dataframe(
                esp_counts,
                use_container_width=True,
                hide_index=True
            )

        # ----------------------------------------------------------------------
        # TRAZABILIDAD DE ETAPAS
        # ----------------------------------------------------------------------
        st.subheader("🕒 Tiempos del proceso")

        def promedio_etapa(columna):
            valores = []

            for _, r in df.iterrows():

                inicio = r["fecha_dt"]

                if pd.isna(inicio):
                    continue

                fin = pd.to_datetime(
                    r[columna],
                    errors="coerce"
                )

                if pd.notna(fin):
                    valores.append(
                        max((fin - inicio).days, 0)
                    )

            return round(
                sum(valores) / len(valores),
                2
            ) if valores else 0

        tiempos = pd.DataFrame({
            "Etapa": [
                "Registro → Aprobación",
                "Registro → Ejecución",
                "Registro → Inspección",
                "Registro → Cierre"
            ],
            "Promedio (días)": [
                promedio_etapa("fecha_aprobacion"),
                promedio_etapa("fecha_ejecucion"),
                promedio_etapa("fecha_inspeccion"),
                promedio_etapa("fecha_cierre")
            ]
        })

        st.dataframe(
            tiempos,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------------------------
        # ANÁLISIS IA DEL HISTÓRICO
        # ----------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🧠 Análisis IA del histórico")

        st.write(
            "La IA interpreta el comportamiento de las NCR registradas. "
            "Los indicadores anteriores son calculados directamente por el sistema."
        )

        if st.button(
            "🔍 Analizar patrones del histórico con IA",
            use_container_width=True
        ):
            with st.spinner(
                "🧠 Analizando patrones, rechazos, estrategias y tiempos..."
            ):
                try:
                    resultado_historico = analisis_historico_ia(df)

                    st.session_state.analisis_historico = resultado_historico

                except Exception as e:
                    st.error(
                        f"No se pudo generar el análisis histórico: {e}"
                    )

        if "analisis_historico" in st.session_state:
            st.info(st.session_state.analisis_historico)

        # ----------------------------------------------------------------------
        # TABLA COMPLETA
        # ----------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📚 Histórico de NCR")

        columnas_mostrar = [
            "ncr",
            "proyecto",
            "fecha",
            "fecha_cierre",
            "tipo_resolucion",
            "estado_ncr",
            "TNC_dias",
            "num_iteraciones_ia",
            "num_rechazos",
            "especialidades_involucradas"
        ]

        st.dataframe(
            df[columnas_mostrar].rename(
                columns={
                    "ncr": "NCR",
                    "proyecto": "Proyecto",
                    "fecha": "Registro",
                    "fecha_cierre": "Cierre",
                    "tipo_resolucion": "Estrategia",
                    "estado_ncr": "Estado",
                    "TNC_dias": "TNC (días)",
                    "num_iteraciones_ia": "Iteraciones IA",
                    "num_rechazos": "Rechazos",
                    "especialidades_involucradas": "Especialidades"
                }
            ),
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "Nota metodológica: PNC y PNCO están configurados aquí como "
            "porcentaje de NCR levantadas y no levantadas. Si en tu tesis "
            "tienes una definición específica de estas fórmulas, debe "
            "reemplazarse en el bloque de cálculo para que coincida exactamente "
            "con tu metodología."
        )
