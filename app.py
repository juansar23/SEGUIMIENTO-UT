import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización por Barrio")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

# --- CONFIGURACIÓN DE COLUMNAS ---
col_barrio = "BARRIO" # <--- Asegúrate que este sea el nombre exacto en tu Excel

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()
    
    # Limpieza de datos
    df["TECNICOS_INTEGRALES"] = df["TECNICOS_INTEGRALES"].astype(str).str.strip()
    if col_barrio in df.columns:
        df[col_barrio] = df[col_barrio].astype(str).str.strip()

    # Limpieza de deuda (necesaria para priorizar dentro de los barrios)
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False).str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # DEFINICIÓN DE GRUPOS (IMAGEN)
    # ================================
    unidades_ita_imagen = [
        "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
        "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
        "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", 
        "ITA SUSPENSION BQ 37 PH"
    ]

    # --- LÓGICA 1: ITA IMAGEN (MAYOR DEUDA PURA) ---
    df_ita = df[df["TECNICOS_INTEGRALES"].isin(unidades_ita_imagen)].copy()
    df_ita_final = (
        df_ita.sort_values(by="_deuda_num", ascending=False)
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
    )

    # --- LÓGICA 2: DEMÁS UNIDADES (CONCENTRACIÓN POR BARRIOS EN CASCADA) ---
    df_otros_base = df[~df["TECNICOS_INTEGRALES"].isin(unidades_ita_imagen)].copy()
    
    lista_otros_procesados = []

    for tecnico, grupo in df_otros_base.groupby("TECNICOS_INTEGRALES"):
        if col_barrio in grupo.columns:
            # 1. Contar cuántas pólizas hay por barrio para este técnico y ordenarlos de mayor a menor
            conteo_barrios = grupo[col_barrio].value_counts().index.tolist()
            
            pólizas_tecnico = []
            contador = 0
            
            # 2. Ir barrio por barrio hasta completar 50
            for barrio in conteo_barrios:
                if contador >= 50:
                    break
                
                espacio_disponible = 50 - contador
                df_este_barrio = grupo[grupo[col_barrio] == barrio].copy()
                
                # Priorizar por deuda dentro del mismo barrio
                df_este_barrio = df_este_barrio.sort_values(by="_deuda_num", ascending=False).head(espacio_disponible)
                
                pólizas_tecnico.append(df_este_barrio)
                contador += len(df_este_barrio)
            
            if pólizas_tecnico:
                lista_otros_procesados.append(pd.concat(pólizas_tecnico))
        else:
            # Si no hay columna barrio, lógica normal de deuda
            lista_otros_procesados.append(grupo.sort_values(by="_deuda_num", ascending=False).head(50))

    df_otros_final = pd.concat(lista_otros_procesados) if lista_otros_procesados else pd.DataFrame()

    # ================================
    # RESULTADOS Y DESCARGA
    # ================================
    df_total = pd.concat([df_ita_final, df_otros_final], ignore_index=True)

    st.divider()
    st.success(f"✅ Procesamiento finalizado. Total pólizas asignadas: {len(df_total)}")

    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        st.info(f"📍 Unidades con Lógica Barrio: {df_otros_final['TECNICOS_INTEGRALES'].nunique()}")
        st.dataframe(df_otros_final[["TECNICOS_INTEGRALES", col_barrio, "DEUDA_TOTAL"]].head(10), use_container_width=True)

    with col_btn2:
        st.info(f"💰 Unidades con Lógica Deuda (ITA): {df_ita_final['TECNICOS_INTEGRALES'].nunique()}")
        st.dataframe(df_ita_final[["TECNICOS_INTEGRALES", "DEUDA_TOTAL"]].head(10), use_container_width=True)

    # --- EXPORTAR A EXCEL ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_total.drop(columns=["_deuda_num"], errors="ignore").to_excel(writer, index=False, sheet_name="Reporte_Final")
    
    st.download_button(
        label="📥 Descargar Reporte Optimizado",
        data=output.getvalue(),
        file_name="reporte_unidades_trabajo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👋 Por favor, sube el archivo Excel para aplicar las reglas de barrio e ITA.")
