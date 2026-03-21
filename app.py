import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación por Bloque de Barrio")

archivo = st.sidebar.file_uploader("Sube el archivo (.xls, .xlsx)", type=["xls", "xlsx", "xlsm", "xlsb"])

# Configuración de columnas según tus capturas
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"

if archivo:
    try:
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()
        
        # Limpieza de deuda para el Top 10
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False).str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # Filtros Sidebar
        ciclos_disp = sorted(df[col_ciclo].astype(str).unique())
        ciclos_sel = st.sidebar.multiselect("Ciclos", ciclos_disp, default=ciclos_disp)
        
        todos_tecnicos = sorted(df[col_tecnico].astype(str).unique())
        tecnicos_sel = st.sidebar.multiselect("Técnicos a Procesar", todos_tecnicos, default=todos_tecnicos)

        # Dataset Filtrado
        df_pool = df[(df[col_ciclo].astype(str).isin(ciclos_sel)) & (df[col_tecnico].isin(tecnicos_sel))].copy()

        # =========================================================
        # NUEVA LÓGICA: ASIGNACIÓN PRIORITARIA POR BARRIO (BLOQUE)
        # =========================================================
        # 1. Separar PH (Lógica de Deuda)
        unidades_ph = ["ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH", 
                       "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", "ITA SUSPENSION BQ 37 PH"]
        
        df_ph_final = df_pool[df_pool[col_tecnico].isin(unidades_ph)].sort_values(by="_deuda_num", ascending=False).groupby(col_tecnico).head(50)

        # 2. Otros (Lógica de Concentración Geográfica Total)
        df_otros = df_pool[~df_pool[col_tecnico].isin(unidades_ph)].copy()
        
        # Ordenamos todo el pool por Ciclo y Barrio para que los bloques estén juntos
        df_otros = df_otros.sort_values(by=[col_ciclo, col_barrio, col_direccion])
        
        lista_final_otros = []
        pols_asignadas_indices = set()

        for tec in [t for t in tecnicos_sel if t not in unidades_ph]:
            cupo_restante = 50
            acumulado_tec = []
            
            # Buscamos el barrio más frecuente que aún tenga pólizas para este técnico
            # o seguimos el orden de ruta lógica para no saltar por toda la ciudad
            pols_disponibles = df_otros[~df_otros.index.isin(pols_asignadas_indices)]
            
            if pols_disponibles.empty:
                continue

            # Tomamos el primer barrio disponible en la ruta lógica
            barrio_actual = pols_disponibles.iloc[0][col_barrio]
            
            while cupo_restante > 0:
                # Intentamos tomar TODAS las del barrio actual para este técnico
                pols_del_barrio = pols_disponibles[pols_disponibles[col_barrio] == barrio_actual].head(cupo_restante)
                
                if not pols_del_barrio.empty:
                    acumulado_tec.append(pols_del_barrio)
                    pols_asignadas_indices.update(pols_del_barrio.index)
                    cupo_restante -= len(pols_del_barrio)
                    
                    # Actualizar disponibles para el siguiente ciclo del while
                    pols_disponibles = df_otros[~df_otros.index.isin(pols_asignadas_indices)]
                
                if pols_disponibles.empty or cupo_restante <= 0:
                    break
                
                # Si aún queda cupo, saltamos al SIGUIENTE barrio disponible en la lista ordenada
                barrio_actual = pols_disponibles.iloc[0][col_barrio]

            if acumulado_tec:
                df_tec_final = pd.concat(acumulado_tec)
                df_tec_final[col_tecnico] = tec # Re-asignamos al técnico actual
                lista_final_otros.append(df_tec_final)

        df_resultado = pd.concat([df_ph_final] + lista_final_otros, ignore_index=True)

        # =========================================================
        # VISUALIZACIÓN
        # =========================================================
        tab1, tab2 = st.tabs(["📋 Tabla y Descarga", "📊 Dashboard"])

        with tab1:
            st.success(f"Asignación completada. Barrios como '{barrio_actual}' se han mantenido agrupados.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
            st.sidebar.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="Asignacion_UT.xlsx")

        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🏆 Top 10 Técnicos (Deuda Total)")
                ranking = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                ranking.columns = ["Técnico", "Deuda"]
                ranking["Deuda"] = ranking["Deuda"].apply(lambda x: f"$ {x:,.0f}")
                st.table(ranking)
            with c2:
                st.subheader("📊 Pólizas por Rango de Edad")
                fig = px.bar(df_resultado["RANGO_EDAD"].value_counts().reset_index(), x="index", y="RANGO_EDAD")
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
