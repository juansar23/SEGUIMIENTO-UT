import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación Integral UT")

# Mapeo de Unidades PH a Funcionarios Reales
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Nombres de Columnas
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_unidad = "UNIDAD_TRABAJO"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"
col_subcat = "SUBCATEGORIA"

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    try:
        # 1. LECTURA
        df = pd.read_excel(archivo) if not archivo.name.lower().endswith(".xls") else pd.read_excel(archivo, engine="xlrd")
        df.columns = df.columns.str.strip()

        # Limpieza deuda para cálculos
        df["_deuda_num"] = pd.to_numeric(df[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)

        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

        with tab_filtros:
            st.subheader("⚙️ Filtros Globales")
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                ciclos_disp = sorted(df[col_ciclo].dropna().unique().astype(str))
                ciclos_sel = st.multiselect("Filtrar Ciclos", ciclos_disp, default=ciclos_disp)
                
                subcat_disp = sorted(df[col_subcat].dropna().unique().astype(str))
                subcat_sel = st.multiselect("Filtrar Subcategoría", subcat_disp, default=subcat_disp)
            
            with c2:
                edades_disp = sorted(df[col_edad].dropna().astype(str).unique())
                prioridad_edades = st.multiselect("Prioridad de Edad (Mueve para ordenar):", edades_disp, default=edades_disp)
            
            with c3:
                nombres_ph = list(mapeo_ph.values())
                tecnicos_reparto = sorted([t for t in df[col_tecnico].dropna().unique() if t not in nombres_ph])
                tecnicos_sel = st.multiselect("Técnicos para Reparto General", tecnicos_reparto, default=tecnicos_reparto)

        # =========================
        # PROCESAMIENTO
        # =========================
        # Filtrado Base
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) & 
            (df[col_edad].astype(str).isin(prioridad_edades)) &
            (df[col_subcat].astype(str).isin(subcat_sel))
        ].copy()

        # Orden por Prioridad de Edad y Deuda
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)
        df_pool = df_pool.sort_values(by=[col_edad, "_deuda_num"], ascending=[True, False])

        # Lógica PH
        df_ph_final = pd.DataFrame()
        if not excluir_ph:
            list_ph = []
            for unidad, funcionario in mapeo_ph.items():
                pool_ph = df_pool[df_pool[col_unidad] == unidad].copy()
                if not pool_ph.empty:
                    asignacion = pool_ph.head(50)
                    asignacion[col_tecnico] = funcionario
                    list_ph.append(asignacion)
            if list_ph: df_ph_final = pd.concat(list_ph)

        # Reparto General
        df_para_reparto = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys())].copy()
        df_para_reparto = df_para_reparto.sort_values(by=[col_edad, col_barrio, "_deuda_num"], ascending=[True, True, False])

        lista_final_otros = []
        puntero = 0
        for tec in tecnicos_sel:
            bloque = df_para_reparto.iloc[puntero : puntero + 50].copy()
            if not bloque.empty:
                bloque[col_tecnico] = tec
                lista_final_otros.append(bloque)
                puntero += 50

        # Unificación
        final_dfs = []
        if not df_ph_final.empty: final_dfs.append(df_ph_final)
        if lista_final_otros: final_dfs.extend(lista_final_otros)
        df_resultado = pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()

        # =========================
        # VISTAS
        # =========================
        with tab1:
            if not df_resultado.empty:
                st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="Asignacion_Final.xlsx")
            else:
                st.warning("Sin datos.")

        with tab2:
            if not df_resultado.empty:
                col_d1, col_d2 = st.columns(2)
                
                with col_d1:
                    st.subheader("🏆 Top 10 Técnicos (Deuda)")
                    ranking = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                    ranking.columns = ["Técnico", "Deuda Asignada"]
                    st.table(ranking.style.format({"Deuda Asignada": "$ {:,.0f}"}))

                with col_d2:
                    st.subheader("🥧 Distribución por Subcategoría")
                    fig_pie = px.pie(df_resultado, names=col_subcat, hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)

                st.divider()
                st.subheader("📊 Pólizas por Rango de Edad")
                conteo_edad = df_resultado[col_edad].value_counts().reindex(prioridad_edades).reset_index()
                st.plotly_chart(px.bar(conteo_edad, x=col_edad, y="count", color=col_edad), use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
