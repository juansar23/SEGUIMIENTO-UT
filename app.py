import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Asignación Dual (Sup/Tec)")

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
    st.sidebar.header("🎯 Filtros de Selección")
    
    # 1. Filtro Supervisores
    st.sidebar.subheader("👨‍💼 Supervisores")
    modo_ex_sup = st.sidebar.checkbox("Seleccionar todos excepto (Sup)")
    if modo_ex_sup:
        excluir_sup = st.sidebar.multiselect("Supervisores a excluir", SUPERVISORES_NOMINA)
        sups_final = [s for s in SUPERVISORES_NOMINA if s not in excluir_sup]
    else:
        sups_final = st.sidebar.multiselect("Supervisores a incluir", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    # 2. Filtro Técnicos
    st.sidebar.divider()
    st.sidebar.subheader("👥 Técnicos Integrales")
    tecnicos_lista = sorted(df["TECNICOS_INTEGRALES"].dropna().unique())
    modo_ex_tec = st.sidebar.checkbox("Seleccionar todos excepto (Tec)")
    if modo_ex_tec:
        excluir_tec = st.sidebar.multiselect("Técnicos a excluir", tecnicos_lista)
        tecs_final = [t for t in tecnicos_lista if t not in excluir_tec]
    else:
        tecs_final = st.sidebar.multiselect("Técnicos a incluir", tecnicos_lista, default=tecnicos_lista)

    # 3. Filtros de Data
    st.sidebar.divider()
    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    sub_sel = st.sidebar.multiselect("Subcategoría", sorted(df["SUBCATEGORIA"].unique()), default=df["SUBCATEGORIA"].unique())
    deuda_minima = st.sidebar.number_input("Deudas mayores a:", min_value=0, value=100000)

    if st.sidebar.button("Limpiar filtros"):
        st.rerun()

    # ================================
    # LÓGICA DE ASIGNACIÓN (SIN CRUCES)
    # ================================
    
    # Base inicial filtrada por criterios globales
    df_base = df[
        (df["SUBCATEGORIA"].isin(sub_sel)) & 
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values("_deuda_num", ascending=False)

    # --- ASIGNACIÓN SUPERVISORES (Primero) ---
    total_sup = len(sups_final) * 8
    df_supervisores = df_base.head(total_sup).copy()
    
    # Asignar nombres
    lista_sups = []
    for s in sups_final: lista_sups.extend([s] * 8)
    df_supervisores["ASIGNADO_A"] = lista_sups[:len(df_supervisores)]
    df_supervisores["TIPO_ASIGNACION"] = "SUPERVISOR"

    # --- ASIGNACIÓN TÉCNICOS (Segundo - Lo que sobra) ---
    # Eliminamos lo que ya se llevó el supervisor para que no se crucen
    df_restante = df_base.drop(df_supervisores.index)
    
    # Filtrar solo por los técnicos seleccionados en sidebar
    df_restante = df_restante[df_restante["TECNICOS_INTEGRALES"].isin(tecs_final)]
    
    df_tecnicos = (
        df_restante
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
        .copy()
    )
    df_tecnicos["ASIGNADO_A"] = df_tecnicos["TECNICOS_INTEGRALES"]
    df_tecnicos["TIPO_ASIGNACION"] = "TECNICO"

    # Consolidado Final
    df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)

    # ================================
    # TABS Y VISUALIZACIÓN
    # ================================
    tab1, tab2 = st.tabs(["📋 Listado de Trabajo", "📊 Dashboard Comparativo"])

    with tab1:
        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Pólizas Supervisores", len(df_supervisores))
        col_t2.metric("Pólizas Técnicos", len(df_tecnicos))
        
        st.dataframe(df_final, use_container_width=True)

        # Exportación
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.to_excel(writer, index=False, sheet_name="Asignacion_Total")
        st.download_button("📥 Descargar Base Consolidada", data=output.getvalue(), file_name="asignacion_ut.xlsx")

    with tab2:
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("👨‍💼 Carga Supervisores")
            fig_sup = px.bar(df_supervisores.groupby("ASIGNADO_A").size().reset_index(name='Cant'), 
                             x="Cant", y="ASIGNADO_A", orientation='h', text_auto=True, title="Pólizas por Supervisor (Máx 8)")
            st.plotly_chart(fig_sup, use_container_width=True)

        with c2:
            st.subheader("👥 Top 10 Carga Técnicos")
            fig_tec = px.bar(df_tecnicos.groupby("ASIGNADO_A").size().reset_index(name='Cant').sort_values("Cant", ascending=False).head(10), 
                             x="Cant", y="ASIGNADO_A", orientation='h', text_auto=True, title="Pólizas por Técnico (Máx 50)")
            st.plotly_chart(fig_tec, use_container_width=True)

        st.divider()
        
        st.subheader("💰 Distribución de Deuda por Tipo de Asignación")
        fig_pie = px.sunburst(df_final, path=['TIPO_ASIGNACION', 'ASIGNADO_A'], values='_deuda_num')
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.info("👆 Sube el archivo para generar la asignación jerárquica.")
