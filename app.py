import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración de página
st.set_page_config(page_title="Gestión UT - Sistema ITA", layout="wide")

# Estilo CSS para visibilidad y estética
st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #1e2129;
        border: 1px solid #3d4450;
        padding: 15px;
        border-radius: 10px;
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; }
    .stTabs [aria-selected="true"] { background-color: #007bff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Sistema ITA - Asignación Final")
st.subheader("Zonificación por Barrios y Control PH")

# Lista fija de supervisores
SUPERVISORES_NOMINA = [
    "FAVIO ERNESTO VASQUEZ ROMERO",
    "DEGUIN ZOCRATE DEGUIN ZOCRATE",
    "YESID RAFAEL REALES MORENO",
    "ABILIO SEGUNDO ARAUJO ARIÑO",
    "JAVIER DAVID GOMEZ BARRIOS"
]

archivo = st.file_uploader("📂 Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    col_barrio = "BARRIO" if "BARRIO" in df.columns else "NOMBRE_BARRIO"
    
    # Limpieza de Deuda
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # SIDEBAR: PANELES DE FILTROS
    # ================================
    st.sidebar.header("🎯 Panel de Filtros")
    
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos_disponibles = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    with st.sidebar.expander("📍 Segmentación Global", expanded=True):
        rangos_sel = st.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
        sub_sel = st.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
        deuda_minima = st.sidebar.number_input("Deuda mínima ($)", min_value=0, value=100000)

    with st.sidebar.expander("👨‍💼 Supervisores"):
        sups_final = st.multiselect("Incluir Supervisores", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    with st.sidebar.expander("👥 Filtro de Operarios"):
        modo_exc = st.checkbox("Modo Exclusión")
        tecs_sel = st.multiselect("Seleccionar Técnicos", tecnicos_disponibles, 
                                  default=tecnicos_disponibles if not modo_exc else [])
        tecs_final = [t for t in tecnicos_disponibles if t not in tecs_sel] if modo_exc else tecs_sel

    # ================================
    # LÓGICA DE ASIGNACIÓN
    # ================================
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by=["_deuda_num"], ascending=False).copy()

    # 1. Supervisores (Bloquean Barrios)
    df_supervisores = df_base.head(len(sups_final) * 8).copy()
    barrios_prohibidos = set()
    if not df_supervisores.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = nombres_sups[:len(df_supervisores)]
        barrios_prohibidos = set(df_supervisores[col_barrio].unique())

    # 2. Operarios (Exclusión y PH)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    df_disponible = df_restante[~df_restante[col_barrio].isin(barrios_prohibidos)]
    
    tecs_ph = [t for t in tecs_final if "PH" in str(t).upper()]
    tecs_std = [t for t in tecs_final if "PH" not in str(t).upper()]

    asignaciones_tecnicos = []
    conteo_asignacion = {t: 0 for t in tecs_final}
    
    for _, row in df_disponible.iterrows():
        es_ph = "PH" in str(row["TECNICOS_INTEGRALES"]).upper()
        candidatos = tecs_ph if es_ph else tecs_std
        validos = [t for t in candidatos if conteo_asignacion[t] < 50 and t != row["TECNICOS_INTEGRALES"]]
        
        if validos:
            elegido = min(validos, key=lambda x: conteo_asignacion[x])
            nueva_fila = row.copy()
            nueva_fila["ASIGNADO_A"] = elegido
            asignaciones_tecnicos.append(nueva_fila)
            conteo_asignacion[elegido] += 1

    df_tecnicos = pd.DataFrame(asignaciones_tecnicos)

    # ================================
    # DASHBOARD
    # ================================
    tab_res, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    with tab_res:
        df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Pólizas", f"{len(df_final):,}")
        c2.metric("Deuda", f"$ {df_final['_deuda_num'].sum():,.0f}")
        c3.metric("Seguridad", "Activa ✅")
        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)

    with tab_sup:
        if not df_supervisores.empty:
            st.subheader("Ranking y Análisis de Supervisores")
            
            # 1. Ranking de mayor a menor deuda
            ranking_sup = df_supervisores.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).reset_index()
            ranking_sup.columns = ["Supervisor", "Deuda Total"]
            st.write("🏆 **Ranking por Deuda Gestionada**")
            st.dataframe(ranking_sup.style.format({"Deuda Total": "$ {:,.0f}"}), use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.info("📊 Pólizas por Rango de Edad")
                fig_s1 = px.bar(df_supervisores["RANGO_EDAD"].astype(str).value_counts().reset_index(), x="RANGO_EDAD", y="count", text_auto=True)
                st.plotly_chart(fig_s1, use_container_width=True)
            with col2:
                st.info("🥧 Composición por Subcategoría")
                fig_s2 = px.pie(df_supervisores, names="SUBCATEGORIA", values="_deuda_num", hole=0.4)
                st.plotly_chart(fig_s2, use_container_width=True)

    with tab_tec:
        if not df_tecnicos.empty:
            st.subheader("Análisis de Operarios")
            
            # 1. Top 10 Operarios con mayor deuda
            top10_tec = df_tecnicos.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
            top10_tec.columns = ["Operario", "Deuda"]
            st.write("🏆 **Top 10 Operarios con Mayor Deuda**")
            st.dataframe(top10_tec.style.format({"Deuda": "$ {:,.0f}"}), use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                st.info("📊 Cantidad de Póliza por Rango de Edad")
                fig_t1 = px.bar(df_tecnicos["RANGO_EDAD"].astype(str).value_counts().reset_index(), x="RANGO_EDAD", y="count", text_auto=True, color_discrete_sequence=['#28a745'])
                st.plotly_chart(fig_t1, use_container_width=True)
            with col4:
                st.info("🥧 Composición por Subcategoría")
                fig_t2 = px.pie(df_tecnicos, names="SUBCATEGORIA", values="_deuda_num", hole=0.4)
                st.plotly_chart(fig_t2, use_container_width=True)

else:
    st.info("👋 Sube el archivo Excel para generar el plan de trabajo.")
