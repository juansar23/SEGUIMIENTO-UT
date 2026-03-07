import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Unidad de Trabajo")

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

    # ================================
    # VALIDAR COLUMNAS CLAVE
    # ================================
    columnas_necesarias = ["RANGO_EDAD", "SUBCATEGORIA", "DEUDA_TOTAL", "TECNICOS_INTEGRALES"]
    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ No existe la columna: {col}")
            st.stop()

    # ================================
    # LIMPIAR DEUDA PARA CALCULOS
    # ================================
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
    st.sidebar.header("🎯 Filtros")
    
    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos_lista = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)
    deuda_minima = st.sidebar.number_input("Deudas mayores a:", min_value=0, value=100000, step=50000)

    st.sidebar.subheader("👨‍💼 Supervisores")
    sups_final = st.sidebar.multiselect("Supervisores a incluir", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    st.sidebar.subheader("👥 Técnicos Integrales")
    modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")
    if modo_exclusion:
        excluir = st.sidebar.multiselect("Técnicos a excluir", tecnicos_lista)
        tecnicos_final = [t for t in tecnicos_lista if t not in excluir]
    else:
        tecnicos_final = st.sidebar.multiselect("Técnicos a incluir", tecnicos_lista, default=tecnicos_lista)

    if st.sidebar.button("Limpiar filtros"):
        st.rerun()

    # ================================
    # LÓGICA DE ASIGNACIÓN (SIN CRUCES)
    # ================================
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by="_deuda_num", ascending=False).copy()

    # Asignación Supervisores (8 polizas c/u)
    total_cupos_sup = len(sups_final) * 8
    df_supervisores = df_base.head(total_cupos_sup).copy()
    if not df_supervisores.empty:
        lista_nombres_sup = []
        for s in sups_final: lista_nombres_sup.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = lista_nombres_sup[:len(df_supervisores)]

    # Asignación Operarios (Resto, 50 polizas c/u)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    df_restante = df_restante[df_restante["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_final)]
    df_tecnicos = df_restante.groupby("TECNICOS_INTEGRALES").head(50).copy()
    df_tecnicos["ASIGNADO_A"] = df_tecnicos["TECNICOS_INTEGRALES"]

    # ================================
    # PESTAÑAS DEL DASHBOARD
    # ================================
    tab_tabla, tab_sup, tab_tec = st.tabs(["📋 Tabla General", "👨‍💼 Supervisores", "👥 Operarios"])

    with tab_tabla:
        df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)
        st.success(f"Pólizas asignadas: {len(df_final)}")
        st.dataframe(df_final, use_container_width=True)
        
        # Descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Reporte")
        st.download_button("📥 Descargar Reporte", data=output.getvalue(), file_name="asignacion_ut.xlsx")

    with tab_sup:
        st.header("Análisis de Carga - Supervisores")
        m1, m2 = st.columns(2)
        m1.metric("Pólizas Supervisores", len(df_supervisores))
        m2.metric("Deuda Gestionada", f"$ {df_supervisores['_deuda_num'].sum():,.0f}")
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Carga por Supervisor (Máx 8)")
            fig_sup_bar = px.bar(df_supervisores["ASIGNADO_A"].value_counts().reset_index(), 
                                 x="count", y="ASIGNADO_A", orientation='h', text_auto=True)
            st.plotly_chart(fig_sup_bar, use_container_width=True)

        with col2:
            st.subheader("🥧 Distribución por Subcategoría")
            fig_sup_pie = px.pie(df_supervisores, names="SUBCATEGORIA", values="_deuda_num")
            st.plotly_chart(fig_sup_pie, use_container_width=True)

        st.divider()
        st.subheader("🏆 Detalle de Deuda por Supervisor")
        top_sup_tabla = df_supervisores.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).reset_index()
        top_sup_tabla.columns = ["Supervisor", "Total Deuda"]
        top_sup_tabla["Total Deuda"] = top_sup_tabla["Total Deuda"].apply(lambda x: f"$ {x:,.0f}")
        st.table(top_sup_tabla)

    with tab_tec:
        st.header("Análisis de Carga - Operarios")
        m3, m4 = st.columns(2)
        m3.metric("Pólizas Operarios", len(df_tecnicos))
        m4.metric("Deuda Gestionada", f"$ {df_tecnicos['_deuda_num'].sum():,.0f}")

        st.divider()
        st.subheader("🏆 Top 10 Operarios con Mayor Deuda")
        top10_tec = df_tecnicos.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
        top10_tec.columns = ["Operario", "Total Deuda"]
        top10_tec["Total Deuda"] = top10_tec["Total Deuda"].apply(lambda x: f"$ {x:,.0f}")
        st.dataframe(top10_tec, use_container_width=True)

        st.divider()
        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("📊 Pólizas por Rango de Edad")
            fig_tec_edad = px.bar(df_tecnicos["RANGO_EDAD"].astype(str).value_counts().reset_index(), 
                                  x="RANGO_EDAD", y="count", text_auto=True)
            st.plotly_chart(fig_tec_edad, use_container_width=True)

        with col4:
            st.subheader("🥧 Distribución por Subcategoría")
            fig_tec_pie = px.pie(df_tecnicos, names="SUBCATEGORIA", values="count")
            st.plotly_chart(fig_tec_pie, use_container_width=True)

else:
    st.info("👆 Sube un archivo Excel para procesar las asignaciones.")
