import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación con Prioridad de Edad")

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

        # Limpieza de deuda para cálculos
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
        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración y Filtros", "📋 Tabla y Descarga", "📊 Dashboard"])

        # =========================
        # FILTROS Y PRIORIDAD
        # =========================
        with tab_filtros:
            st.subheader("⚙️ Parámetros de Selección")
            
            c1, c2 = st.columns(2)
            with c1:
                ciclos_disp = sorted(df[col_ciclo].dropna().astype(str).unique())
                ciclos_sel = st.multiselect("1. Filtrar Ciclos", ciclos_disp, default=ciclos_disp)
                
                todos_tecnicos = sorted(df[col_tecnico].dropna().astype(str).str.strip().unique())
                tecnicos_sel = st.multiselect("2. Técnicos a Procesar", todos_tecnicos, default=todos_tecnicos)

            with c2:
                edades_disp = sorted(df[col_edad].dropna().astype(str).unique())
                edades_sel = st.multiselect("3. Filtrar Rangos de Edad", edades_disp, default=edades_disp)
                
                # --- Lógica de Prioridad ---
                st.write("**4. Definir Prioridad de Edad (Arrastra para reordenar)**")
                prioridad_edades = st.multiselect(
                    "Orden de importancia (el primero tiene prioridad):", 
                    edades_sel, 
                    default=edades_sel,
                    help="Las pólizas se asignarán primero a los rangos que pongas arriba en esta lista."
                )

        # =========================
        # PROCESAMIENTO Y ORDENAMIENTO
        # =========================
        # Filtrado Base
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) &
            (df[col_edad].astype(str).isin(edades_sel))
        ].copy()

        # Aplicar Prioridad Dinámica
        # Convertimos la columna de edad en una categoría con el orden elegido por el usuario
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)
        
        # Ordenamos: 1. Por el orden de edad elegido, 2. Por Deuda (mayor a menor)
        df_pool = df_pool.sort_values(by=[col_edad, "_deuda_num"], ascending=[True, False])

        # =========================
        # LÓGICA DE ASIGNACIÓN
        # =========================
        unidades_ph = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH",
            "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUS-PENSION BQ 36 PH",
            "ITA SUSPENSION BQ 37 PH"
        ]

        # 1. Asignación PH (Mantienen su lógica de top 50 por deuda dentro de su grupo)
        df_ph_final = (
            df_pool[df_pool[col_tecnico].isin(unidades_ph)]
            .groupby(col_tecnico)
            .head(50)
        )

        # 2. Asignación General (Técnicos NO PH)
        indices_ph = set(df_ph_final.index)
        df_para_repartir = df_pool.drop(index=indices_ph, errors='ignore').copy()
        
        # Importante: Re-ordenamos para asegurar que el reparto respete la prioridad de edad
        df_para_repartir = df_para_repartir.sort_values(by=[col_edad, col_barrio, "_deuda_num"], ascending=[True, True, False])

        lista_final_otros = []
        puntero = 0
        tecnicos_no_ph = [t for t in tecnicos_sel if t not in unidades_ph]

        for tec in tecnicos_no_ph:
            bloque = df_para_repartir.iloc[puntero : puntero + 50].copy()
            if not bloque.empty:
                bloque[col_tecnico] = tec
                lista_final_otros.append(bloque)
                puntero += 50
            else:
                break

        df_resultado = pd.concat([df_ph_final] + lista_final_otros, ignore_index=True) if lista_final_otros or not df_ph_final.empty else pd.DataFrame()

        # =========================
        # VISTAS (TABLA Y DASHBOARD)
        # =========================
        if not df_resultado.empty:
            with tab_filtros:
                st.divider()
                st.success(f"✅ Se han asignado {len(df_resultado)} pólizas prioritarias.")

            with tab1:
                st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel de Asignación", data=output.getvalue(), file_name="Asignacion_Priorizada.xlsx")

            with tab2:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🏆 Deuda Asignada por Técnico")
                    ranking = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                    ranking.columns = ["Técnico", "Deuda Total"]
                    st.table(ranking.style.format({"Deuda Total": "$ {:,.0f}"}))
                with c2:
                    st.subheader("📊 Cumplimiento de Prioridad (Edades)")
                    conteo_edad = df_resultado[col_edad].value_counts().reindex(prioridad_edades).reset_index()
                    fig_bar = px.bar(conteo_edad, x=col_edad, y="count", color=col_edad, title="Pólizas asignadas según tu prioridad")
                    st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("No hay datos que coincidan con los filtros seleccionados.")

    except Exception as e:
        st.error(f"Error en el proceso: {e}")
else:
    st.info("👋 Sube un archivo Excel para comenzar.")
