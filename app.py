import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Unidad de Trabajo")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ================================
    # VALIDAR COLUMNAS CLAVE
    # ================================
    columnas_necesarias = [
        "RANGO_EDAD",
        "SUBCATEGORIA",
        "DEUDA_TOTAL",
        "TECNICOS_INTEGRALES"
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ No existe la columna: {col}")
            st.stop()

    # ================================
    # LIMPIAR DEUDA PARA CALCULOS
    # ================================
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )

    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # SIDEBAR FILTROS
    # ================================
    st.sidebar.header("🎯 Filtros")

    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)

    deuda_minima = st.sidebar.number_input(
        "Deudas mayores a:",
        min_value=0,
        value=100000,
        step=50000
    )

    # Seleccionar todos excepto
    st.sidebar.subheader("👥 Técnicos Integrales")

    modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")

    if modo_exclusion:
        excluir = st.sidebar.multiselect("Técnicos a excluir", tecnicos)
        tecnicos_final = [t for t in tecnicos if t not in excluir]
    else:
        tecnicos_final = st.sidebar.multiselect(
            "Técnicos a incluir",
            tecnicos,
            default=tecnicos
        )

    st.sidebar.markdown(f"📊 Técnicos activos: {len(tecnicos_final)}")

    if st.sidebar.button("Limpiar filtros"):
        st.experimental_rerun()

    # ================================
    # FILTRAR DATA
    # ================================
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima) &
        (df["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_final))
    ].copy()

    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)

    # Limitar 50 por técnico
    df_filtrado = (
        df_filtrado
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
        .reset_index(drop=True)
    )

    # ================================
    # FORMATEAR FECHAS (SIN HORA)
    # ================================
    columnas_fecha = [
        "FECHA_VENCIMIENTO",
        "ULT_FECHAPAGO",
        "FECHA_ASIGNACION"
    ]

    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(
                df_filtrado[col],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

    # ================================
    # TABS
    # ================================
    tab1, tab2 = st.tabs(["📋 Tabla", "📊 Dashboard"])

    # ================================
    # TABLA + DESCARGA EXCEL
    # ================================
    with tab1:

        st.success(f"Total pólizas: {len(df_filtrado)}")
        st.dataframe(df_filtrado, use_container_width=True)

        if not df_filtrado.empty:

            output = io.BytesIO()
            df_export = df_filtrado.copy()

            columnas_moneda = [
                "ULT_PAGO",
                "VALOR_ULTFACT",
                "DEUDA_TOTAL"
            ]

            # Convertir a número real
            for col in columnas_moneda:
                if col in df_export.columns:
                    df_export[col] = (
                        df_export[col]
                        .astype(str)
                        .str.replace("$", "", regex=False)
                        .str.replace(",", "", regex=False)
                        .str.replace(".", "", regex=False)
                        .str.strip()
                    )
                    df_export[col] = pd.to_numeric(df_export[col], errors="coerce").fillna(0)

            df_export = df_export.drop(columns=["_deuda_num"], errors="ignore")

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Reporte")

                workbook = writer.book
                worksheet = writer.sheets["Reporte"]

                for col in columnas_moneda:
                    if col in df_export.columns:
                        col_idx = df_export.columns.get_loc(col) + 1
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=col_idx).number_format = '"$"#,##0'

            output.seek(0)

            st.download_button(
                "📥 Descargar archivo",
                data=output,
                file_name="resultado_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # ================================
    # DASHBOARD
    # ================================
    with tab2:

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Pólizas", len(df_filtrado))
        col2.metric("Total Deuda", f"$ {df_filtrado['_deuda_num'].sum():,.0f}")
        col3.metric("Técnicos Activos", df_filtrado["TECNICOS_INTEGRALES"].nunique())

        st.divider()

        # Top 10 técnicos
        st.subheader("🏆 Top 10 Técnicos con Mayor Deuda")

        top10 = (
            df_filtrado
            .groupby("TECNICOS_INTEGRALES")["_deuda_num"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        top10.columns = ["Técnico", "Total Deuda"]
        top10["Total Deuda"] = top10["Total Deuda"].apply(lambda x: f"$ {x:,.0f}")

        st.dataframe(top10, use_container_width=True)

        # Gráfica Rango Edad
        st.subheader("📊 Pólizas por Rango de Edad")

        conteo = df_filtrado["RANGO_EDAD"].astype(str).value_counts().reset_index()
        conteo.columns = ["Rango Edad", "Cantidad"]

        fig = px.bar(
            conteo,
            x="Rango Edad",
            y="Cantidad",
            text_auto=True
        )

        st.plotly_chart(fig, use_container_width=True)

        # Pie Subcategoría
        st.subheader("🥧 Distribución por Subcategoría")

        conteo_sub = df_filtrado["SUBCATEGORIA"].value_counts().reset_index()
        conteo_sub.columns = ["Subcategoría", "Cantidad"]

        fig2 = px.pie(
            conteo_sub,
            names="Subcategoría",
            values="Cantidad"
        )

        st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("👆 Sube un archivo para comenzar.")
