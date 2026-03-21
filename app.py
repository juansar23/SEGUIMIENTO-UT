import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Dashboard UT", layout="wide")

st.title("📊 Procesador de Unidades de Trabajo")

# TRUCO: Quitamos el parámetro 'type' para que Windows muestre TODOS los archivos
# Así verás tus archivos .xls sin problemas en la ventana de búsqueda
archivo = st.file_uploader("Selecciona tu archivo de Seguimiento")

col_barrio = "BARRIO" 

if archivo:
    try:
        # Validamos el formato internamente después de subirlo
        nombre = archivo.name.lower()
        if nombre.endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        elif nombre.endswith(".xlsx") or nombre.endswith(".xlsm"):
            df = pd.read_excel(archivo, engine="openpyxl")
        else:
            st.error("❌ Por favor sube un archivo de Excel válido (.xls o .xlsx)")
            st.stop()

        st.success(f"✅ Cargado: {archivo.name}")

        # --- PROCESAMIENTO ---
        df.columns = df.columns.str.strip()
        df["TECNICOS_INTEGRALES"] = df["TECNICOS_INTEGRALES"].astype(str).str.strip()
        
        # Limpieza de Deuda
        df["_deuda_num"] = (
            df["DEUDA_TOTAL"].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # Unidades PH de la imagen
        unidades_ph = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
            "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
            "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", 
            "ITA SUSPENSION BQ 37 PH"
        ]

        # Lógica 1: PH (Top Deuda)
        df_ph = df[df["TECNICOS_INTEGRALES"].isin(unidades_ph)].copy()
        df_ph_final = df_ph.sort_values(by="_deuda_num", ascending=False).groupby("TECNICOS_INTEGRALES").head(50)

        # Lógica 2: Otros (Barrios Cascada)
        df_otros = df[~df["TECNICOS_INTEGRALES"].isin(unidades_ph)].copy()
        final_otros = []
        
        for tec, grupo in df_otros.groupby("TECNICOS_INTEGRALES"):
            if col_barrio in grupo.columns:
                grupo[col_barrio] = grupo[col_barrio].astype(str).str.strip()
                orden_barrios = grupo[col_barrio].value_counts().index.tolist()
                acumulado = []
                count = 0
                for b in orden_barrios:
                    if count >= 50: break
                    df_b = grupo[grupo[col_barrio] == b].sort_values(by="_deuda_num", ascending=False).head(50 - count)
                    acumulado.append(df_b)
                    count += len(df_b)
                if acumulado: final_otros.append(pd.concat(acumulado))
            else:
                final_otros.append(grupo.sort_values(by="_deuda_num", ascending=False).head(50))

        df_final_otros = pd.concat(final_otros) if final_otros else pd.DataFrame()
        df_resultado = pd.concat([df_ph_final, df_final_otros], ignore_index=True)

        st.dataframe(df_resultado.drop(columns=["_deuda_num"], errors="ignore"), use_container_width=True)

        # Botón de Descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_resultado.drop(columns=["_deuda_num"], errors="ignore").to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Reporte Final", data=output.getvalue(), file_name="Reporte_Asignacion.xlsx")

    except Exception as e:
        st.error(f"Error técnico: {e}")

else:
    st.info("💡 Tip: Si el archivo sigue sin aparecer, en la ventana de Windows cambia 'Archivos personalizados' a 'Todos los archivos (*.*)'")
