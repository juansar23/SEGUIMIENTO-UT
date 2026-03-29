import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación con Mapeo Estricto PH")

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
col_subcat = "SUBCATEGORIA"

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    try:
        # 1. Lectura
        df = pd.read_excel(archivo) if not archivo.name.lower().endswith(".xls") else pd.read_excel(archivo, engine="xlrd")
        df.columns = df.columns.str.strip()

        # Limpieza deuda
        df["_deuda_num"] = pd.to_numeric(df[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)

        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

        with tab_filtros:
            st.subheader("⚙️ Configuración de Reparto")
            c1, c2 = st.columns(2)
            with c1:
                ciclos_sel = st.multiselect("Filtrar Ciclos", sorted(df[col_ciclo].dropna().unique()), default=df[col_ciclo].dropna().unique())
                # Excluimos nombres de PH del reparto general
                tecnicos_reparto = sorted([t for t in df[col_tecnico].dropna().unique() if t not in mapeo_ph.values()])
                tecnicos_sel = st.multiselect("Técnicos Integrales para Reparto General", tecnicos_reparto, default=tecnicos_reparto)
            with c2:
                edades_disp = sorted(df[col_edad].dropna().astype(str).unique())
                prioridad_edades = st.multiselect("Prioridad de Edad (Arrastra para ordenar):", edades_disp, default=edades_disp)

        # =========================
        # PROCESAMIENTO
        # =========================
        df_pool = df[(df[col_ciclo].astype(str).isin(ciclos_sel)) & (df[col_edad].astype(str).isin(prioridad_edades))].copy()

        # 1. ASIGNACIÓN PH (BLOQUEADA)
        # Solo tomamos pólizas cuya UNIDAD_TRABAJO sea una de las PH
        df_ph_final_list = []
        for unidad, funcionario in mapeo_ph.items():
            # Filtramos solo lo que le corresponde a esa unidad
            pool_ph = df_pool[df_pool[col_unidad] == unidad].copy()
            if not pool_ph.empty:
                # Top 50 por deuda de SU PROPIA UNIDAD
                asignacion_ph = pool_ph.sort_values("_deuda_num", ascending=False).head(50)
                asignacion_ph[col_tecnico] = funcionario
                df_ph_final_list.append(asignacion_ph)

        df_ph_final = pd.concat(df_ph_final_list) if df_ph_final_list else pd.DataFrame()

        # 2. REPARTO GENERAL (PARA EL RESTO)
        # Importante: Excluimos TODA la carga que pertenezca a unidades PH
        df_para_reparto = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys())].copy()
        
        # Ordenar por tu prioridad de edad
        df_para_reparto[col_edad] = pd.Categorical(df_para_reparto[col_edad], categories=prioridad_edades, ordered=True)
        df_para_reparto = df_para_reparto.sort_values(by=[col_edad, col_barrio, "_deuda_num"], ascending=[True, True, False])

        lista_final_otros = []
        puntero = 0
        for tec in tecnicos_sel:
            bloque = df_para_reparto.iloc[puntero : puntero + 50].copy()
            if not bloque.empty:
                bloque[col_tecnico] = tec
                lista_final_otros.append(bloque)
                puntero += 50

        # UNIÓN
        df_resultado = pd.concat([df_ph_final] + lista_final_otros, ignore_index=True)

        with tab1:
            st.success(f"Asignación Exitosa: {len(df_ph_final)} pólizas para PH y {len(df_resultado) - len(df_ph_final)} repartidas.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="Asignacion_Final_UT.xlsx")

        with tab2:
            st.subheader("Carga por Técnico Asignado")
            st.plotly_chart(px.bar(df_resultado[col_tecnico].value_counts().reset_index(), x=col_tecnico, y="count", color=col_tecnico), use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
