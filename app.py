import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración de página con tema oscuro/limpio
st.set_page_config(page_title="Gestión UT - Sistema ITA", layout="wide", initial_sidebar_state="expanded")

# Estilo personalizado para mejorar la estética
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; background-color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f1f3f4; border-radius: 5px 5px 0px 0px; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #007bff; color: white !important; }
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

archivo = st.file_uploader("📂 Sube el archivo Excel de Inventario", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # Validaciones de columnas
    columnas_necesarias = ["RANGO_EDAD", "SUBCATEGORIA", "DEUDA_TOTAL", "TECNICOS_INTEGRALES"]
    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ Falta la columna necesaria: {col}")
            st.stop()

    # Limpieza de Deuda (Remover símbolos y convertir a número)
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # SIDEBAR: FILTROS OPTIMIZADOS
    # ================================
    st.sidebar.header("🎯 Panel de Control")
    
    # FIX para TypeError: Convertir a string antes de ordenar y filtrar nulos
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos_disponibles = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    with st.sidebar.expander("📍 Filtros de Segmentación", expanded=True):
        rangos_sel = st.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
        sub_sel = st.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
        deuda_minima = st.number_input("Deuda mínima ($)", min_value=0, value=100000, step=50000)

    with st.sidebar.expander("👨‍💼 Asignación Supervisores"):
        sups_final = st.multiselect("Incluir Supervisores", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    with st.sidebar.expander("👥 Asignación Operarios"):
        modo_exc = st.checkbox("Excluir técnicos seleccionados")
        tecs_sel = st.multiselect("Lista de Técnicos", tecnicos_disponibles, default=tecnicos_disponibles if not modo_exc else [])
        tecs_final = [t for t in tecnicos_disponibles if t not in tecs_sel] if modo_exc else tecs_sel

    # ================================
    # LÓGICA DE ASIGNACIÓN (SIN CRUCES)
    # ================================
    # Aplicar filtros globales (Rango, Subcategoría, Deuda)
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by="_deuda_num", ascending=False).copy()

    # 1. Asignación Supervisores (Prioridad de Deuda)
    df_supervisores = df_base.head(len(sups_final) * 8).copy()
    if not df_supervisores.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = nombres_sups[:len(df_supervisores)]

    # 2. Asignación Operarios (Resto del inventario)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    df_restante = df_restante[df_restante["TECNICOS_INTEGRALES"].astype(str).isin(tecs_final)]
    df_tecnicos = df_restante.groupby("TECNICOS_INTEGRALES").head(50).copy()
    df_tecnicos["ASIGNADO_A"] = df_tecnicos["TECNICOS_INTEGRALES"]

    # ================================
    # INTERFAZ DE USUARIO (TABS)
    # ================================
    tab_resumen, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    with tab_resumen:
        df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Pólizas", len(df_final))
        col_m2.metric("Deuda Total", f"$ {df_final['_deuda_num'].sum():,.0f}")
        col_m3.metric("Efectividad Filtros", f"{(len(df_final)/len(df)*100):.1f}%")

        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)
        
        # Descarga estética
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Asignacion_ITA")
        st.download_button("📥 Descargar Plan de Trabajo Excel", data=output.getvalue(), file_name="plan_trabajo_ut.xlsx")

    with tab_sup:
        st.subheader("Análisis de Segmentación - Supervisores")
        if not df_supervisores.empty:
            c1, c2 = st.columns(2)
            with c1:
                # Reemplazo solicitado: Pólizas por Rango de Edad
                st.info("Distribución por Rango de Edad")
                conteo_edad_s = df_supervisores["RANGO_EDAD"].astype(str).value_counts().reset_index()
                conteo_edad_s.columns = ["Rango", "Pólizas"]
                st.plotly_chart(px.bar(conteo_edad_s, x="Rango", y="Pólizas", text_auto=True, color_discrete_sequence=['#007bff']), use_container_width=True)
            
            with c2:
                st.info("Deuda por Subcategoría")
                st.plotly_chart(px.pie(df_supervisores, names="SUBCATEGORIA", values="_deuda_num", hole=0.4), use_container_width=True)
            
            st.divider()
            st.write("📂 **Carga asignada por Supervisor**")
            carga_s = df_supervisores.groupby("ASIGNADO_A").agg({"_deuda_num": "sum", "RANGO_EDAD": "count"}).reset_index()
            carga_s.columns = ["Nombre", "Deuda Total", "Pólizas"]
            st.table(carga_s.style.format({"Deuda Total": "$ {:,.0f}"}))
        else:
            st.warning("No hay pólizas asignadas a supervisores con los filtros actuales.")

    with tab_tec:
        st.subheader("Análisis de Segmentación - Operarios")
        if not df_tecnicos.empty:
            c3, c4 = st.columns(2)
            with c3:
                st.info("Distribución por Rango de Edad")
                conteo_edad_t = df_tecnicos["RANGO_EDAD"].astype(str).value_counts().reset_index()
                conteo_edad_t.columns = ["Rango", "Pólizas"]
                st.plotly_chart(px.bar(conteo_edad_t, x="Rango", y="Pólizas", text_auto=True, color_discrete_sequence=['#28a745']), use_container_width=True)
            
            with c4:
                st.info("Composición por Subcategoría")
                # FIX para ValueError: Validar que existan datos antes de graficar Pie
                conteo_sub_t = df_tecnicos["SUBCATEGORIA"].value_counts().reset_index()
                conteo_sub_t.columns = ["Subcat", "Cant"]
                st.plotly_chart(px.pie(conteo_sub_t, names="Subcat", values="Cant", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)

            st.divider()
            st.write("🏆 **Top 10 Operarios por Deuda Asignada**")
            top10 = df_tecnicos.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
            top10.columns = ["Operario", "Deuda"]
            st.table(top10.style.format({"Deuda": "$ {:,.0f}"}))
        else:
            st.warning("No hay pólizas asignadas a operarios con estos filtros.")

else:
    st.info("👋 Por favor, carga el archivo Excel para visualizar los datos del Sistema ITA.")
