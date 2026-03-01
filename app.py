import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Unidad de Trabajo")

archivo = st.file_uploader("Sube el archivo Excel consolidado", type=["xlsx"])

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
            st.error(f"No existe la columna requerida: {col}")
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
    # SIDEBAR FILTROS
    # =========================
    st.sidebar.header("🎯 Filtros Generales")

    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)
    deuda_minima = st.sidebar.number_input("Deuda mínima", min_value=0, value=100000, step=50000)

    st.sidebar.subheader("👥 Técnicos")
    tecnicos_sel = st.sidebar.multiselect("Seleccionar técnicos", tecnicos, default=tecnicos)

    # =========================
    # FILTRADO TÉCNICOS
    # =========================
    df_tecnicos = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima) &
        (df["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_sel))
    ].copy()

    df_tecnicos = df_tecnicos.sort_values("_deuda_num", ascending=False)

    # Límite 50 por técnico
    df_tecnicos = (
        df_tecnicos
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
        .reset_index(drop=True)
    )

    # =========================
    # TABS
    # =========================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Tabla Técnicos",
        "📊 Dashboard",
        "🧑‍💼 Asignación Supervisores",
        "🏆 Resumen Supervisores"
    ])

    # =====================================================
    # TAB 1 - TÉCNICOS
    # =====================================================
    with tab1:

        st.success(f"Total pólizas asignadas a técnicos: {len(df_tecnicos)}")
        st.dataframe(df_tecnicos, use_container_width=True)

        if not df_tecnicos.empty:

            output = io.BytesIO()
            df_export = df_tecnicos.copy()

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
                df_export.to_excel(writer, index=False, sheet_name="Tecnicos")
                worksheet = writer.sheets["Tecnicos"]

                for col in columnas_moneda:
                    if col in df_export.columns:
                        col_idx = df_export.columns.get_loc(col) + 1
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=col_idx).number_format = '"$"#,##0'

            output.seek(0)

            st.download_button(
                "📥 Descargar Excel Técnicos",
                data=output,
                file_name="asignacion_tecnicos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # =====================================================
    # TAB 2 - DASHBOARD
    # =====================================================
    with tab2:

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Pólizas", len(df_tecnicos))
        col2.metric("Total Deuda", f"$ {df_tecnicos['_deuda_num'].sum():,.0f}")
        col3.metric("Técnicos Activos", df_tecnicos["TECNICOS_INTEGRALES"].nunique())

        st.divider()

        top10 = (
            df_tecnicos
            .groupby("TECNICOS_INTEGRALES")["_deuda_num"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        fig = px.bar(top10, x="TECNICOS_INTEGRALES", y="_deuda_num", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    # =====================================================
    # TAB 3 - ASIGNACIÓN SUPERVISORES
    # =====================================================
    with tab3:

        st.subheader("🧑‍💼 Asignación Supervisores")

        SUPERVISORES_FIJOS = [
            "FAVIO ERNESTO VASQUEZ ROMERO",
            "DEGUIN ZOCRATE DEGUIN ZOCRATE",
            "YESID RAFAEL REALES MORENO",
            "ABILIO SEGUNDO ARAUJO ARIÑO",
            "JAVIER MESA MARTINEZ"
        ]

        max_por_supervisor = 8

        activar = st.toggle("Activar asignación a supervisores")

        if activar:

            supervisores_seleccionados = st.multiselect(
                "Selecciona supervisores:",
                SUPERVISORES_FIJOS
            )

            if supervisores_seleccionados:

                df_sup = df[
                    (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
                    (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
                    (df["_deuda_num"] >= deuda_minima)
                ].copy()

                df_sup = df_sup.sort_values("_deuda_num", ascending=False).reset_index(drop=True)
                df_sup["SUPERVISOR_ASIGNADO"] = None

                total_capacidad = len(supervisores_seleccionados) * max_por_supervisor
                contador_global = 0

                for sup in supervisores_seleccionados:
                    contador_local = 0
                    for i in range(len(df_sup)):
                        if contador_global >= total_capacidad:
                            break
                        if pd.isna(df_sup.at[i, "SUPERVISOR_ASIGNADO"]) and contador_local < max_por_supervisor:
                            df_sup.at[i, "SUPERVISOR_ASIGNADO"] = sup
                            contador_local += 1
                            contador_global += 1

                st.dataframe(df_sup, use_container_width=True)

        else:
            st.info("Asignación desactivada.")

    # =====================================================
    # TAB 4 - RESUMEN SUPERVISORES
    # =====================================================
    with tab4:

        st.subheader("🏆 Resumen Supervisores")

        SUPERVISORES_FIJOS = [
            "FAVIO ERNESTO VASQUEZ ROMERO",
            "DEGUIN ZOCRATE DEGUIN ZOCRATE",
            "YESID RAFAEL REALES MORENO",
            "ABILIO SEGUNDO ARAUJO ARIÑO",
            "JAVIER MESA MARTINEZ"
        ]

        max_por_supervisor = 8

        activar_resumen = st.toggle("Activar resumen supervisores")

        if activar_resumen:

            supervisores_seleccionados = st.multiselect(
                "Selecciona supervisores para resumen:",
                SUPERVISORES_FIJOS,
                key="resumen"
            )

            if supervisores_seleccionados:

                df_sup = df[
                    (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
                    (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
                    (df["_deuda_num"] >= deuda_minima)
                ].copy()

                df_sup = df_sup.sort_values("_deuda_num", ascending=False).reset_index(drop=True)
                df_sup["SUPERVISOR_ASIGNADO"] = None

                total_capacidad = len(supervisores_seleccionados) * max_por_supervisor
                contador_global = 0

                for sup in supervisores_seleccionados:
                    contador_local = 0
                    for i in range(len(df_sup)):
                        if contador_global >= total_capacidad:
                            break
                        if pd.isna(df_sup.at[i, "SUPERVISOR_ASIGNADO"]) and contador_local < max_por_supervisor:
                            df_sup.at[i, "SUPERVISOR_ASIGNADO"] = sup
                            contador_local += 1
                            contador_global += 1

                df_resumen = (
                    df_sup
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
            st.info("Resumen desactivado.")

else:
    st.info("Sube el archivo consolidado para comenzar.")
