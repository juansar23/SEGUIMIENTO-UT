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

    columnas_necesarias = [
        "RANGO_EDAD",
        "SUBCATEGORIA",
        "DEUDA_TOTAL",
        "TECNICOS_INTEGRALES"
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"No existe la columna: {col}")
            st.stop()

    # =========================
    # LIMPIAR DEUDA
    # =========================
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # =========================
    # FILTROS
    # =========================
    st.sidebar.header("🎯 Filtros")

    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)

    deuda_minima = st.sidebar.number_input("Deuda mínima", min_value=0, value=100000, step=50000)

    st.sidebar.subheader("👥 Técnicos")
    modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")

    if modo_exclusion:
        excluir = st.sidebar.multiselect("Excluir técnicos", tecnicos)
        tecnicos_final = [t for t in tecnicos if t not in excluir]
    else:
        tecnicos_final = st.sidebar.multiselect("Incluir técnicos", tecnicos, default=tecnicos)

    # =========================
    # FILTRADO
    # =========================
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima) &
        (df["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_final))
    ].copy()

    df_filtrado = df_filtrado.sort_values("_deuda_num", ascending=False)

    # Limitar 50 por técnico
    df_filtrado = (
        df_filtrado
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
        .reset_index(drop=True)
    )

    # =========================
    # FORMATEAR FECHAS
    # =========================
    columnas_fecha = ["FECHA_VENCIMIENTO", "ULT_FECHAPAGO", "FECHA_ASIGNACION"]

    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # =========================
    # TABS
    # =========================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Tabla",
        "📊 Dashboard",
        "🧑‍💼 Asignación Supervisores",
        "🏆 Resumen Supervisores"
    ])

    # =========================
    # TAB 1 TABLA
    # =========================
    with tab1:

        st.success(f"Total pólizas: {len(df_filtrado)}")
        st.dataframe(df_filtrado, use_container_width=True)

        if not df_filtrado.empty:

            output = io.BytesIO()
            df_export = df_filtrado.copy()

            columnas_moneda = ["ULT_PAGO", "VALOR_ULTFACT", "DEUDA_TOTAL"]

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
                worksheet = writer.sheets["Reporte"]

                for col in columnas_moneda:
                    if col in df_export.columns:
                        col_idx = df_export.columns.get_loc(col) + 1
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=col_idx).number_format = '"$"#,##0'

            output.seek(0)

            st.download_button(
                "📥 Descargar Excel",
                data=output,
                file_name="resultado_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # =========================
    # TAB 2 DASHBOARD
    # =========================
    with tab2:

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Pólizas", len(df_filtrado))
        col2.metric("Total Deuda", f"$ {df_filtrado['_deuda_num'].sum():,.0f}")
        col3.metric("Técnicos Activos", df_filtrado["TECNICOS_INTEGRALES"].nunique())

        st.divider()

        top10 = (
            df_filtrado
            .groupby("TECNICOS_INTEGRALES")["_deuda_num"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        fig = px.bar(top10, x="TECNICOS_INTEGRALES", y="_deuda_num", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    # =========================
    # TAB 3 ASIGNACIÓN
    # =========================
    with tab3:

        if df_filtrado.empty:
            st.warning("No hay pólizas para asignar.")
        else:

            supervisores_input = st.text_area("Supervisores (uno por línea)")

            if supervisores_input:

                supervisores = [s.strip() for s in supervisores_input.split("\n") if s.strip()]
                max_por_supervisor = 8

                df_asignacion = df_filtrado.copy().reset_index(drop=True)
                df_asignacion["SUPERVISOR_ASIGNADO"] = None

                total_capacidad = len(supervisores) * max_por_supervisor
                contador_global = 0

                for sup in supervisores:
                    contador_local = 0
                    for i in range(len(df_asignacion)):
                        if contador_global >= total_capacidad:
                            break
                        if pd.isna(df_asignacion.at[i, "SUPERVISOR_ASIGNADO"]) and contador_local < max_por_supervisor:
                            df_asignacion.at[i, "SUPERVISOR_ASIGNADO"] = sup
                            contador_local += 1
                            contador_global += 1

                st.session_state["df_asignacion"] = df_asignacion

                st.dataframe(df_asignacion, use_container_width=True)

    # =========================
    # TAB 4 RESUMEN
    # =========================
    with tab4:

        if "df_asignacion" not in st.session_state:
            st.info("Genera primero la asignación.")
        else:

            df_asignacion = st.session_state["df_asignacion"]

            df_resumen = (
                df_asignacion
                .dropna(subset=["SUPERVISOR_ASIGNADO"])
                .groupby("SUPERVISOR_ASIGNADO")
                .agg(
                    Total_Polizas=("SUPERVISOR_ASIGNADO", "count"),
                    Total_Deuda=("_deuda_num", "sum"),
                    Promedio_Deuda=("_deuda_num", "mean")
                )
                .reset_index()
            )

            st.dataframe(df_resumen, use_container_width=True)

            fig = px.bar(df_resumen, x="SUPERVISOR_ASIGNADO", y="Total_Deuda", text_auto=True)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Sube un archivo para comenzar.")
