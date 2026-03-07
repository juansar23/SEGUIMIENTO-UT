import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo Supervisores", layout="wide")

st.title("📊 Dashboard Ejecutivo - Supervisores")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    columnas_necesarias = [
        "RANGO_EDAD",
        "SUBCATEGORIA",
        "DEUDA_TOTAL",
        "SUPERVISOR"
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ Falta la columna: {col}")
            st.stop()

    # Supervisores permitidos
    supervisores_permitidos = [
        "FAVIO ERNESTO VASQUEZ ROMERO",
        "DEGUIN ZOCRATE DEGUIN ZOCRATE",
        "YESID RAFAEL REALES MORENO",
        "ABILIO SEGUNDO ARAUJO ARIÑO",
        "JAVIER DAVID GOMEZ BARRIOS"
    ]

    df = df[df["SUPERVISOR"].isin(supervisores_permitidos)]

    # Limpiar deuda
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"]
        .astype(str)
        .str.replace("$","",regex=False)
        .str.replace(",","",regex=False)
        .str.replace(".","",regex=False)
    )

    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ========================
    # FILTROS
    # ========================

    st.sidebar.header("🎯 Filtros")

    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    supervisores = sorted(df["SUPERVISOR"].unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, subcategorias)

    deuda_min = st.sidebar.number_input(
        "Deuda mínima",
        min_value=0,
        value=100000,
        step=50000
    )

    supervisores_sel = st.sidebar.multiselect(
        "Supervisores",
        supervisores,
        supervisores
    )

    df_filtrado = df[
        (df["RANGO_EDAD"].isin(rangos_sel)) &
        (df["SUBCATEGORIA"].isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_min) &
        (df["SUPERVISOR"].isin(supervisores_sel))
    ].copy()

    # ========================
    # KPIs GERENCIALES
    # ========================

    total_polizas = len(df_filtrado)
    total_deuda = df_filtrado["_deuda_num"].sum()
    deuda_promedio = df_filtrado["_deuda_num"].mean()
    supervisores_activos = df_filtrado["SUPERVISOR"].nunique()

    col1,col2,col3,col4 = st.columns(4)

    col1.metric("📄 Total Pólizas", f"{total_polizas:,}")
    col2.metric("💰 Total Deuda", f"$ {total_deuda:,.0f}")
    col3.metric("📊 Deuda Promedio", f"$ {deuda_promedio:,.0f}")
    col4.metric("👨‍💼 Supervisores", supervisores_activos)

    st.divider()

    # ========================
    # GRAFICA DEUDA POR SUPERVISOR
    # ========================

    deuda_supervisor = (
        df_filtrado
        .groupby("SUPERVISOR")["_deuda_num"]
        .sum()
        .reset_index()
        .sort_values("_deuda_num", ascending=False)
    )

    fig = px.bar(
        deuda_supervisor,
        x="SUPERVISOR",
        y="_deuda_num",
        text_auto=True,
        title="💰 Deuda Total por Supervisor"
    )

    st.plotly_chart(fig, use_container_width=True)

    # ========================
    # PARTICIPACION SUPERVISORES
    # ========================

    fig2 = px.pie(
        deuda_supervisor,
        names="SUPERVISOR",
        values="_deuda_num",
        title="📊 Participación de Deuda por Supervisor"
    )

    st.plotly_chart(fig2, use_container_width=True)

    # ========================
    # RANGO DE EDAD
    # ========================

    rango = (
        df_filtrado["RANGO_EDAD"]
        .value_counts()
        .reset_index()
    )

    rango.columns = ["Rango Edad","Cantidad"]

    fig3 = px.bar(
        rango,
        x="Rango Edad",
        y="Cantidad",
        text_auto=True,
        title="📈 Distribución por Rango de Edad"
    )

    st.plotly_chart(fig3, use_container_width=True)

    # ========================
    # TOP POLIZAS
    # ========================

    st.subheader("🏆 Top 20 Pólizas con Mayor Deuda")

    top_polizas = (
        df_filtrado
        .sort_values("_deuda_num", ascending=False)
        .head(20)
    )

    st.dataframe(top_polizas, use_container_width=True)

    # ========================
    # DESCARGA
    # ========================

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_filtrado.to_excel(writer, index=False)

    st.download_button(
        "📥 Descargar resultado",
        data=output.getvalue(),
        file_name="reporte_supervisores.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👆 Sube un archivo Excel para comenzar.")
