import streamlit as st
import pandas as pd
import io

# ----------------------------
# CONFIGURACION PAGINA
# ----------------------------
st.set_page_config(page_title="Seguimiento UT", layout="wide")

st.title("📊 Seguimiento Unidad de Trabajo")

# ----------------------------
# 1. MENU MULTIPLE RANGO EDAD
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
    default=["0 - 30", "31 - 60", "61 - 90"]  # igual que tu script original
)

# ----------------------------
# 2. LEER ARCHIVO (ANTES ERA RUTA FIJA)
# ----------------------------
archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo and rangos_validos:

    df = pd.read_excel(archivo)

    # ----------------------------
    # 3. LIMPIAR NOMBRES DE COLUMNAS
    # ----------------------------
    df.columns = df.columns.str.strip()

    # ----------------------------
    # 4. LIMPIAR NOMBRES DE TECNICOS
    # ----------------------------
    df["TECNICOS INTEGRALES"] = (
        df["TECNICOS INTEGRALES"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )

    # ----------------------------
    # 5. FILTRAR POR RANGO DE EDAD
    # ----------------------------
    df = df[df["RANGO_EDAD"].isin(rangos_validos)]

    # ----------------------------
    # 6. EXCLUIR LOS QUE TENGAN VALOR EN CRUCE
    # ----------------------------
    df = df[df["CRUCE"].isna()]

    # ----------------------------
    # 7. COLUMNA AUXILIAR PARA ORDENAR POR DEUDA
    # ----------------------------
    df["_deuda_num"] = (
        df["DEUDA TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("-", "0", regex=False)
        .str.strip()
    )

    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ----------------------------
    # 8. ORDENAR POR MAYOR DEUDA
    # ----------------------------
    df = df.sort_values(by="_deuda_num", ascending=False)

    # ----------------------------
    # 9. TOMAR MAXIMO 50 POR UNIDAD OPERATIVA
    # ----------------------------
    df_final = (
        df.groupby("Unidad de trabajo")
        .head(50)
        .reset_index(drop=True)
    )

    # Eliminar columna auxiliar
    df_final = df_final.drop(columns=["_deuda_num"])

    # ----------------------------
    # MOSTRAR RESULTADO
    # ----------------------------
    st.success("✅ Archivo procesado correctamente")
    st.dataframe(df_final, use_container_width=True)

    # ----------------------------
    # 10. DESCARGAR EXCEL (REEMPLAZA TKINTER)
    # ----------------------------
    buffer = io.BytesIO()
    df_final.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        label="📥 Descargar archivo procesado",
        data=buffer,
        file_name="resultado_filtrado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

elif archivo and not rangos_validos:
    st.warning("⚠️ Debes seleccionar al menos un rango.")
