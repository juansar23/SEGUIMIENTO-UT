import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación con Restricción PH")

# Colores y Configuración de Columnas
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"
col_subcat = "SUBCATEGORIA"

# Lista Maestra PH
unidades_ph = [
    "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH",
    "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUS-PENSION BQ 36 PH",
    "ITA SUSPENSION BQ 37 PH"
]

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    try:
        # 1. LECTURA Y LIMPIEZA
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()

        # Limpieza de deuda
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # TABS
        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

        with tab_filtros:
            st.subheader("⚙️ Filtros y Prioridades")
            c1, c2 = st.columns(2)
            
            with c1:
                ciclos_disp = sorted(df[col_ciclo].dropna().astype(str).unique())
                ciclos_sel = st.multiselect("Filtrar Ciclos", ciclos_disp, default=ciclos_disp)
                
                todos_tecnicos = sorted(df[col_tecnico].dropna().astype(str).str.strip().unique())
                tecnicos_sel = st.multiselect("Técnicos a incluir en el reparto", todos_tecnicos, default=todos_tecnicos)

            with c2:
                edades_disp = sorted(df[col_edad].dropna().astype(str).unique())
                edades_sel = st.multiselect("Filtrar Rangos de Edad", edades_disp, default=edades_disp)
                
                prioridad_edades = st.multiselect(
                    "Prioridad de asignación (Orden de Edad):", 
                    edades_sel, 
                    default=edades_sel
                )

        # =========================
        # PROCESAMIENTO
        # =========================
        # Aplicar filtros básicos
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) &
            (df[col_edad].astype(str).isin(edades_sel))
        ].copy()

        # Establecer orden categórico por edad
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)

        # --- REGLA PH: Solo se asignan a sí mismos ---
        # Filtramos las pólizas que YA pertenecen a un PH
        df_solo_ph = df_pool[df_pool[col_tecnico].isin(unidades_ph)].copy()
        
        # Cada técnico PH se queda con sus mejores 50 (por deuda)
        df_ph_final = (
            df_solo_ph.sort_values(by="_deuda_num", ascending=False)
            .groupby(col_tecnico)
            .head(50)
        )

        # --- REPARTO GENERAL ---
        # El resto de pólizas (incluyendo las de PH que sobraron o las sin técnico)
        indices_ph_asignados = set(df_ph_final.index)
        
        # IMPORTANTE: Excluimos TODAS las pólizas que venían marcadas como PH originalmente 
        # para que no se le entreguen a técnicos integrales comunes.
        indices_todas_ph_originales = set(df_solo_ph.index)
        
        df_para_reparto = df_pool.drop(index=indices_todas_ph_originales, errors='ignore').copy()
        
        # Ordenar pool general por prioridad de edad y barrio
        df_para_reparto = df_para_reparto.sort_values(
            by=[col_edad, col_barrio, "_deuda_num"], 
            ascending=[True, True, False]
        )

        lista_final_otros = []
        puntero = 0
        tecnicos_no_ph = [t for t in tecnicos_sel if t not in unidades_ph]

        for tec in tecnicos_no_ph:
            bloque = df_para_reparto.iloc[puntero : puntero + 50].copy()
            if not bloque.empty:
                bloque[col_tecnico] = tec
                lista_final_otros.append(bloque)
                puntero += 50
            else:
                break

        # UNIÓN FINAL
        df_resultado = pd.concat([df_ph_final] + lista_final_otros, ignore_index=True)

        # MOSTRAR RESULTADOS
        with tab1:
            st.info(f"Se asignaron {len(df_ph_final)} pólizas a técnicos PH (propias) y {len(df_resultado) - len(df_ph_final)} al resto.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="Asignacion_UT.xlsx")

        with tab2:
            st.subheader("Distribución de Pólizas por Rango de Edad")
            fig = px.bar(df_resultado[col_edad].value_counts().reset_index(), x=col_edad, y="count", color=col_edad)
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
