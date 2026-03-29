import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación con Prioridad de Edad y Control PH")

# Mapeo de Unidades PH a Funcionarios Reales
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALAMRALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Columnas
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_unidad = "UNIDAD_TRABAJO"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    try:
        # 1. LECTURA
        df = pd.read_excel(archivo) if not archivo.name.lower().endswith(".xls") else pd.read_excel(archivo, engine="xlrd")
        df.columns = df.columns.str.strip()

        # Limpieza deuda
        df["_deuda_num"] = pd.to_numeric(df[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)

        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

        with tab_filtros:
            st.subheader("⚙️ Controles de Asignación")
            
            # Botón de exclusión PH
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH (No procesar ni asignar trabajo de PH)", value=False)
            
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                ciclos_disp = sorted(df[col_ciclo].dropna().unique().astype(str))
                ciclos_sel = st.multiselect("1. Filtrar Ciclos", ciclos_disp, default=ciclos_disp)
                
                # Técnicos para el reparto general
                nombres_ph = list(mapeo_ph.values())
                tecnicos_reparto = sorted([t for t in df[col_tecnico].dropna().unique() if t not in nombres_ph])
                tecnicos_sel = st.multiselect("2. Técnicos Integrales para Reparto General", tecnicos_reparto, default=tecnicos_reparto)
            
            with c2:
                edades_disp = sorted(df[col_edad].dropna().astype(str).unique())
                # AQUÍ SE DEFINE LA PRIORIDAD
                prioridad_edades = st.multiselect(
                    "3. Prioridad de Edad (Mueve para ordenar importancia):", 
                    edades_disp, 
                    default=edades_disp,
                    help="Las pólizas se asignarán primero a los rangos que pongas arriba."
                )

        # =========================
        # PROCESAMIENTO LÓGICO
        # =========================
        # 1. Filtrar pool por Ciclo y Edad seleccionados
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) & 
            (df[col_edad].astype(str).isin(prioridad_edades))
        ].copy()

        # 2. Aplicar ORDEN DE PRIORIDAD por Edad y Deuda
        # Esto hace que las pólizas "más importantes" queden arriba de todo el archivo
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)
        df_pool = df_pool.sort_values(by=[col_edad, "_deuda_num"], ascending=[True, False])

        # --- SECCIÓN PH ---
        df_ph_final = pd.DataFrame()
        if not excluir_ph:
            df_ph_final_list = []
            for unidad, funcionario in mapeo_ph.items():
                # Buscamos en el pool ya ordenado por edad/deuda
                pool_ph = df_pool[df_pool[col_unidad] == unidad].copy()
                if not pool_ph.empty:
                    # Toma las 50 mejores respetando la prioridad de edad que pusiste arriba
                    asignacion_ph = pool_ph.head(50) 
                    asignacion_ph[col_tecnico] = funcionario
                    df_ph_final_list.append(asignacion_ph)
            
            if df_ph_final_list:
                df_ph_final = pd.concat(df_ph_final_list)

        # --- SECCIÓN REPARTO GENERAL ---
        # Excluimos las unidades PH para que no se mezclen con el reparto general
        df_para_reparto = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys())].copy()
        
        # Re-ordenamos para el reparto general por Edad -> Barrio -> Deuda
        df_para_reparto = df_para_reparto.sort_values(
            by=[col_edad, col_barrio, "_deuda_num"], 
            ascending=[True, True, False]
        )

        lista_final_otros = []
        puntero = 0
        for tec in tecnicos_sel:
            bloque = df_para_reparto.iloc[puntero : puntero + 50].copy()
            if not bloque.empty:
                bloque[col_tecnico] = tec
                lista_final_otros.append(bloque)
                puntero += 50

        # UNIÓN FINAL
        final_list = []
        if not df_ph_final.empty: final_list.append(df_ph_final)
        if lista_final_otros: final_list.extend(lista_final_otros)
        
        if final_list:
            df_resultado = pd.concat(final_list, ignore_index=True)
        else:
            df_resultado = pd.DataFrame()

        # =========================
        # VISTAS
        # =========================
        with tab1:
            if not df_resultado.empty:
                st.success(f"Asignación generada con éxito respeando prioridades.")
                st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="Asignacion_UT_Priorizada.xlsx")
            else:
                st.warning("No hay pólizas que coincidan con los filtros.")

        with tab2:
            if not df_resultado.empty:
                st.subheader("Pólizas Asignadas por Rango de Edad")
                # Gráfico para validar que la prioridad se cumplió
                conteo_prioridad = df_resultado[col_edad].value_counts().reindex(prioridad_edades).reset_index()
                fig_edad = px.bar(conteo_prioridad, x=col_edad, y="count", color=col_edad, title="Cumplimiento de Prioridad")
                st.plotly_chart(fig_edad, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
