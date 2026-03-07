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
    columnas_necesarias = [
        "RANGO_EDAD",
        "SUBCATEGORIA",
        "DEUDA_TOTAL",
        "TECNICOS_INTEGRALES"
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ No existe la columna: {col}")
            st.stop()

    # ================================
    # LIMPIAR DEUDA PARA CALCULOS
    # ================================
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"]
        .astype(str)
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

    # Filtro Seguro (Fix TypeError)
    rangos = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)

    deuda_minima = st.sidebar.number_input(
        "Deudas mayores a:",
        min_value=0,
        value=100000,
        step=50000
    )

    # Sección Supervisores en Sidebar
    st.sidebar.subheader("👨‍💼 Supervisores")
    sups_final = st.sidebar.multiselect("Supervisores a incluir", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    # Sección Técnicos en Sidebar
    st.sidebar.subheader("👥 Técnicos Integrales")
    modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")

    if modo_exclusion:
        excluir = st.sidebar.multiselect("Técnicos a excluir", tecnicos)
        tecnicos_final = [t for t in tecnicos if t not in excluir]
    else:
        tecnicos_final = st.sidebar.multiselect("Técnicos a incluir", tecnicos, default=tecnicos)

    if st.sidebar.button("Limpiar filtros"):
        st.rerun()

    # ================================
    # LÓGICA DE ASIGNACIÓN SIN CRUCES
    # ================================
    
    # 1. Base filtrada inicial
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by="_deuda_num", ascending=False).copy()

    # 2. Asignación Supervisores (Primero las de mayor deuda)
    total_cupos_sup = len(sups_final) * 8
    df_supervisores = df_base.head(total_cupos_sup).copy()
    
    if not df_supervisores.empty:
        lista_nombres_sup = []
        for s in sups_final:
            lista_nombres_sup.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = lista_nombres_sup[:len(df_supervisores)]
        df_supervisores["TIPO"] = "SUPERVISOR"

    # 3. Asignación Técnicos (Lo que sobra de la base)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    df_restante = df_restante[df_restante["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_final)]
    
    df_tecnicos = df_restante.groupby("TECNICOS_INTEGRALES").head(50).copy()
    df_tecnicos["ASIGNADO_A"] = df_tecnicos["TECNICOS_INTEGRALES"]
    df_tecnicos["TIPO"] = "TECNICO"

    # Consolidado para la tabla
    df_filtrado = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)

    # ================================
    # FORMATEAR FECHAS
    # ================================
    columnas_fecha = ["FECHA_VENCIMIENTO", "ULT_FECHAPAGO", "FECHA_ASIGNACION"]
    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # ================================
    # TABS
    # ================================
    tab1, tab2 = st.tabs(["📋 Tabla", "📊 Dashboard"])

    with tab1:
        st.success(f"Pólizas Supervisores: {len(df_supervisores)} | Pólizas Técnicos: {len(df_tecnicos)}")
        st.dataframe(df_filtrado, use_container_width=True)

        if not df_filtrado.empty:
            output = io.BytesIO()
            df_export = df_filtrado.copy()
            columnas_moneda = ["ULT_PAGO", "VALOR_ULTFACT", "DEUDA_TOTAL"]

            for col in columnas_moneda:
                if col in df_export.columns:
                    df_export[col] = df_export[col].astype(str).str.replace(r"[\$,.]", "", regex=True)
                    df_export[col] = pd.to_numeric(df_export[col], errors="coerce").fillna(0)

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Reporte")
            
            st.download_button("📥 Descargar archivo", data=output.getvalue(), file_name="resultado_asignacion.xlsx")

    with tab2:
        # MÉTRICAS
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Pólizas", len(df_filtrado))
        c2.metric("Total Deuda", f"$ {df_filtrado['_deuda_num'].sum():,.0f}")
        c3.metric("Personal Activo", df_filtrado["ASIGNADO_A"].nunique())

        st.divider()

        # --- SECCIÓN SUPERVISORES (NUEVA) ---
        st.header("👨‍💼 Sección Supervisores")
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.subheader("🏆 Top Supervisores por Deuda")
            top_sup = df_supervisores.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).reset_index()
            top_sup.columns = ["Supervisor", "Total Deuda"]
            top_sup["Total Deuda"] = top_sup["Total Deuda"].apply(lambda x: f"$ {x:,.0f}")
            st.dataframe(top_sup, use_container_width=True)

        with col_s2:
            st.subheader("📊 Carga de Pólizas (Máx 8)")
            conteo_sup = df_supervisores["ASIGNADO_A"].value_counts().reset_index()
            fig_sup = px.bar(conteo_sup, x="count", y="ASIGNADO_A", orientation='h', text_auto=True, color_discrete_sequence=['#636EFA'])
            st.plotly_chart(fig_sup, use_container_width=True)

        st.divider()

        # --- SECCIÓN TÉCNICOS (ORIGINAL) ---
        st.header("👥 Sección Técnicos")
        st.subheader("🏆 Top 10 Técnicos con Mayor Deuda")
        top10_tec = df_tecnicos.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
        top10_tec.columns = ["Técnico", "Total Deuda"]
        top10_tec["Total Deuda"] = top10_tec["Total Deuda"].apply(lambda x: f"$ {x:,.0f}")
        st.dataframe(top10_tec, use_container_width=True)

        # GRÁFICAS GENERALES (CONSERVADAS)
        st.divider()
        st.subheader("📊 Pólizas por Rango de Edad (Total)")
        conteo_edad = df_filtrado["RANGO_EDAD"].astype(str).value_counts().reset_index()
        fig_edad = px.bar(conteo_edad, x="RANGO_EDAD", y="count", text_auto=True)
        st.plotly_chart(fig_edad, use_container_width=True)

        st.subheader("🥧 Distribución por Subcategoría (Total)")
        conteo_sub = df_filtrado["SUBCATEGORIA"].value_counts().reset_index()
        fig_pie = px.pie(conteo_sub, names="SUBCATEGORIA", values="count")
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.info("👆 Sube un archivo para comenzar.")
