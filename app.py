import streamlit as st
import pandas as pd
import io
from openpyxl.styles import numbers

# ----------------------------
# CONFIGURACION PAGINA
# ----------------------------
st.set_page_config(page_title="Seguimiento UT", layout="wide")
st.title("📊 Seguimiento Unidad de Trabajo")

# ----------------------------
# MENU RANGO EDAD
# ----------------------------
opciones_rango = [
    "0 - 30",
    "31 - 60",
    "61 - 90",
    "91 - 120",
    "121 - 360",
    "361 - 1080",
    "> 1080"
]

rangos_validos = st.multiselect(
    "Seleccione uno o varios rangos de edad:",
    opciones_rango,
    default=["0 - 30", "31 - 60", "61 - 90"]
)

# ----------------------------
# SUBIR ARCHIVO
# ----------------------------
archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo and rangos_validos:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ----------------------------
    # VALIDAR COLUMNAS NECESARIAS
    # ----------------------------
    columnas_necesarias = [
        "TECNICOS INTEGRALES",
        "RANGO_EDAD",
        "CRUCE",
        "DEUDA TOTAL",
        "Unidad de trabajo"
    ]

    faltantes = [col for col in columnas_necesarias if col not in df.columns]

    if faltantes:
        st.error(f"❌ El archivo no contiene las columnas: {faltantes}")
        st.stop()

    # ----------------------------
    # FORMATEAR COLUMNAS FECHA
    # ----------------------------
    columnas_fecha = [
        "FECHA_VENCIMIENTO",
        "ULT_FECHA_PAGO",
        "FECHA DE ASIGNACION"
    ]

    for col in columnas_fecha:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # ----------------------------
    # FORMATEAR COLUMNAS MONEDA
    # ----------------------------
    columnas_moneda = [
        "VALOR_ULTIMA_FACTURA",
        "ULT_PAGO",
        "DEUDA TOTAL"
    ]

    for col in columnas_moneda:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ----------------------------
    # LIMPIAR TECNICOS
    # ----------------------------
    df["TECNICOS INTEGRALES"] = (
        df["TECNICOS INTEGRALES"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )

    # ----------------------------
    # FILTROS
    # ----------------------------
    df = df[df["RANGO_EDAD"].isin(rangos_validos)]
    df = df[df["CRUCE"].isna()]

    # ----------------------------
    # ORDENAR POR MAYOR DEUDA
    # ----------------------------
    df = df.sort_values(by="DEUDA TOTAL", ascending=False)

    # ----------------------------
    # MAXIMO 50 POR UNIDAD
    # ----------------------------
    df_final = (
        df.groupby("Unidad de trabajo")
        .head(50)
        .reset_index(drop=True)
    )

    # ----------------------------
    # MOSTRAR RESULTADO FORMATEADO
    # ----------------------------
    st.success("✅ Archivo procesado correctamente")

    formato_monedas = {
        "VALOR_ULTIMA_FACTURA": "${:,.0f}",
        "ULT_PAGO": "${:,.0f}",
        "DEUDA TOTAL": "${:,.0f}"
    }

    columnas_formato = {k: v for k, v in formato_monedas.items() if k in df_final.columns}

    st.dataframe(
        df_final.style.format(columnas_formato),
        use_container_width=True
    )

    # ----------------------------
    # EXPORTAR A EXCEL CON FORMATO
    # ----------------------------
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Resultado")

        workbook = writer.book
        worksheet = writer.sheets["Resultado"]

        # Formato moneda real en Excel
        for col in columnas_moneda:
            if col in df_final.columns:
                col_idx = df_final.columns.get_loc(col) + 1
                for row in range(2, len(df_final) + 2):
                    worksheet.cell(row=row, column=col_idx).number_format = '"$"#,##0'

        # Formato fecha corta en Excel
        for col in columnas_fecha:
            if col in df_final.columns:
                col_idx = df_final.columns.get_loc(col) + 1
                for row in range(2, len(df_final) + 2):
                    worksheet.cell(row=row, column=col_idx).number_format = 'DD/MM/YYYY'

    buffer.seek(0)

    st.download_button(
        label="📥 Descargar archivo procesado",
        data=buffer,
        file_name="resultado_filtrado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

elif archivo and not rangos_validos:
    st.warning("⚠️ Debes seleccionar al menos un rango.")
