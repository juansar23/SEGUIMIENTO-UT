import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización Logística")

# Configuración para aceptar ambos formatos
archivo = st.file_uploader("Sube el archivo Excel (97-2003 o Moderno)", type=["xls", "xlsx"])

col_barrio = "BARRIO"  # Asegúrate de que este nombre sea igual en tu Excel

if archivo:
    try:
        # LÓGICA DE CARGA SEGÚN EL FORMATO
        if archivo.name.endswith(".xls"):
            # Para archivos Libro de Excel 97-2003
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            # Para archivos .xlsx modernos
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()
        
        # Limpieza rápida de columnas clave
        df["TECNICOS_INTEGRALES"] = df["TECNICOS_INTEGRALES"].astype(str).str.strip()
        if col_barrio in df.columns:
            df[col_barrio] = df[col_barrio].astype(str).str.strip()

        # Limpiar deuda para cálculos
        df["_deuda_num"] = (
            df["DEUDA_TOTAL"].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # ==========================================
        # SEGMENTACIÓN DE UNIDADES
        # ==========================================
        unidades_ita_imagen = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
            "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
            "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", 
            "ITA SUSPENSION BQ 37 PH"
        ]

        # 1. Lógica ITA (Imagen): Top 50 Deuda Pura
        df_ita = df[df["TECNICOS_INTEGRALES"].isin(unidades_ita_imagen)].copy()
        df_ita_final = (
            df_ita.sort_values(by="_deuda_num", ascending=False)
            .groupby("TECNICOS_INTEGRALES")
            .head(50)
        )

        # 2. Lógica Otros: Barrios en Cascada
        df_otros_base = df[~df["TECNICOS_INTEGRALES"].isin(unidades_ita_imagen)].copy()
        lista_otros_procesados = []

        for tecnico, grupo in df_otros_base.groupby("TECNICOS_INTEGRALES"):
            if col_barrio in grupo.columns:
                conteo_barrios = grupo[col_barrio].value_counts().index.tolist()
                pólizas_tecnico = []
                contador = 0
                
                for barrio in conteo_barrios:
                    if contador >= 50: break
                    
                    espacio_cupo = 50 - contador
                    df_barrio = grupo[grupo[col_barrio] == barrio].copy()
                    # Dentro del barrio, priorizamos deuda
                    df_barrio_top = df_barrio.sort_values(by="_deuda_num", ascending=False).head(espacio_cupo)
                    
                    pólizas_tecnico.append(df_barrio_top)
                    contador += len(df_barrio_top)
                
                if pólizas_tecnico:
                    lista_otros_procesados.append(pd.concat(pólizas_tecnico))
            else:
                lista_otros_procesados.append(grupo.sort_values(by="_deuda_num", ascending=False).head(50))

        df_otros_final = pd.concat(lista_otros_procesados) if lista_otros_procesados else pd.DataFrame()

        # Unir ambos universos
        df_total = pd.concat([df_ita_final, df_otros_final], ignore_index=True)

        # --- MOSTRAR RESULTADOS ---
        st.success(f"✅ Archivo '{archivo.name}' procesado con éxito.")
        
        col1, col2 = st.columns(2)
        col1.metric("Pólizas ITA (Deuda)", len(df_ita_final))
        col2.metric("Pólizas Otros (Barrios)", len(df_otros_final))

        st.dataframe(df_total.drop(columns=["_deuda_num"], errors="ignore"), use_container_width=True)

        # --- BOTÓN DE DESCARGA ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_total.drop(columns=["_deuda_num"], errors="ignore").to_excel(writer, index=False, sheet_name="Reporte_Final")
        
        st.download_button(
            label="📥 Descargar Reporte Final (.xlsx)",
            data=output.getvalue(),
            file_name="reporte_asignacion_optimo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        st.info("Asegúrate de que el archivo no esté protegido con contraseña o dañado.")

else:
    st.info("👆 Sube tu archivo .xls (97-2003) para procesar las unidades de trabajo.")
