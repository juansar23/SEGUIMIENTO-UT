import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación por Bloque de Barrio")

# Cargar archivo
archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

# Columnas
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"
col_subcat = "SUBCATEGORIA"

if archivo:
    try:
        # =========================
        # 1. LECTURA
        # =========================
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()

        # =========================
        # LIMPIEZA DEUDA
        # =========================
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # =========================
        # TABS
        # =========================
        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Filtros", "📋 Tabla y Descarga", "📊 Dashboard"])

        # =========================
        # FILTROS
        # =========================
        with tab_filtros:
            st.subheader("⚙️ Configuración de Filtros")

            ciclos_disp = sorted(df[col_ciclo].dropna().astype(str).unique())
            ciclos_sel = st.multiselect("Filtrar Ciclos", ciclos_disp, default=ciclos_disp)

            # Extraer técnicos únicos (quitando nulos)
            todos_tecnicos = sorted(df[col_tecnico].dropna().astype(str).str.strip().unique())
            tecnicos_sel = st.multiselect("Técnicos a Procesar", todos_tecnicos, default=todos_tecnicos)

            edades_disp = sorted(df[col_edad].dropna().astype(str).unique())
            edades_sel = st.multiselect("Filtrar por Rango de Edad", edades_disp, default=edades_disp)

        # =========================
        # FILTRADO BASE
        # =========================
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) &
            (df[col_edad].astype(str).isin(edades_sel))
        ].copy()

        # =========================
        # LÓGICA DE ASIGNACIÓN MEJORADA
        # =========================
        unidades_ph = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH",
            "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUS-PENSION BQ 36 PH",
            "ITA SUSPENSION BQ 37 PH"
        ]

        # 1. Procesar PH (Se llevan sus mejores 50 por deuda)
        df_ph_final = (
            df_pool[df_pool[col_tecnico].isin(unidades_ph)]
            .sort_values(by="_deuda_num", ascending=False)
            .groupby(col_tecnico)
            .head(50)
        )

        # 2. Pool para técnicos NO PH (incluye los que no tenían técnico asignado)
        indices_ocupados_ph = set(df_ph_final.index)
        
        # Filtramos lo que queda disponible (excluyendo lo que ya tomó PH)
        df_disponible_otros = df_pool.drop(index=indices_ocupados_ph, errors='ignore').copy()
        
        # Ordenamos geográficamente para que los bloques de 50 sean coherentes por barrio
        df_disponible_otros = df_disponible_otros.sort_values(by=[col_ciclo, col_barrio, col_direccion])

        lista_final_otros = []
        puntero = 0 # Para ir segmentando el dataframe de 50 en 50
        
        tecnicos_no_ph = [t for t in tecnicos_sel if t not in unidades_ph]

        for tec in tecnicos_no_ph:
            # Extraemos un bloque de 50 filas partiendo de la posición actual del puntero
            bloque = df_disponible_otros.iloc[puntero : puntero + 50].copy()
            
            if not bloque.empty:
                bloque[col_tecnico] = tec
                lista_final_otros.append(bloque)
                puntero += 50
            else:
                # Si no hay más filas, dejamos de asignar
                break

        # Combinar resultados finales
        if lista_final_otros:
            df_resultado = pd.concat([df_ph_final] + lista_final_otros, ignore_index=True)
        else:
            df_resultado = df_ph_final

        # =========================
        # MÉTRICAS EN TAB FILTROS
        # =========================
        with tab_filtros:
            st.divider()
            st.info(f"💡 **Estado de la Asignación:**\n"
                    f"- Pólizas totales tras filtros: **{len(df_pool)}**\n"
                    f"- Pólizas asignadas con éxito: **{len(df_resultado)}**\n"
                    f"- Técnicos que recibieron trabajo: **{df_resultado[col_tecnico].nunique()}** de **{len(tecnicos_sel)}**")
            
            if len(df_resultado) < (len(tecnicos_sel) * 50) and len(df_disponible_otros) < (len(tecnicos_no_ph) * 50):
                st.warning("⚠️ Se agotaron las pólizas disponibles antes de completar el cupo de todos los técnicos.")

        # =========================
        # TABLA Y DESCARGA
        # =========================
        with tab1:
            st.subheader("📋 Vista Previa de la Asignación")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)

            st.download_button(
                label="📥 Descargar Excel de Asignación",
                data=output.getvalue(),
                file_name="Asignacion_UT_Final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # =========================
        # DASHBOARD
        # =========================
        with tab2:
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("🏆 Top 10 Técnicos (Deuda Asignada)")
                ranking = (
                    df_resultado.groupby(col_tecnico)["_deuda_num"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                    .reset_index()
                )
                ranking.columns = ["Técnico", "Deuda"]
                ranking["Deuda"] = ranking["Deuda"].apply(lambda x: f"$ {x:,.0f}")
                st.table(ranking)

            with c2:
                st.subheader("🥧 Distribución por Subcategoría")
                conteo_sub = df_resultado[col_subcat].value_counts().reset_index()
                conteo_sub.columns = [col_subcat, "cantidad"]
                fig_pie = px.pie(conteo_sub, names=col_subcat, values="cantidad", hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()

            st.subheader("📊 Pólizas por Rango de Edad")
            conteo_edad = df_resultado[col_edad].value_counts().reset_index()
            conteo_edad.columns = [col_edad, "cantidad"]
            fig_bar = px.bar(conteo_edad, x=col_edad, y="cantidad", color=col_edad, text_auto=True)
            st.plotly_chart(fig_bar, use_container_width=True)

    except Exception as e:
        st.error(f"Se produjo un error al procesar el archivo: {e}")

else:
    st.info("Por favor, sube un archivo Excel para comenzar el proceso de asignación.")
