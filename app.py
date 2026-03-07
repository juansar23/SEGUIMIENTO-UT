import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("📊 Dashboard Gestión de Pólizas")

# =====================================================
# CARGA ARCHIVO
# =====================================================

archivo = st.file_uploader("Cargar archivo consolidado", type=["xlsx"])

if archivo:

    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ----------------------------
    # FORMATO FECHAS
    # ----------------------------
    columnas_fecha = ["FECHA_VENCIMIENTO", "ULT_FECHAPAGO", "FECHA_ASIGNACION"]

    for col in columnas_fecha:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # ----------------------------
    # LIMPIAR MONEDA
    # ----------------------------
    df["DEUDA_TOTAL"] = (
        df["DEUDA_TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )

    df["_deuda_num"] = pd.to_numeric(df["DEUDA_TOTAL"], errors="coerce").fillna(0)

    # =====================================================
    # SIDEBAR FILTROS
    # =====================================================

    st.sidebar.header("🔎 Filtros Generales")

    rangos_ordenados = [
        "0-30", "31-60", "61-90", "91-120",
        "121-360", "361-1080", ">1080"
    ]

    rangos_disponibles = [r for r in rangos_ordenados if r in df["RANGO_EDAD"].unique()]

    rangos_sel = st.sidebar.multiselect(
        "Rango Edad",
        rangos_disponibles,
        default=rangos_disponibles
    )

    sub_sel = st.sidebar.multiselect(
        "Subcategoría",
        df["SUBCATEGORIA"].dropna().unique(),
        default=df["SUBCATEGORIA"].dropna().unique()
    )

    deuda_minima = st.sidebar.number_input("Deuda mínima", min_value=0, value=0)

    if st.sidebar.button("⚡ Limpiar filtros"):
        st.rerun()

    # =====================================================
    # FILTRADO BASE
    # =====================================================

    df_filtrado = df[
        (df["RANGO_EDAD"].isin(rangos_sel)) &
        (df["SUBCATEGORIA"].isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].copy()

    # =====================================================
    # TABS
    # =====================================================

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard Técnicos",
        "🛠 Asignación Técnicos",
        "👨‍💼 Asignación Supervisores",
        "📈 Dashboard Supervisores"
    ])

    # =====================================================
    # TAB 2 - ASIGNACIÓN TÉCNICOS
    # =====================================================

    with tab2:

        st.subheader("Asignación a Técnicos")

        tecnicos = df_filtrado["TECNICOS_INTEGRALES"].dropna().unique()
        excluir = st.multiselect("🚫 Excluir técnicos", tecnicos)

        activos = [t for t in tecnicos if t not in excluir]

        st.info(f"👥 Técnicos activos: {len(activos)}")

        df_tecnicos = df_filtrado[
            df_filtrado["TECNICOS_INTEGRALES"].isin(activos)
        ].copy()

        st.session_state["df_tecnicos"] = df_tecnicos

        st.dataframe(df_tecnicos, use_container_width=True)

    # =====================================================
    # TAB 1 - DASHBOARD TÉCNICOS
    # =====================================================

    with tab1:

        if "df_tecnicos" in st.session_state:

            df_t = st.session_state["df_tecnicos"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Pólizas", len(df_t))
            col2.metric("Total Deuda", f"$ {df_t['_deuda_num'].sum():,.0f}")
            col3.metric("Técnicos Activos", df_t["TECNICOS_INTEGRALES"].nunique())

            st.divider()

            st.subheader("🏆 Top 10 Técnicos por Deuda")

            top10 = (
                df_t.groupby("TECNICOS_INTEGRALES")["_deuda_num"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )

            top10.columns = ["Técnico", "Total Deuda"]
            top10["Total Deuda"] = top10["Total Deuda"].apply(lambda x: f"$ {x:,.0f}")

            st.dataframe(top10, use_container_width=True)

            st.subheader("📊 Pólizas por Rango Edad")

            rango_count = (
                df_t["RANGO_EDAD"]
                .value_counts()
                .reindex(rangos_ordenados)
                .dropna()
                .reset_index()
            )

            rango_count.columns = ["Rango", "Cantidad"]

            fig1 = px.bar(rango_count, x="Rango", y="Cantidad", text_auto=True)
            st.plotly_chart(fig1, use_container_width=True, key="grafico_rango_tecnicos")

            st.subheader("🥧 Subcategoría")

            sub_count = df_t["SUBCATEGORIA"].value_counts().reset_index()
            sub_count.columns = ["Subcategoría", "Cantidad"]

            fig2 = px.pie(sub_count, names="Subcategoría", values="Cantidad")
            st.plotly_chart(fig2, use_container_width=True, key="grafico_sub_tecnicos")

    # =====================================================
    # TAB 3 - ASIGNACIÓN SUPERVISORES
    # =====================================================

    with tab3:

        activar = st.toggle("Activar asignación a supervisores")

        supervisores = [
            "FAVIO ERNESTO VASQUEZ ROMERO",
            "DEGUIN ZOCRATE DEGUIN ZOCRATE",
            "YESID RAFAEL REALES MORENO",
            "ABILIO SEGUNDO ARAUJO ARIÑO",
            "JAVIER GOMEZ "
        ]

        if activar:

            supervisor_sel = st.selectbox("Seleccionar Supervisor", supervisores)

            df_base_sup = df_filtrado.copy()

            if "df_tecnicos" in st.session_state:
                df_base_sup = df_base_sup[
                    ~df_base_sup.index.isin(st.session_state["df_tecnicos"].index)
                ]

            df_base_sup = df_base_sup.head(8).copy()
            df_base_sup["SUPERVISOR_ASIGNADO"] = supervisor_sel

            st.session_state["df_sup"] = df_base_sup

            st.success(f"Asignadas {len(df_base_sup)} pólizas a {supervisor_sel}")

            st.dataframe(df_base_sup, use_container_width=True)

    # =====================================================
    # TAB 4 - DASHBOARD SUPERVISORES
    # =====================================================

    with tab4:

        if "df_sup" in st.session_state:

            df_s = st.session_state["df_sup"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Pólizas", len(df_s))
            col2.metric("Total Deuda", f"$ {df_s['_deuda_num'].sum():,.0f}")
            col3.metric("Supervisores Activos", df_s["SUPERVISOR_ASIGNADO"].nunique())

            st.divider()

            st.subheader("🏆 Ranking Supervisores por Deuda")

            ranking = (
                df_s.groupby("SUPERVISOR_ASIGNADO")["_deuda_num"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )

            fig_rank = px.bar(
                ranking,
                x="SUPERVISOR_ASIGNADO",
                y="_deuda_num",
                text_auto=True
            )

            st.plotly_chart(fig_rank, use_container_width=True, key="grafico_rank_supervisores")

            st.subheader("📊 Pólizas por Rango Edad")

            rango_sup = (
                df_s["RANGO_EDAD"]
                .value_counts()
                .reindex(rangos_ordenados)
                .dropna()
                .reset_index()
            )

            rango_sup.columns = ["Rango", "Cantidad"]

            fig3 = px.bar(rango_sup, x="Rango", y="Cantidad", text_auto=True)
            st.plotly_chart(fig3, use_container_width=True, key="grafico_rango_supervisores")

            st.subheader("🥧 Subcategoría")

            sub_sup = df_s["SUBCATEGORIA"].value_counts().reset_index()
            sub_sup.columns = ["Subcategoría", "Cantidad"]

            fig4 = px.pie(sub_sup, names="Subcategoría", values="Cantidad")
            st.plotly_chart(fig4, use_container_width=True, key="grafico_sub_supervisores")
