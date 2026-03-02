import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("📊 Seguimiento UT")

# =============================
# CARGA ARCHIVO
# =============================

archivo = st.file_uploader("Cargar archivo consolidado", type=["xlsx", "csv"])

if archivo is not None:

    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)

    # =============================
    # LIMPIEZA BÁSICA
    # =============================

    df["_deuda_num"] = (
        df["DEUDA"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    df["EDAD"] = pd.to_numeric(df["EDAD"], errors="coerce")

    # =============================
    # SIDEBAR FILTROS
    # =============================

    st.sidebar.header("🔎 Filtros")

    edad_min, edad_max = st.sidebar.slider(
        "Rango de Edad",
        int(df["EDAD"].min()),
        int(df["EDAD"].max()),
        (25, 60)
    )

    subcategoria = st.sidebar.multiselect(
        "Subcategoría",
        df["SUBCATEGORIA"].unique()
    )

    deuda_minima = st.sidebar.number_input(
        "Deuda mínima",
        min_value=0.0,
        value=0.0
    )

    df_filtrado = df.copy()

    df_filtrado = df_filtrado[
        (df_filtrado["EDAD"] >= edad_min) &
        (df_filtrado["EDAD"] <= edad_max)
    ]

    if subcategoria:
        df_filtrado = df_filtrado[df_filtrado["SUBCATEGORIA"].isin(subcategoria)]

    df_filtrado = df_filtrado[df_filtrado["_deuda_num"] >= deuda_minima]

    # =============================
    # TABS
    # =============================

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard",
        "👨‍🔧 Técnicos",
        "👨‍💼 Supervisores",
        "🏆 Resumen Supervisores"
    ])

    # =====================================================
    # TAB 1 - DASHBOARD (GRÁFICAS ORIGINALES)
    # =====================================================

    with tab1:

        st.subheader("Resumen General")

        col1, col2 = st.columns(2)

        with col1:
            fig1 = px.histogram(df_filtrado, x="EDAD")
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            fig2 = px.bar(
                df_filtrado.groupby("SUBCATEGORIA")["_deuda_num"].sum().reset_index(),
                x="SUBCATEGORIA",
                y="_deuda_num",
                text_auto=True
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(df_filtrado, use_container_width=True)

    # =====================================================
    # TAB 2 - ASIGNACIÓN TÉCNICOS
    # =====================================================

    with tab2:

        st.subheader("Asignación Técnicos")

        tecnicos = st.number_input("Cantidad de técnicos", 1, 20, 5)

        max_por_tecnico = st.number_input("Máximo por técnico", 1, 20, 8)

        if st.button("Asignar técnicos"):

            df_tecnicos = df_filtrado.copy()
            df_tecnicos["TECNICO"] = None

            total_capacidad = tecnicos * max_por_tecnico
            contador_global = 0

            for t in range(1, tecnicos + 1):
                contador_local = 0
                for i in range(len(df_tecnicos)):
                    if contador_global >= total_capacidad:
                        break
                    if pd.isna(df_tecnicos.at[i, "TECNICO"]) and contador_local < max_por_tecnico:
                        df_tecnicos.at[i, "TECNICO"] = f"Técnico {t}"
                        contador_local += 1
                        contador_global += 1

            st.session_state["df_tecnicos"] = df_tecnicos

            st.dataframe(df_tecnicos, use_container_width=True)

    # =====================================================
    # TAB 3 - ASIGNACIÓN SUPERVISORES
    # =====================================================

    with tab3:

        st.subheader("Asignación Supervisores")

        SUPERVISORES_FIJOS = [
            "FAVIO ERNESTO VASQUEZ ROMERO",
            "DEGUIN ZOCRATE DEGUIN ZOCRATE",
            "YESID RAFAEL REALES MORENO",
            "ABILIO SEGUNDO ARAUJO ARIÑO",
            "JAVIER DAVID GOMEZ BARRIOS"
        ]

        activar = st.toggle("Activar asignación a supervisores")

        if activar and "df_tecnicos" in st.session_state:

            df_sup = st.session_state["df_tecnicos"].copy()

            supervisores_sel = st.multiselect(
                "Selecciona supervisores:",
                SUPERVISORES_FIJOS
            )

            if supervisores_sel:

                df_sup["SUPERVISOR_ASIGNADO"] = None

                max_por_supervisor = 8
                total_capacidad = len(supervisores_sel) * max_por_supervisor

                contador_global = 0

                for sup in supervisores_sel:
                    contador_local = 0
                    for i in range(len(df_sup)):
                        if contador_global >= total_capacidad:
                            break
                        if pd.isna(df_sup.at[i, "SUPERVISOR_ASIGNADO"]) and contador_local < max_por_supervisor:
                            df_sup.at[i, "SUPERVISOR_ASIGNADO"] = sup
                            contador_local += 1
                            contador_global += 1

                st.session_state["df_sup"] = df_sup

                st.dataframe(df_sup, use_container_width=True)

        else:
            st.info("Primero asigna técnicos.")

    # =====================================================
    # TAB 4 - RESUMEN SUPERVISORES
    # =====================================================

    with tab4:

        st.subheader("Resumen Supervisores")

        if "df_sup" in st.session_state:

            df_sup = st.session_state["df_sup"]

            df_resumen = (
                df_sup
                .dropna(subset=["SUPERVISOR_ASIGNADO"])
                .groupby("SUPERVISOR_ASIGNADO")
                .agg(
                    Total_Polizas=("SUPERVISOR_ASIGNADO", "count"),
                    Total_Deuda=("_deuda_num", "sum")
                )
                .reset_index()
            )

            if not df_resumen.empty:

                st.dataframe(df_resumen, use_container_width=True)

                fig = px.bar(
                    df_resumen,
                    x="SUPERVISOR_ASIGNADO",
                    y="Total_Deuda",
                    text_auto=True
                )

                st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("No hay asignaciones aún.")

        else:
            st.info("No se han asignado supervisores.")
