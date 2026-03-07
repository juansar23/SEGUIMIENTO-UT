import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración de página con tema oscuro para mejor visibilidad
st.set_page_config(page_title="Gestión UT - Sistema ITA", layout="wide")

# Estilo CSS para arreglar la visibilidad de las métricas y botones
st.markdown("""
    <style>
    /* Fondo oscuro para las métricas para que el texto blanco resalte */
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 28px; }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; }
    div[data-testid="stMetric"] {
        background-color: #1e2129;
        border: 1px solid #3d4450;
        padding: 15px;
        border-radius: 10px;
    }
    /* Estilo de pestañas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #262730;
        color: white;
        border-radius: 5px;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Dashboard Ejecutivo - Unidad de Trabajo")

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
    # SIDEBAR: FILTROS (CORRECCIÓN TypeError)
    # ================================
    st.sidebar.header("🎯 Panel de Filtros")
    
    # Se usa .astype(str) para evitar el error de sorted() con nulos
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos_disponibles = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    with st.sidebar.expander("📍 Filtros de Segmentación", expanded=True):
        rangos_sel = st.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
        sub_sel = st.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
        deuda_minima = st.number_input("Deuda mínima ($)", min_value=0, value=100000, step=50000)

    with st.sidebar.expander("👨‍💼 Supervisores"):
        sups_final = st.multiselect("Incluir Supervisores", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    # ================================
    # LÓGICA DE ASIGNACIÓN (SIN CRUCES)
    # ================================
    # Los filtros ahora afectan a TODA la base de datos
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by="_deuda_num", ascending=False).copy()

    # Asignación Supervisores (Prioridad 1)
    df_supervisores = df_base.head(len(sups_final) * 8).copy()
    if not df_supervisores.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = nombres_sups[:len(df_supervisores)]

    # Asignación Operarios (Prioridad 2 - Restante)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    df_tecnicos = df_restante.groupby("TECNICOS_INTEGRALES").head(50).copy()
    df_tecnicos["ASIGNADO_A"] = df_tecnicos["TECNICOS_INTEGRALES"]

    # ================================
    # PESTAÑAS
    # ================================
    tab_resumen, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    with tab_resumen:
        df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)
        col_m1, col_m2, col_m3 = st.columns(3)
        # Métricas ahora visibles con fondo oscuro
        col_m1.metric("Total Pólizas", f"{len(df_final):,}")
        col_m2.metric("Deuda Total", f"$ {df_final['_deuda_num'].sum():,.0f}")
        col_m3.metric("Efectividad", f"{(len(df_final)/len(df)*100):.1f}%")

        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Asignacion")
        st.download_button("📥 Descargar Plan de Trabajo", data=output.getvalue(), file_name="plan_trabajo.xlsx")

    with tab_sup:
        st.subheader("Análisis de Supervisores (Filtrado)")
        if not df_supervisores.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.info("📊 Pólizas por Rango de Edad")
                conteo_e_s = df_supervisores["RANGO_EDAD"].astype(str).value_counts().reset_index()
                st.plotly_chart(px.bar(conteo_e_s, x="RANGO_EDAD", y="count", text_auto=True), use_container_width=True)
            with c2:
                st.info("🥧 Deuda por Subcategoría")
                st.plotly_chart(px.pie(df_supervisores, names="SUBCATEGORIA", values="_deuda_num", hole=0.3), use_container_width=True)
        else:
            st.warning("Sin datos para supervisores.")

    with tab_tec:
        st.subheader("Análisis de Operarios (Filtrado)")
        if not df_tecnicos.empty:
            c3, c4 = st.columns(2)
            with c3:
                st.info("📊 Pólizas por Rango de Edad")
                conteo_e_t = df_tecnicos["RANGO_EDAD"].astype(str).value_counts().reset_index()
                st.plotly_chart(px.bar(conteo_e_t, x="RANGO_EDAD", y="count", text_auto=True), use_container_width=True)
            with c4:
                # Se asegura que el gráfico de torta reciba datos válidos
                st.info("🥧 Composición por Subcategoría")
                conteo_s_t = df_tecnicos["SUBCATEGORIA"].value_counts().reset_index()
                st.plotly_chart(px.pie(conteo_s_t, names="SUBCATEGORIA", values="count", hole=0.3), use_container_width=True)
        else:
            st.warning("Sin datos para operarios.")

else:
    st.info("👋 Sube el archivo para comenzar la asignación.")
