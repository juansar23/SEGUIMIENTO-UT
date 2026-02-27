import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Seguimiento Unidad de Trabajo")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ==================================================
    # DETECTAR SUBCATEGORIA
    # ==================================================
    columnas_normalizadas = {col.lower(): col for col in df.columns}

    if "subcategoría" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoría"]
    elif "subcategoria" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoria"]
    else:
        st.error("No existe columna Subcategoría")
        st.stop()

    columnas_obligatorias = ["RANGO_EDAD", "TECNICOS INTEGRALES", "DEUDA TOTAL"]
    for col in columnas_obligatorias:
        if col not in df.columns:
            st.error(f"No existe columna {col}")
            st.stop()

    # ==================================================
    # SIDEBAR FILTROS
    # ==================================================
    st.sidebar.header("🎯 Filtros")

    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df[col_sub].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)

    deuda_minima = st.sidebar.number_input(
        "Deudas mayores a:",
        min_value=0,
        value=100000,
        step=50000
    )

    # ==================================================
    # FILTRO INTELIGENTE TECNICOS
    # ==================================================
    st.sidebar.subheader("👥 Técnicos Integrales")

    modo_exclusion = st.sidebar.checkbox("🧠 Seleccionar todos excepto...")

    if modo_exclusion:
        tecnicos_excluir = st.sidebar.multiselect("🚫 Técnicos a excluir", tecnicos)
        tecnicos_final = [t for t in tecnicos if t not in tecnicos_excluir]
    else:
        tecnicos_final = st.sidebar.multiselect(
            "✅ Técnicos a incluir",
            tecnicos,
            default=tecnicos
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"📊 **Técnicos activos:** {len(tecnicos_final)}")

    if st.sidebar.button("⚡ Limpiar filtros"):
        st.experimental_rerun()

    # ==================================================
    # LIMPIAR DEUDA
    # ==================================================
    df["_deuda_num"] = (
        df["DEUDA TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
    )

    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ==================================================
    # FILTRAR
    # ==================================================
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df[col_sub].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima) &
        (df["TECNICOS INTEGRALES"].astype(str).isin(tecnicos_final))
    ].copy()

    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)

    # LIMITE 50 POLIZAS POR TECNICO
    df_filtrado = (
        df_filtrado
        .groupby("TECNICOS INTEGRALES")
        .head(50)
        .reset_index(drop=True)
    )

    # ==================================================
    # TABS
    # ==================================================
    tab1, tab2 = st.tabs(["📋 Tabla", "📊 Dashboard Ejecutivo"])

    # ==================================================
    # TABLA
    # ==================================================
    with tab1:

        st.subheader("Resultado Final")
        st.success(f"Total pólizas: {len(df_filtrado)}")

        st.dataframe(df_filtrado, use_container_width=True)

        if not df_filtrado.empty:
            output = io.BytesIO()
            df_export = df_filtrado.drop(columns=["_deuda_num"], errors="ignore")
            df_export.to_excel(output, index=False, engine="openpyxl")
            output.seek(0)

            st.download_button(
                "📥 Descargar archivo",
                data=output,
                file_name="resultado_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # ==================================================
    # DASHBOARD
    # ==================================================
    with tab2:

        st.subheader("📊 Indicadores Clave")

        total_polizas = len(df_filtrado)
        total_deuda = df_filtrado["_deuda_num"].sum()
        tecnicos_activos = df_filtrado["TECNICOS INTEGRALES"].nunique()

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Pólizas", total_polizas)
        col2.metric("Total Deuda", f"${total_deuda:,.0f}")
        col3.metric("Técnicos Activos", tecnicos_activos)

        st.divider()

        # ==================================================
        # TOP 10 EN TABLA
        # ==================================================
        st.subheader("🏆 Top 10 Técnicos con Mayor Deuda")

        top10 = (
            df_filtrado
            .groupby("TECNICOS INTEGRALES")["_deuda_num"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        top10.columns = ["Técnico Integral", "Total Deuda"]
        top10["Total Deuda"] = top10["Total Deuda"].apply(lambda x: f"${x:,.0f}")

        st.dataframe(top10, use_container_width=True)

        # ==================================================
        # SUBCATEGORIA
        # ==================================================
        st.subheader("🥧 Distribución por Subcategoría")

        conteo_sub = df_filtrado[col_sub].value_counts().reset_index()
        conteo_sub.columns = ["Subcategoría", "Cantidad"]

        fig_pie = px.pie(conteo_sub, names="Subcategoría", values="Cantidad")
        st.plotly_chart(fig_pie, use_container_width=True)

        # ==================================================
        # RANGO EDAD ORDEN PERSONALIZADO
        # ==================================================
        st.subheader("📊 Pólizas por Rango de Edad")

        orden_personalizado = [
            "0-30",
            "31-60",
            "61-90",
            "91-120",
            "121-360",
            "361-1080",
            ">1080"
        ]

        conteo_edad = (
            df_filtrado["RANGO_EDAD"]
            .value_counts()
            .reindex(orden_personalizado, fill_value=0)
            .reset_index()
        )

        conteo_edad.columns = ["Rango Edad", "Cantidad"]

        fig_edad = px.bar(
            conteo_edad,
            x="Rango Edad",
            y="Cantidad",
            text_auto=True
        )

        st.plotly_chart(fig_edad, use_container_width=True)

else:
    st.info("👆 Sube un archivo para comenzar.")
