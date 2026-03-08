import streamlit as st
import pandas as pd
import io
import plotly.express as px
import plotly.graph_objects as go

# Configuración de página
st.set_page_config(page_title="Gestión UT - Sistema ITA", layout="wide")

# Estilo para métricas
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
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Dashboard Ejecutivo - Sistema ITA")

# Lista de supervisores
SUPERVISORES_NOMINA = [
    "FAVIO ERNESTO VASQUEZ ROMERO", "DEGUIN ZOCRATE DEGUIN ZOCRATE",
    "YESID RAFAEL REALES MORENO", "ABILIO SEGUNDO ARAUJO ARIÑO",
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
        .str.replace("$", "", regex=False).str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False).str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # FILTROS SIDEBAR
    # ================================
    st.sidebar.header("🎯 Filtros")
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecs_disponibles = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
    sub_sel = st.sidebar.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
    deuda_minima = st.sidebar.number_input("Deuda mínima", value=100000)
    
    sups_final = st.sidebar.multiselect("Supervisores", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)
    tecs_final = st.sidebar.multiselect("Operarios", tecs_disponibles, default=tecs_disponibles)

    # ================================
    # LÓGICA DE ASIGNACIÓN
    # ================================
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by="_deuda_num", ascending=False).copy()

    # 1. Asignación Supervisores
    df_sup = df_base.head(len(sups_final) * 8).copy()
    barrios_bloqueados = set()
    if not df_sup.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_sup["ASIGNADO_A"] = nombres_sups[:len(df_sup)]
        barrios_bloqueados = set(df_sup[col_barrio].unique())

    # 2. Asignación Operarios (Exclusión Barrios y PH)
    df_res = df_base.drop(df_sup.index) if not df_sup.empty else df_base
    df_disp = df_res[~df_res[col_barrio].isin(barrios_bloqueados)]
    
    tecs_ph = [t for t in tecs_final if "PH" in str(t).upper()]
    tecs_std = [t for t in tecs_final if "PH" not in str(t).upper()]
    
    asig_tec = []
    conteo = {t: 0 for t in tecs_final}
    
    for _, row in df_disp.iterrows():
        es_ph = "PH" in str(row["TECNICOS_INTEGRALES"]).upper()
        candidatos = tecs_ph if es_ph else tecs_std
        validos = [t for t in candidatos if conteo[t] < 50 and t != row["TECNICOS_INTEGRALES"]]
        if validos:
            elegido = min(validos, key=lambda x: conteo[x])
            nueva = row.copy()
            nueva["ASIGNADO_A"] = elegido
            asig_tec.append(nueva)
            conteo[elegido] += 1
    df_tec = pd.DataFrame(asig_tec)

    # ================================
    # PESTAÑAS CON GRÁFICAS DE INDICADORES
    # ================================
    tab_res, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    def crear_grafica_indicador(titulo, valor, color, es_moneda=True):
        fig = go.Figure(go.Indicator(
            mode = "number",
            value = valor,
            number = {'prefix': "$ " if es_moneda else "", 'valueformat': ",.0f"},
            title = {"text": titulo, 'font': {'size': 20}},
            domain = {'x': [0, 1], 'y': [0, 1]}
        ))
        fig.update_layout(height=180, margin=dict(l=10, r=10, t=40, b=10))
        return fig

    with tab_sup:
        if not df_sup.empty:
            st.subheader("📊 Indicadores de Supervisión")
            c1, c2 = st.columns(2)
            c1.plotly_chart(crear_grafica_indicador("Deuda Total a Gestionar", df_sup["_deuda_num"].sum(), "#007bff"), use_container_width=True)
            c2.plotly_chart(crear_grafica_indicador("Número de Pólizas", len(df_sup), "#007bff", False), use_container_width=True)
            
            st.divider()
            st.write("🏆 **Ranking de Gestión por Deuda**")
            rank_s = df_sup.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).reset_index()
            st.plotly_chart(px.bar(rank_s, x="ASIGNADO_A", y="_deuda_num", text_auto='.2s', labels={"ASIGNADO_A": "Supervisor", "_deuda_num": "Deuda"}), use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.info("Pólizas por Rango de Edad")
                st.plotly_chart(px.bar(df_sup["RANGO_EDAD"].astype(str).value_counts().reset_index(), x="RANGO_EDAD", y="count"), use_container_width=True)
            with col2:
                st.info("Composición por Subcategoría")
                st.plotly_chart(px.pie(df_sup, names="SUBCATEGORIA", values="_deuda_num", hole=0.4), use_container_width=True)

    with tab_tec:
        if not df_tec.empty:
            st.subheader("📊 Indicadores de Operarios")
            c3, c4 = st.columns(2)
            c3.plotly_chart(crear_grafica_indicador("Deuda Total a Gestionar", df_tec["_deuda_num"].sum(), "#28a745"), use_container_width=True)
            c4.plotly_chart(crear_grafica_indicador("Número de Pólizas", len(df_tec), "#28a745", False), use_container_width=True)

            st.divider()
            st.write("🏆 **Top 10 Operarios con Mayor Deuda**")
            top10 = df_tec.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
            st.plotly_chart(px.bar(top10, x="ASIGNADO_A", y="_deuda_num", text_auto='.2s', color_discrete_sequence=['#28a745']), use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                st.info("Pólizas por Rango de Edad")
                st.plotly_chart(px.bar(df_tec["RANGO_EDAD"].astype(str).value_counts().reset_index(), x="RANGO_EDAD", y="count"), use_container_width=True)
            with col4:
                st.info("Composición por Subcategoría")
                st.plotly_chart(px.pie(df_tec, names="SUBCATEGORIA", values="_deuda_num", hole=0.4), use_container_width=True)

    with tab_res:
        df_final = pd.concat([df_sup, df_tec], ignore_index=True)
        st.success(f"Carga final lista para descargar: {len(df_final)} pólizas.")
        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Asignacion")
        st.download_button("📥 Descargar Plan de Trabajo", data=output.getvalue(), file_name="plan_ita_final.xlsx")

else:
    st.info("👋 Sube el Excel para visualizar las gráficas de indicadores.")
