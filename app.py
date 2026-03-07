import streamlit as st
import pandas as pd
import io
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Asignación de Trabajo - Supervisores")

# Lista fija de supervisores
SUPERVISORES_NOMINA = [
    "FAVIO ERNESTO VASQUEZ ROMERO",
    "DEGUIN ZOCRATE DEGUIN ZOCRATE",
    "YESID RAFAEL REALES MORENO",
    "ABILIO SEGUNDO ARAUJO ARIÑO",
    "JAVIER DAVID GOMEZ BARRIOS"
]

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # VALIDAR COLUMNAS CLAVE (Sin Supervisor porque la crearemos)
    columnas_necesarias = ["RANGO_EDAD", "SUBCATEGORIA", "DEUDA_TOTAL", "TECNICOS_INTEGRALES"]
    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ No existe la columna: {col}")
            st.stop()

    # LIMPIAR DEUDA
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # SIDEBAR FILTROS
    # ================================
    st.sidebar.header("🎯 Configuración de Asignación")

    # Filtro de Supervisores (Manual)
    modo_ex_sup = st.sidebar.checkbox("Seleccionar todos los supervisores excepto")
    if modo_ex_sup:
        excluir_sup = st.sidebar.multiselect("Supervisores a excluir", SUPERVISORES_NOMINA)
        supervisores_final = [s for s in SUPERVISORES_NOMINA if s not in excluir_sup]
    else:
        supervisores_final = st.sidebar.multiselect("Supervisores a incluir", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    st.sidebar.divider()
    
    # Filtros de datos
    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    
    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)
    deuda_minima = st.sidebar.number_input("Deudas mayores a:", min_value=0, value=100000, step=50000)

    if st.sidebar.button("Limpiar filtros"):
        st.rerun()

    # ================================
    # PROCESO DE ASIGNACIÓN
    # ================================
    
    # 1. Filtrar la base según criterios
    df_filtrado = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].copy()

    # 2. Ordenar por deuda (Priorizar lo más alto)
    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)

    # 3. Lógica de Asignación a Supervisores (Máximo 8 c/u)
    total_a_asignar = len(supervisores_final) * 8
    df_asignacion = df_filtrado.head(total_a_asignar).copy()

    if not df_asignacion.empty:
        # Creamos la columna de supervisor repitiendo cada nombre 8 veces
        lista_asignacion = []
        for sup in supervisores_final:
            lista_asignacion.extend([sup] * 8)
        
        # Recortamos la lista en caso de que haya menos de (Supervisores * 8) pólizas
        lista_asignacion = lista_asignacion[:len(df_asignacion)]
        df_asignacion["SUPERVISOR_ASIGNADO"] = lista_asignacion
    
    # ================================
    # TABS
    # ================================
    tab1, tab2 = st.tabs(["📋 Plan de Trabajo", "📊 Análisis de Carga"])

    with tab1:
        if df_asignacion.empty:
            st.warning("No hay pólizas que cumplan con los filtros para asignar.")
        else:
            st.success(f"Se han asignado {len(df_asignacion)} pólizas a {len(supervisores_final)} supervisores.")
            st.dataframe(df_asignacion, use_container_width=True)

            # Preparar descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_asignacion.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Asignacion")
            
            st.download_button(
                "📥 Descargar Excel de Asignación",
                data=output.getvalue(),
                file_name="trabajo_supervisores.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with tab2:
        if not df_asignacion.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📦 Pólizas por Supervisor")
                carga = df_asignacion["SUPERVISOR_ASIGNADO"].value_counts().reset_index()
                carga.columns = ["Supervisor", "Cantidad"]
                fig1 = px.bar(carga, x="Cantidad", y="Supervisor", orientation='h', 
                             text_auto=True, color="Cantidad", color_continuous_scale="Blues")
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                st.subheader("💰 Deuda Total Asignada")
                deuda_sup = df_asignacion.groupby("SUPERVISOR_ASIGNADO")["_deuda_num"].sum().reset_index()
                fig2 = px.pie(deuda_sup, values="_deuda_num", names="SUPERVISOR_ASIGNADO", hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)
            
            st.divider()
            
            st.subheader("📈 Top 10 Pólizas de Mayor Deuda en la Asignación")
            top_p = df_asignacion.head(10)[["SUPERVISOR_ASIGNADO", "TECNICOS_INTEGRALES", "DEUDA_TOTAL"]]
            st.table(top_p)
        else:
            st.info("Sube un archivo y ajusta los filtros para ver las gráficas.")

else:
    st.info("👆 Sube el archivo Excel para iniciar la repartición de trabajo por supervisor.")
