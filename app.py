import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Filtro Dinámico", layout="wide")

st.title("📊 Filtro por Rango de Edad y Subcategoría")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)

    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()

    # -----------------------------
    # DETECTAR COLUMNA SUBCATEGORIA
    # -----------------------------
    columnas_normalizadas = {col.lower(): col for col in df.columns}

    if "subcategoría" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoría"]
    elif "subcategoria" in columnas_normalizadas:
        col_sub = columnas_normalizadas["subcategoria"]
    else:
        st.error("❌ No existe columna Subcategoría en el archivo")
        st.write("Columnas detectadas:", df.columns.tolist())
        st.stop()

    # -----------------------------
    # VALIDAR RANGO EDAD
    # -----------------------------
    if "RANGO_EDAD" not in df.columns:
        st.error("❌ No existe columna RANGO_EDAD")
        st.stop()

    # -----------------------------
    # FILTRO RANGO EDAD
    # -----------------------------
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

    # -----------------------------
    # FILTRO SUBCATEGORIA
    # -----------------------------
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

    # -----------------------------
    # APLICAR FILTROS
    # -----------------------------
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_seleccionados)) &
        (df[col_sub].astype(str).isin(subcategorias_seleccionadas))
    ].copy()

    st.write("### Resultado filtrado")
    st.dataframe(df_filtrado, use_container_width=True)

    # -----------------------------
    # PREPARAR DESCARGA EXCEL
    # -----------------------------
    if not df_filtrado.empty:

        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name='Filtrado')

            workbook = writer.book
            worksheet = writer.sheets['Filtrado']

            formato_fecha = workbook.add_format({'num_format': 'dd/mm/yyyy'})
            formato_moneda = workbook.add_format({'num_format': '$#,##0'})

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

            for idx, col in enumerate(df_filtrado.columns):
                if col in columnas_fecha:
                    worksheet.set_column(idx, idx, 15, formato_fecha)
                if col in columnas_moneda:
                    worksheet.set_column(idx, idx, 18, formato_moneda)

        output.seek(0)

        st.download_button(
            label="📥 Descargar archivo filtrado",
            data=output,
            file_name="resultado_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.warning("⚠ No hay datos con los filtros seleccionados")
