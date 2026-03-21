import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Asignación por Bloque de Barrio")

# Sidebar para cargar archivo
archivo = st.sidebar.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

# Nombres de columnas según tus imágenes
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION" # Corregido según imagen
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"

if archivo:
    try:
        # 1. LECTURA DE DATOS
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd") # Requiere xlrd según imagen
        else:
            df = pd.read_excel(archivo, engine="openpyxl") # Requiere openpyxl según imagen

        df.columns = df.columns.str.strip()
        
        # Limpieza de Deuda para cálculos numéricos
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False).str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # Filtros en Sidebar
        ciclos_disp = sorted(df[col_ciclo].astype(str).unique())
        ciclos_sel = st.sidebar.multiselect("Filtrar Ciclos", ciclos_disp, default=ciclos_disp)
        
        todos_tecnicos = sorted(df[col_tecnico].astype(str).unique())
        tecnicos_sel = st.sidebar.multiselect("Técnicos a Procesar", todos_tecnicos, default=todos_tecnicos)

        # Pool de datos filtrados
        df_pool = df[(df[col_ciclo].astype(str).isin(ciclos_sel)) & (df[col_tecnico].isin(tecnicos_sel))].copy()

        # =========================================================
        # LÓGICA DE ASIGNACIÓN: BARRIO AGOTADO POR TÉCNICO
        # =========================================================
        unidades_ph = ["ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH", 
                       "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", "ITA SUSPENSION BQ 37 PH"]
        
        # PH: Lógica tradicional de mayor deuda
        df_ph_final = df_pool[df_pool[col_tecnico].isin(unidades_ph)].sort_values(by="_deuda_num", ascending=False).groupby(col_tecnico).head(50)

        # Otros: Lógica de BLOQUE DE BARRIO para un solo técnico
        df_otros = df_pool[~df_pool[col_tecnico].isin(unidades_ph)].copy()
        df_otros = df_otros.sort_values(by=[col_ciclo, col_barrio, col_direccion])
        
        lista_final_otros = []
        indices_asignados = set()

        for tec in [t for t in tecnicos_sel if t not in unidades_ph]:
            cupo = 50
            acumulado_tec = []
            
            pols_disponibles = df_otros[~df_otros.index.isin(indices_asignados)]
            if pols_disponibles.empty: break

            # Tomar el primer barrio que aparezca en la ruta lógica
            while cupo > 0 and not pols_disponibles.empty:
                barrio_actual = pols_disponibles.iloc[0][col_barrio]
                
                # Intentamos tomar todo el bloque de ese barrio
                bloque_barrio = pols_disponibles[pols_disponibles[col_barrio] == barrio_actual].head(cupo)
                
                acumulado_tec.append(bloque_barrio)
                indices_asignados.update(bloque_barrio.index)
                cupo -= len(bloque_barrio)
                
                pols_disponibles = df_otros[~df_otros.index.isin(indices_asignados)]

            if acumulado_tec:
                df_tec_res = pd.concat(acumulado_tec)
                df_tec_res[col_tecnico] = tec # Asignar el bloque al técnico actual
                lista_final_otros.append(df_tec_res)

        df_resultado = pd.concat([df_ph_final] + lista_final_otros, ignore_index=True)

        # =========================================================
        # TABS Y GRÁFICAS (CON CORRECCIÓN DE ERROR)
        # =========================================================
        tab1, tab2 = st.tabs(["📋 Tabla y Descarga", "📊 Dashboard"])

        with tab1:
            st.success(f"Asignación finalizada: {len(df_resultado)} registros procesados.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
            st.sidebar.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="Asignacion_UT.xlsx")

        with tab2:
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("🏆 Top 10 Técnicos (Deuda)")
                ranking = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                ranking.columns = ["Técnico", "Deuda"]
                ranking["Deuda"] = ranking["Deuda"].apply(lambda x: f"$ {x:,.0f}")
                st.table(ranking)

            with c2:
                # CORRECCIÓN DE ERROR DE GRÁFICA
                st.subheader("📊 Pólizas por Rango de Edad")
                conteo_edad = df_resultado[col_edad].value_counts().reset_index()
                # Renombrar columnas explícitamente para evitar error de 'index'
                conteo_edad.columns = [col_edad, "cantidad"]
                
                fig = px.bar(
                    conteo_edad, 
                    x=col_edad, # Nombre de columna explícito corregido
                    y="cantidad", 
                    color=col_edad,
                    text_auto=True
                )
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error detectado: {e}")
else:
    st.info("👆 Sube un archivo para procesar los bloques de barrios.")
