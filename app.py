import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Seguimiento UT", layout="wide")

st.title("📊 Seguimiento Unidad de Trabajo")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ==============================
    # DETECTAR SUBCATEGORIA
    # ==============================
    columnas_normalizadas = {col.lower(): col for col in df.columns}

    if "subcategoría" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoría"]
    elif "subcategoria" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoria"]
    else:
        st.error("No existe columna Subcategoría")
        st.stop()

    # ==============================
    # VALIDAR COLUMNAS
    # ==============================
    if "RANGO_EDAD" not in df.columns:
        st.error("No existe columna RANGO_EDAD")
        st.stop()

    if "TECNICOS INTEGRALES" not in df.columns:
        st.error("No existe columna TECNICOS INTEGRALES")
        st.stop()

    # ==============================
    # FILTROS
    # ==============================
    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df[col_sub].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS INTEGRALES"].dropna().astype(str).unique())

    col1, col2, col3 = st.columns(3)

    with col1:
        rangos_sel = st.multiselect("Rango Edad", rangos, default=rangos)

    with col2:
        sub_sel = st.multiselect("Subcategoría", subcategorias, default=subcategorias)

    with col3:
        tecnicos_sel = st.multiselect("Técnicos", tecnicos, default=tecnicos)

    deuda_minima = st.number_input(
        "Filtrar deudas mayores a:",
        min_value=0,
        value=100000,
        step=50000
    )

    # ==============================
    # LIMPIAR DEUDA
    # ==============================
    df["_deuda_num"] = (
        df["DEUDA TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
    )

    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ==============================
    # APLICAR FILTROS
    # ==============================
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df[col_sub].astype(str).isin(sub_sel)) &
        (df["TECNICOS INTEGRALES"].astype(str).isin(tecnicos_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].copy()

    # Ordenar por mayor deuda
    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)

    # Máximo 50 pólizas por técnico
    df_filtrado = (
        df_filtrado
        .groupby("TECNICOS INTEGRALES")
        .head(50)
        .reset_index(drop=True)
    )

    # Formato fecha corta
    columnas_fecha = [
        "FECHA_VENCIMIENTO",
        "ULT_FECHA_PAGO",
        "FECHA DE ASIGNACION"
    ]

    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(
                df_filtrado[col], errors="coerce"
            ).dt.strftime("%d-%m-%Y")

    # ==========================================
    # PESTAÑAS
    # ==========================================
    tab1, tab2 = st.tabs(["📋 Tabla y Descarga", "📊 Dashboard"])

    # ==========================================
    # TABLA
    # ==========================================
    with tab1:

        st.subheader("Resultado Final")
        st.success(f"Total pólizas: {len(df_filtrado)}")

        st.dataframe(df_filtrado, use_container_width=True)

        if not df_filtrado.empty:
            output = io.BytesIO()
            df_filtrado.drop(columns=["_deuda_num"], errors="ignore") \
                .to_excel(output, index=False, engine="openpyxl")
            output.seek(0)

            st.download_button(
                "📥 Descargar archivo",
                data=output,
                file_name="resultado_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # ==========================================
    # DASHBOARD
    # ==========================================
    with tab2:

        st.subheader("📊 Indicadores Generales")

        colA, colB, colC = st.columns(3)

        colA.metric("Total Pólizas", len(df_filtrado))
        colB.metric("Total Deuda", f"${df_filtrado['_deuda_num'].sum():,.0f}")
        colC.metric("Técnicos Activos", df_filtrado["TECNICOS INTEGRALES"].nunique())

        st.divider()

        # ------------------------------
        # GRAFICO SUBCATEGORIA
        # ------------------------------
        conteo_sub = df_filtrado[col_sub].value_counts().reset_index()
        conteo_sub.columns = ["Subcategoría", "Cantidad"]

        fig1 = px.bar(
            conteo_sub,
            x="Subcategoría",
            y="Cantidad",
            title="Pólizas por Subcategoría",
            text_auto=True
        )

        st.plotly_chart(fig1, use_container_width=True)

        # ------------------------------
        # GRAFICO RANGO EDAD
        # ------------------------------
        conteo_edad = df_filtrado["RANGO_EDAD"].value_counts().reset_index()
        conteo_edad.columns = ["Rango Edad", "Cantidad"]

        fig2 = px.bar(
            conteo_edad,
            x="Rango Edad",
            y="Cantidad",
            title="Pólizas por Rango de Edad",
            text_auto=True
        )

        st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("Sube un archivo para comenzar.")
