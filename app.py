import streamlit as st
import pandas as pd
import io

# Configuración de la página
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización Logística")
st.markdown("---")

# 1. CARGADOR DE ARCHIVOS (Configurado para mostrar .xls y .xlsx)
archivo = st.file_uploader(
    "Selecciona tu archivo de Seguimiento (Formato .xls o .xlsx)", 
    type=["xls", "xlsx"]
)

# Nombre de la columna del barrio (Ajustar si es diferente en tu Excel)
col_barrio = "BARRIO" 

if archivo:
    try:
        # Detectar motor según extensión
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        # Limpieza inicial de nombres de columnas
        df.columns = df.columns.str.strip()
        
        # Validar columnas necesarias
        cols_necesarias = ["TECNICOS_INTEGRALES", "DEUDA_TOTAL", col_barrio]
        for c in cols_necesarias:
            if c not in df.columns:
                st.error(f"❌ No se encontró la columna: {c}")
                st.stop()

        # Estandarizar datos
        df["TECNICOS_INTEGRALES"] = df["TECNICOS_INTEGRALES"].astype(str).str.strip()
        df[col_barrio] = df[col_barrio].astype(str).str.strip()

        # Limpiar Deuda para cálculos numéricos
        df["_deuda_num"] = (
            df["DEUDA_TOTAL"].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # ==========================================
        # DEFINICIÓN DE GRUPOS (Lógica Diferenciada)
        # ==========================================
        unidades_ita_ph = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
            "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
            "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", 
            "ITA SUSPENSION BQ 37 PH"
        ]

        # --- LÓGICA 1: Unidades PH (Imagen) -> Top 50 Deuda Pura ---
        df_ita = df[df["TECNICOS_INTEGRALES"].isin(unidades_ita_ph)].copy()
        df_ita_final = (
            df_ita.sort_values(by="_deuda_num", ascending=False)
            .groupby("TECNICOS_INTEGRALES")
            .head(50)
        )

        # --- LÓGICA 2: Demás Unidades -> Barrios en Cascada ---
        df_otros_base = df[~df["TECNICOS_INTEGRALES"].isin(unidades_ita_ph)].copy()
        lista_otros_procesados = []

        for tecnico, grupo in df_otros_base.groupby("TECNICOS_INTEGRALES"):
            # Ordenar barrios donde el técnico tiene más pólizas
            conteo_barrios = grupo[col_barrio].value_counts().index.tolist()
            
            pólizas_tecnico = []
            contador = 0
            
            # Ir sumando barrios hasta llegar a 50
            for barrio in conteo_barrios:
                if contador >= 50:
                    break
                
                espacio_libre = 50 - contador
                df_este_barrio = grupo[grupo[col_barrio] == barrio].copy()
                
                # Dentro del mismo barrio, priorizamos las de mayor deuda
                df_este_barrio_top = df_este_barrio.sort_values(by="_deuda_num", ascending=False).head(espacio_libre)
                
                pólizas_tecnico.append(df_este_barrio_top)
                contador += len(df_este_barrio_top)
            
            if pólizas_tecnico:
                lista_otros_procesados.append(pd.concat(pólizas_tecnico))

        df_otros_final = pd.concat(lista_otros_procesados) if lista_otros_procesados else pd.DataFrame()

        # Unificar ambos resultados
        df_resultado = pd.concat([df_ita_final, df_otros_final], ignore_index=True)

        # ================================
        # INTERFAZ Y DESCARGA
        # ================================
        st.success(f"✅ Proceso exitoso: Se asignaron {len(df_resultado)} pólizas en total.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Unidades ITA (PH)", df_ita_final["TECNICOS_INTEGRALES"].nunique())
        c2.metric("Otras Unidades", df_otros_final["TECNICOS_INTEGRALES"].nunique())
        c3.metric("Total Pólizas", len(df_resultado))

        st.dataframe(df_resultado.drop(columns=["_deuda_num"], errors="ignore"), use_container_width=True)

        # Preparar archivo de salida
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Quitamos la columna auxiliar de deuda antes de exportar
            df_export = df_resultado.drop(columns=["_deuda_num"], errors="ignore")
            df_export.to_excel(writer, index=False, sheet_name="Reporte_Optimizado")
        
        st.download_button(
            label="📥 Descargar Reporte Final Optimizado",
            data=output.getvalue(),
            file_name="Resultado_Seguimiento_Optimizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
        st.info("Asegúrate de haber instalado 'xlrd' para leer archivos .xls antiguos.")

else:
    st.info("👆 Por favor, sube el archivo de Seguimiento para comenzar. El sistema detectará automáticamente los barrios y las unidades especiales.")
