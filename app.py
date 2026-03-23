import streamlit as st
import pandas as pd
import io
import plotly.express as px
import re

st.set_page_config(page_title="UT Optimizado", layout="wide")

st.title("📊 Dashboard UT - Optimizado")

archivo = st.file_uploader("Sube archivo", type=["xlsx"])

col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"
col_subcat = "SUBCATEGORIA"

def normalizar_direccion(dir):
    try:
        d = str(dir).upper()
        d = d.replace("CARRERA", "CR").replace("CRA", "CR")
        d = d.replace("CALLE", "CL")
        nums = re.findall(r'\d+', d)
        partes = d.split()

        if len(partes) >= 2:
            if len(nums) >= 2:
                return f"{partes[0]} {partes[1]} #{nums[0]}-{nums[1]}"
            return f"{partes[0]} {partes[1]}"
        return d
    except:
        return str(dir)

if archivo:
    try:
        # 🔥 SOLO COLUMNAS NECESARIAS
        columnas = [
            col_barrio, col_ciclo, col_direccion,
            col_tecnico, col_deuda, col_edad, col_subcat
        ]

        df = pd.read_excel(archivo, usecols=columnas)

        # 🔥 TIPOS LIVIANOS
        df[col_barrio] = df[col_barrio].astype("category")
        df[col_ciclo] = df[col_ciclo].astype("category")
        df[col_tecnico] = df[col_tecnico].astype("category")

        # LIMPIAR DEUDA
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False)
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # NORMALIZAR DIRECCION
        df["DIR_BASE"] = df[col_direccion].apply(normalizar_direccion)

        # =========================
        # FILTROS (LIVIANOS)
        # =========================
        with st.expander("🎯 Filtros"):

            ciclos_sel = st.multiselect(
                "Ciclo",
                df[col_ciclo].unique(),
                default=df[col_ciclo].unique()
            )

            tecnicos_sel = st.multiselect(
                "Técnicos",
                df[col_tecnico].unique(),
                default=df[col_tecnico].unique()
            )

            excluir = st.multiselect("🚫 Excluir técnicos", df[col_tecnico].unique())

            deuda_min = st.number_input("💰 Deuda mínima", 0, value=0)

        # FILTRADO DIRECTO (SIN COPIAS GRANDES)
        mask = (
            df[col_ciclo].isin(ciclos_sel) &
            df[col_tecnico].isin(tecnicos_sel) &
            ~df[col_tecnico].isin(excluir) &
            (df["_deuda_num"] >= deuda_min)
        )

        df_filtrado = df.loc[mask]

        # ORDEN
        df_filtrado = df_filtrado.sort_values(
            by=[col_ciclo, col_barrio, "DIR_BASE"]
        )

        # =========================
        # ASIGNACIÓN EFICIENTE
        # =========================
        asignados = []
        usados = set()

        tecnicos_final = [t for t in tecnicos_sel if t not in excluir]

        for tec in tecnicos_final:

            cupo = 50

            disponibles = df_filtrado.loc[~df_filtrado.index.isin(usados)]

            for _, grupo in disponibles.groupby([col_ciclo, col_barrio, "DIR_BASE"]):

                if cupo <= 0:
                    break

                bloque = grupo.head(cupo)

                temp = bloque.copy()
                temp[col_tecnico] = tec

                asignados.append(temp)

                usados.update(bloque.index)
                cupo -= len(bloque)

        df_final = pd.concat(asignados, ignore_index=True)

        # =========================
        # RESULTADOS
        # =========================
        st.success(f"Total asignado: {len(df_final)}")

        st.dataframe(df_final, use_container_width=True)

        # DASHBOARD
        col1, col2 = st.columns(2)

        with col1:
            ranking = df_final.groupby(col_tecnico)["_deuda_num"].sum().reset_index()
            st.dataframe(ranking)

        with col2:
            fig = px.pie(df_final, names=col_subcat)
            st.plotly_chart(fig, use_container_width=True)

        # DESCARGA
        output = io.BytesIO()
        df_final.to_excel(output, index=False)

        st.download_button("📥 Descargar", data=output.getvalue())

    except Exception as e:
        st.error(f"Error: {e}")
