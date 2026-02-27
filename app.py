import streamlit as st
import pandas as pd
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="Seguimiento UT", layout="wide")

st.title("📊 Seguimiento Unidad de Trabajo")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ---------------------------------
    # DETECTAR COLUMNA SUBCATEGORIA
    # ---------------------------------
    columnas_normalizadas = {col.lower(): col for col in df.columns}

    if "subcategoría" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoría"]
    elif "subcategoria" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoria"]
    else:
        st.error("❌ No existe columna Subcategoría")
        st.stop()

    # ---------------------------------
    # VALIDAR COLUMNAS NECESARIAS
    # ---------------------------------
    if "RANGO_EDAD" not in df.columns:
        st.error("❌ No existe columna RANGO_EDAD")
        st.stop()

    if "TECNICOS INTEGRALES" not in df.columns:
        st.error("❌ No existe columna TECNICOS INTEGRALES")
        st.stop()

    # ---------------------------------
    # FILTRO RANGO EDAD
    # ---------------------------------
    rangos_disponibles = sorted(
        df["RANGO_EDAD"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    rangos_seleccionados = st.multiselect(
        "Seleccione Rangos de Edad:",
        rangos_disponibles,
        default=rangos_disponibles
    )

    # ---------------------------------
    # FILTRO SUBCATEGORIA
    # ---------------------------------
    subcategorias_disponibles = sorted(
        df[col_sub]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    subcategorias_seleccionadas = st.multiselect(
        "Seleccione Subcategorías:",
        subcategorias_disponibles,
        default=subcategorias_disponibles
    )

    # ---------------------------------
    # FILTRO TECNICOS
    # ---------------------------------
    tecnicos_disponibles = sorted(
        df["TECNICOS INTEGRALES"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    tecnicos_seleccionados = st.multiselect(
        "Seleccione Técnicos Integrales:",
        tecnicos_disponibles,
        default=tecnicos_disponibles
    )

    # ---------------------------------
    # CONVERTIR DEUDA TOTAL A NUMERO
    # ---------------------------------
    df["_deuda_num"] = (
        df["DEUDA TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )

    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ---------------------------------
    # FILTRO DEUDA MINIMA
    # ---------------------------------
    deuda_minima = st.number_input(
        "Filtrar deudas mayores a:",
        min_value=0,
        value=100000,
        step=50000
    )

    # ---------------------------------
    # APLICAR FILTROS
    # ---------------------------------
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_seleccionados)) &
        (df[col_sub].astype(str).isin(subcategorias_seleccionadas)) &
        (df["TECNICOS INTEGRALES"].astype(str).isin(tecnicos_seleccionados)) &
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

    # ---------------------------------
    # FORMATO FECHA CORTA
    # ---------------------------------
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

    df_filtrado = df_filtrado.drop(columns=["_deuda_num"])

    # ---------------------------------
    # MOSTRAR TABLA FINAL
    # ---------------------------------
    st.success(f"Registros finales: {len(df_filtrado)}")
    st.dataframe(df_filtrado, use_container_width=True)

    # =================================
    # 📊 GRAFICA 1: POLIZAS POR SUBCATEGORIA
    # =================================
    st.subheader("📊 Pólizas por Subcategoría")

    conteo_sub = df_filtrado[col_sub].value_counts()

    fig1, ax1 = plt.subplots()
    conteo_sub.plot(kind="bar", ax=ax1)
    ax1.set_ylabel("Cantidad de Pólizas")
    ax1.set_xlabel("Subcategoría")
    ax1.set_title("Cantidad de Pólizas por Subcategoría")
    plt.xticks(rotation=45)

    st.pyplot(fig1)

    # =================================
    # 📊 GRAFICA 2: POLIZAS POR RANGO EDAD
    # =================================
    st.subheader("📊 Pólizas por Rango de Edad")

    conteo_edad = df_filtrado["RANGO_EDAD"].value_counts()

    fig2, ax2 = plt.subplots()
    conteo_edad.plot(kind="bar", ax=ax2)
    ax2.set_ylabel("Cantidad de Pólizas")
    ax2.set_xlabel("Rango de Edad")
    ax2.set_title("Cantidad de Pólizas por Rango de Edad")
    plt.xticks(rotation=45)

    st.pyplot(fig2)

    # ---------------------------------
    # BOTON DESCARGAR
    # ---------------------------------
    if not df_filtrado.empty:

        output = io.BytesIO()
        df_filtrado.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)

        st.download_button(
            label="📥 Descargar archivo filtrado",
            data=output,
            file_name="resultado_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("Sube un archivo para comenzar.")
