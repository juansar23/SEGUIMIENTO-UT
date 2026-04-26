import streamlit as st
import pandas as pd
import io

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación con Intercambio")

# Mapeo de Unidades PH
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Nombres de columnas esperados en MAYÚSCULAS
COL_BARRIO, COL_CICLO = "BARRIO", "CICLO_FACTURACION"
COL_TECNICO, COL_UNIDAD = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO"
COL_DEUDA, COL_EDAD = "DEUDA_TOTAL", "RANGO_EDAD"
COL_SUBCAT = "SUBCATEGORIA"

@st.cache_data(ttl=3600)
def cargar_base_segura(file):
    try:
        df_raw = pd.read_excel(file)
    except:
        df_raw = pd.read_excel(file, engine="openpyxl")
    
    # Limpieza de columnas para evitar el KeyError
    df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
    
    # Crear columna auxiliar de origen asegurando que sea string
    if COL_TECNICO in df_raw.columns:
        df_raw["TEC_ORI"] = df_raw[COL_TECNICO].astype(str).str.strip()
    
    return df_raw

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xlsx", "xlsb"])

if archivo:
    df = cargar_base_segura(archivo)
    
    if COL_TECNICO not in df.columns:
        st.error(f"No se encontró la columna '{COL_TECNICO}'. Verifica tu Excel.")
        st.stop()

    tab_filtros, tab_resultado, tab_dashboard = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

    with tab_filtros:
        # Checkbox de exclusión PH
        excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            ciclos_disp = sorted(df[COL_CICLO].dropna().unique().astype(str))
            ciclos_sel = st.multiselect("Ciclos", ciclos_disp, default=ciclos_disp)
            
            subcat_disp = sorted(df[COL_SUBCAT].dropna().unique().astype(str))
            subcat_sel = st.multiselect("Subcategoría", subcat_disp, default=subcat_disp)

        with c2:
            edades_disp = sorted(df[COL_EDAD].dropna().unique().astype(str))
            prioridad_edades = st.multiselect("Prioridad de Edad:", edades_disp, default=edades_disp)

        with c3:
            nombres_ph = list(mapeo_ph.values())
            # CORRECCIÓN DEL ERROR DE ORDENAMIENTO (sorted)
            # Convertimos a string cada elemento antes de comparar para evitar el TypeError
            tecs_unicos = [str(t) for t in df["TEC_ORI"].unique() if str(t).lower() != "nan"]
            tecs_reparto = sorted([t for t in tecs_unicos if t not in nombres_ph])
            
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecs_reparto, default=tecs_reparto)
        
        procesar = st.button("🚀 Procesar Asignación")

    if procesar:
        # Filtrado inicial
        mask = (
            df[COL_CICLO].astype(str).isin(ciclos_sel) & 
            df[COL_EDAD].astype(str).isin(prioridad_edades) &
            df[COL_SUBCAT].astype(str).isin(subcat_sel)
        )
        df_f = df[mask].copy()
        
        # 1. Manejo de PH (Blindados)
        df_ph_final = pd.DataFrame()
        indices_ph = set()
        if not excluir_ph:
            list_ph = []
            for und, tec in mapeo_ph.items():
                p_ph = df_f[df_f[COL_UNIDAD] == und].head(50)
                if not p_ph.empty:
                    p_ph[COL_TECNICO] = tec
                    list_ph.append(p_ph)
                    indices_ph.update(p_ph.index)
            if list_ph:
                df_ph_final = pd.concat(list_ph)
        
        # 2. Reparto General con Intercambio
        df_gen = df_f[~df_f[COL_UNIDAD].isin(mapeo_ph.keys()) & ~df_f.index.isin(indices_ph)].copy()
        df_gen = df_gen.sort_values([COL_EDAD, COL_BARRIO], ascending=[False, True])
        
        final_reparto = []
        asignados = set()
        
        for tec in tecnicos_sel:
            # Buscamos 50 pólizas donde el dueño original NO sea el técnico actual
            pool = df_gen[(df_gen["TEC_ORI"] != tec) & (~df_gen.index.isin(asignados))].head(50)
            if not pool.empty:
                pool[COL_TECNICO] = tec
                final_reparto.append(pool)
                asignados.update(pool.index)
        
        # Combinar resultados
        if not df_ph_final.empty or final_reparto:
            df_resultado = pd.concat([df_ph_final] + final_reparto, ignore_index=True)
            
            with tab_resultado:
                st.success(f"Asignación lista: {len(df_resultado)} registros.")
                # Quitamos la columna auxiliar antes de mostrar y descargar
                df_mostrar = df_resultado.drop(columns=["TEC_ORI"])
                st.dataframe(df_mostrar, use_container_width=True)
                
                output = io.BytesIO()
                df_mostrar.to_excel(output, index=False, engine="openpyxl")
                st.download_button("📥 Descargar Excel", output.getvalue(), "Asignacion_Final.xlsx")
        else:
            st.warning("No hay datos que coincidan con los filtros seleccionados.")
