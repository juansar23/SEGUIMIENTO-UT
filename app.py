import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Optimizado")

mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

ORDEN_EDAD_GRAFICA = ["0-30", "31-60", "61-90", "91-120", "121-360", "361-1080", "> 1080"]
col_barrio, col_ciclo, col_direccion = "BARRIO", "CICLO_FACTURACION", "DIRECCION"
col_tecnico, col_unidad, col_deuda = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO", "DEUDA_TOTAL"
col_edad, col_subcat = "RANGO_EDAD", "SUBCATEGORIA"

# --- FUNCIONES CACHEADAS PARA VELOCIDAD ---
@st.cache_data(show_spinner="Cargando y limpiando datos pesados...")
def cargar_y_limpiar(file):
    if file.name.lower().endswith((".xlsx", ".xlsm", ".xlsb")):
        df_raw = pd.read_excel(file, engine="openpyxl")
    else:
        df_raw = pd.read_excel(file, engine="xlrd")
    
    df_raw.columns = df_raw.columns.str.strip()
    # Limpieza de strings y conversión de deuda una sola vez
    df_raw[col_edad] = df_raw[col_edad].astype(str).str.strip()
    df_raw[col_subcat] = df_raw[col_subcat].astype(str).str.strip()
    df_raw["_deuda_num"] = pd.to_numeric(df_raw[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)
    return df_raw

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    df = cargar_y_limpiar(archivo)

    tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

    with tab_filtros:
        c1, c2, c3 = st.columns(3)
        with c1:
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
            ciclos_sel = st.multiselect("Ciclos", sorted(df[col_ciclo].dropna().unique().astype(str)), default=df[col_ciclo].dropna().unique().astype(str))
        with c2:
            subcat_sel = st.multiselect("Subcategoría", sorted(df[col_subcat].unique()), default=df[col_subcat].unique())
            edades_disp = [e for e in ORDEN_EDAD_GRAFICA if e in df[col_edad].unique()]
            prioridad_edades = st.multiselect("Prioridad de Edad:", edades_disp, default=edades_disp)
        with c3:
            nombres_ph = list(mapeo_ph.values())
            tecs_unicos = df[col_tecnico].dropna().unique()
            tecnicos_reparto = sorted([t for t in tecs_unicos if t not in nombres_ph])
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecnicos_reparto, default=tecnicos_reparto)

    # --- PROCESAMIENTO OPTIMIZADO ---
    if st.button("🚀 Procesar Asignación"):
        # Filtrado veloz
        mask = (df[col_ciclo].astype(str).isin(ciclos_sel)) & (df[col_edad].isin(prioridad_edades)) & (df[col_subcat].isin(subcat_sel))
        df_pool = df[mask].copy()
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)

        # 1. PH
        df_ph_final = pd.DataFrame()
        indices_ph = set()
        if not excluir_ph:
            list_ph = []
            for unidad, func in mapeo_ph.items():
                p_ph = df_pool[df_pool[col_unidad] == unidad].sort_values([col_edad, "_deuda_num"], ascending=[True, False]).head(50)
                if not p_ph.empty:
                    p_ph[col_tecnico] = func
                    list_ph.append(p_ph)
                    indices_ph.update(p_ph.index)
            if list_ph: df_ph_final = pd.concat(list_ph)

        # 2. REPARTO GENERAL (Optimizado para no filtrar en bucle)
        df_otros = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys()) & ~df_pool.index.isin(indices_ph)].copy()
        df_otros = df_otros.sort_values([col_edad, col_ciclo, col_barrio, col_direccion])
        
        # Convertimos a lista de diccionarios para iteración ultra rápida
        pols_disponibles = df_otros.to_dict('records')
        lista_final_otros = []
        idx_pols = 0
        total_pols = len(pols_disponibles)

        for tec in tecnicos_sel:
            cupo = 50
            while cupo > 0 and idx_pols < total_pols:
                # Lógica de bloque de barrio
                barrio_actual = pols_disponibles[idx_pols][col_barrio]
                temp_bloque = []
                
                # Buscamos pólizas del mismo barrio consecutivas (ya están ordenadas)
                while idx_pols < total_pols and pols_disponibles[idx_pols][col_barrio] == barrio_actual and cupo > 0:
                    row = pols_disponibles[idx_pols]
                    row[col_tecnico] = tec
                    temp_bloque.append(row)
                    idx_pols += 1
                    cupo -= 1
                
                if temp_bloque:
                    lista_final_otros.extend(temp_bloque)

        df_final_reparto = pd.DataFrame(lista_final_otros)
        df_resultado = pd.concat([df_ph_final, df_final_reparto], ignore_index=True) if not df_final_reparto.empty else df_ph_final

        # --- VISTAS ---
        with tab1:
            if not df_resultado.empty:
                st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
                output = io.BytesIO()
                df_resultado.drop(columns=["_deuda_num"]).to_excel(output, index=False, engine='openpyxl')
                st.download_button("📥 Descargar Excel", output.getvalue(), "Asignacion_Final.xlsx")

        with tab2:
            if not df_resultado.empty:
                # Gráfica Rango Edad
                st.subheader("📊 Pólizas por Rango de Edad")
                conteo_edad = df_resultado[col_edad].value_counts().reset_index()
                fig_edad = px.bar(conteo_edad, x=col_edad, y="count", color=col_edad, 
                                  category_orders={col_edad: ORDEN_EDAD_GRAFICA}, text_auto=True)
                st.plotly_chart(fig_edad, use_container_width=True)

                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    st.subheader("🏆 Top 10 Técnicos (Deuda)")
                    rank = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                    st.table(rank.style.format({"_deuda_num": "$ {:,.0f}"}))
                with c_d2:
                    st.subheader("🥧 Subcategoría")
                    st.plotly_chart(px.pie(df_resultado, names=col_subcat), use_container_width=True)
