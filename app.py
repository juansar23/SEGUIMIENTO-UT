import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Asignación de Trabajo")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # 1. VALIDAR COLUMNAS CLAVE
    columnas_necesarias = ["RANGO_EDAD", "SUBCATEGORIA", "DEUDA_TOTAL", "TECNICOS_INTEGRALES", "SUPERVISORES"]
    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ No existe la columna: {col}")
            st.stop()

    # Limpiar deuda
    df["_deuda_num"] = (df["DEUDA_TOTAL"].astype(str).str.replace(r'[$,.]', '', regex=True).str.strip())
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # 2. SIDEBAR FILTROS
    st.sidebar.header("🎯 Filtros")
    
    # Filtros base
    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())
    supervisores = sorted(df["SUPERVISORES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)
    
    # Filtro Técnicos
    tecnicos_final = st.sidebar.multiselect("Técnicos", tecnicos, default=tecnicos)
    
    # Filtro Supervisores
    supervisores_final = st.sidebar.multiselect("Supervisores", supervisores, default=supervisores)

    # 3. FILTRAR Y LIMITAR
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_final)) &
        (df["SUPERVISORES"].astype(str).isin(supervisores_final))
    ].copy()

    # Aplicar límites: 50 técnicos, 8 supervisores
    df_filtrado = df_filtrado.groupby("TECNICOS_INTEGRALES").head(50)
    df_filtrado = df_filtrado.groupby("SUPERVISORES").head(8)

    # 4. TABS
    tab1, tab2 = st.tabs(["📋 Tabla Detalle", "📊 Dashboard"])

    with tab1:
        st.success(f"Total pólizas cargadas: {len(df_filtrado)}")
        st.dataframe(df_filtrado, use_container_width=True)

    with tab2:
        # Métricas
        col1, col2, col3 = st.columns(3)
        col1.metric("Pólizas", len(df_filtrado))
        col2.metric("Deuda Total", f"$ {df_filtrado['_deuda_num'].sum():,.0f}")
        col3.metric("Supervisores Activos", df_filtrado["SUPERVISORES"].nunique())

        st.divider()

        # Gráficas Técnicos
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏆 Top 10 Técnicos (Deuda)")
            top10 = df_filtrado.groupby("TECNICOS_INTEGRALES")["_deuda_num"].sum().nlargest(10).reset_index()
            st.bar_chart(top10.set_index("TECNICOS_INTEGRALES"))

        # Gráficas Supervisores
        with c2:
            st.subheader("👥 Carga por Supervisor")
            carga_sup = df_filtrado["SUPERVISORES"].value_counts().reset_index()
            carga_sup.columns = ["Supervisor", "Pólizas"]
            fig = px.pie(carga_sup, names="Supervisor", values="Pólizas", hole=0.3)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👆 Sube un archivo Excel para comenzar.")
