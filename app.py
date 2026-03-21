import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización por Barrio")

# --- CAMBIO AQUÍ: Aceptar xls y xlsx ---
archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx", "xls"])

col_barrio = "BARRIO" # Asegúrate que sea el nombre exacto en tu Excel

if archivo:
    # Determinamos el motor según la extensión
    if archivo.name.endswith(".xls"):
        df = pd.read_excel(archivo, engine="xlrd")
    else:
        df = pd.read_excel(archivo, engine="openpyxl")

    df.columns = df.columns.str.strip()
    
    # Limpieza de datos
    df["TECNICOS_INTEGRALES"] = df["TECNICOS_INTEGRALES"].astype(str).str.strip()
    if col_barrio in df.columns:
        df[col_barrio] = df[col_barrio].astype(str).str.strip()

    # Limpieza de deuda
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False).str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # SEGMENTACIÓN DE GRUPOS
    # ================================
    unidades_ita_imagen = [
        "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
        "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
        "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", 
        "ITA SUSPENSION BQ 37 PH"
    ]

    # --- LÓGICA 1: ITA IMAGEN (MAYOR DEUDA) ---
    df_ita = df[df["TECNICOS_INTEGRALES"].isin(unidades_ita_imagen)].copy()
    df_ita_final = (
        df_ita.sort_values(by="_deuda_num", ascending=False)
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
    )

    # --- LÓGICA 2: OTROS (BARRIOS EN CASCADA) ---
    df_otros_base = df[~df["TECNICOS_INTEGRALES"].isin(unidades_ita_imagen)].copy()
    lista_otros_procesados = []

    for tecnico, grupo in df_otros_base.groupby("TECNICOS_INTEGRALES"):
        if col_barrio in grupo.columns:
            # Ordenar barrios por frecuencia
            conteo_barrios = grupo[col_barrio].value_counts().index.tolist()
            pólizas_tecnico = []
            contador = 0
            
            for barrio in conteo_barrios:
                if contador >= 50: break
                
                espacio = 50 - contador
                df_barrio = grupo[grupo[col_barrio] == barrio].copy()
                df_barrio_top = df_barrio.sort_values(by="_deuda_num", ascending=False).head(espacio)
                
                pólizas_tecnico.append(df_barrio_top)
                contador += len(df_barrio_top)
            
            if pólizas_tecnico:
                lista_otros_procesados.append(pd.concat(pólizas_tecnico))
        else:
            lista_otros_procesados.append(grupo.sort_values(by="_deuda_num", ascending=False).head(50))

    df_otros_final = pd.concat(lista_otros_procesados) if lista_otros_procesados else pd.DataFrame()

    # Unificación final
    df_total = pd.concat([df_ita_final, df_otros_final], ignore_index=True)

    # --- INTERFAZ ---
    st.success(f"✅ Archivo procesado correctamente ({len(df_total)} pólizas)")
    
    st.dataframe(df_total.drop(columns=["_deuda_num"], errors="ignore"), use_container_width=True)

    # --- DESCARGA ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_total.drop(columns=["_deuda_num"], errors="ignore").to_excel(writer, index=False, sheet_name="Reporte")
    
    st.download_button(
        "📥 Descargar Reporte Final",
        data=output.getvalue(),
        file_name="reporte_optimizado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👋 Sube un archivo (.xls o .xlsx) para comenzar.")
