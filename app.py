import streamlit as st
import pandas as pd

st.set_page_config(page_title="Filtro Dinámico", layout="wide")

st.title("📊 Filtro por Rango de Edad y Subcategoría")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)

    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()

    # Normalizar nombre Subcategoría (con o sin tilde)
    columnas_normalizadas = {col.lower(): col for col in df.columns}

    if "subcategoría" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoría"]
    elif "subcategoria" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoria"]
    else:
        st.error("❌ No existe columna Subcategoría en el archivo")
        st.write("Columnas detectadas:", df.columns.tolist())
        st.stop()

    # -----------------------
    # FILTRO RANGO EDAD
    # -----------------------
    if "RANGO_EDAD" not in df.columns:
        st.error("❌ No existe columna RANGO_EDAD")
        st.stop()

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

    # -----------------------
    # FILTRO SUBCATEGORIA
    # -----------------------
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

    # -----------------------
    # APLICAR FILTROS
    # -----------------------
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_seleccionados)) &
        (df[col_sub].astype(str).isin(subcategorias_seleccionadas))
    ]

    st.write("### Resultado filtrado")
    st.dataframe(df_filtrado)

    # -----------------------
    # FORMATO DE COLUMNAS
    # -----------------------
    columnas_fecha = [
        "FECHA_VENCIMIENTO",
        "ULT_FECHA_PAGO",
        "FECHA DE ASIGNACION"
    ]

    columnas_moneda = [
        "VALOR_ULTIMA_FACTURA",
        "ULT_PAGO",
        "DEUDA TOTAL"
    ]

    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    for col in columnas_moneda:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_numeric(df_filtrado[col], errors="coerce")

    st.write("### Datos con formato aplicado")
    st.dataframe(df_filtrado)

