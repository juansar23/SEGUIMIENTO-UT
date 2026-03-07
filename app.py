import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Asignación Dual: Supervisores y Técnicos")

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

    # VALIDAR COLUMNAS CLAVE
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
    st.sidebar.header("🎯 Configuración")
    
    # 1. Filtro Supervisores
    st.sidebar.subheader("👨‍💼 Supervisores")
    sups_final = st.sidebar.multiselect("Supervisores a incluir", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    # 2. Filtro Técnicos
    st.sidebar.divider()
    st.sidebar.subheader("👥 Técnicos Integrales")
    tecnicos_lista = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())
    tecs_final = st.sidebar.multiselect("Técnicos a incluir", tecnicos_lista, default=tecnicos_lista)

    # 3. Filtros de Data (CORRECCIÓN DEL ERROR DE SORTED)
    st.sidebar.divider()
    
    # Manejo seguro de nulos y tipos mixtos para los filtros
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())

    sub_sel = st.sidebar.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
    edad_sel = st.sidebar.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
    
    deuda_minima = st.sidebar.number_input("Deudas mayores a:", min_value=0, value=100000)

    if st.sidebar.button("Limpiar filtros"):
        st.rerun()

    # ================================
    # LÓGICA DE ASIGNACIÓN (SIN CRUCES)
    # ================================
    
    # Filtro base
    df_base = df[
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) & 
        (df["RANGO_EDAD"].astype(str).isin(edad_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values("_deuda_num", ascending=False)

    # --- ASIGNACIÓN SUPERVISORES (Prioridad 1) ---
    # Tomamos las pólizas con mayor deuda global
    total_cupos_sup = len(sups_final) * 8
    df_supervisores = df_base.head(total_cupos_sup).copy()
    
    if not df_supervisores.empty:
        lista_nombres_sup = []
        for s in sups_final:
            lista_nombres_sup.extend([s] * 8)
        
        df_supervisores["ASIGNADO_A"] = lista_nombres_sup[:len(df_supervisores)]
        df_supervisores["TIPO_ASIGNACION"] = "SUPERVISOR"

    # --- ASIGNACIÓN TÉCNICOS (Prioridad 2) ---
    # Quitamos de la base lo que ya se asignó a supervisores para que NO haya cruces
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    
    # Filtramos por los técnicos seleccionados
    df_restante = df_restante[df_restante["TECNICOS_INTEGRALES"].astype(str).isin(tecs_final)]
    
    # Aplicamos límite de 50 por técnico
    df_tecnicos = df_restante.groupby("TECNICOS_INTEGRALES").head(50).copy()
    df_tecnicos["ASIGNADO_A"] = df_tecnicos["TECNICOS_INTEGRALES"]
    df_tecnicos["TIPO_ASIGNACION"] = "TECNICO"

    # Unimos ambos resultados
    df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)

    # ================================
    # TABS Y DASHBOARD
    # ================================
    tab1, tab2 = st.tabs(["📋 Listado de Trabajo", "📊 Dashboard"])

    with tab1:
        st.success(f"Asignación completada: {len(df_supervisores)} pólizas a Supervisores y {len(df_tecnicos)} a Técnicos.")
        st.dataframe(df_final, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Reporte")
        
        st.download_button("📥 Descargar Plan de Trabajo", data=output.getvalue(), file_name="asignacion_ut.xlsx")

    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Carga por Supervisor (Máx 8)")
            if not df_supervisores.empty:
                sup_graph = df_supervisores["ASIGNADO_A"].value_counts().reset_index()
                st.plotly_chart(px.bar(sup_graph, x="count", y="ASIGNADO_A", orientation='h', text_auto=True), use_container_width=True)
            else:
                st.write("No hay datos asignados a supervisores.")

        with col2:
            st.subheader("Carga por Técnicos (Top 10)")
            if not df_tecnicos.empty:
                tec_graph = df_tecnicos["ASIGNADO_A"].value_counts().head(10).reset_index()
                st.plotly_chart(px.bar(tec_graph, x="count", y="ASIGNADO_A", orientation='h', text_auto=True), use_container_width=True)
            else:
                st.write("No hay datos asignados a técnicos.")

        st.divider()
        st.subheader("💰 Resumen de Deuda")
        fig_pie = px.pie(df_final, values="_deuda_num", names="TIPO_ASIGNACION", title="Deuda: Supervisores vs Técnicos")
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.info("👆 Sube el archivo Excel para procesar las asignaciones.")
