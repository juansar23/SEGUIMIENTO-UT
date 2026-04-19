import streamlit as st
import pandas as pd
import io

# Configuración de página
st.set_page_config(page_title="Sistema ITA - Reparto Seguro", layout="wide")
st.title("📊 Asignación con Intercambio Obligatorio")

# Unidades PH que NO deben intercambiar
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

col_barrio, col_ciclo, col_tecnico = "BARRIO", "CICLO_FACTURACION", "TECNICOS_INTEGRALES"
col_unidad, col_deuda, col_edad = "UNIDAD_TRABAJO", "DEUDA_TOTAL", "RANGO_EDAD"

@st.cache_data(ttl=3600)
def procesar_base_ligera(file):
    # Usamos motor calamine si está disponible, sino el estándar
    try:
        df_raw = pd.read_excel(file, engine="calamine")
    except:
        df_raw = pd.read_excel(file)
    
    df_raw.columns = df_raw.columns.str.strip()
    # Guardamos técnico original para validar intercambio
    df_raw["TEC_ORI"] = df_raw[col_tecnico].astype(str).str.strip()
    df_raw[col_edad] = df_raw[col_edad].astype(str).str.strip()
    df_raw["_val"] = pd.to_numeric(df_raw[col_deuda].astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce").fillna(0)
    return df_raw

archivo = st.file_uploader("Subir Seguimiento", type=["xlsx", "xlsb"])

if archivo:
    df = procesar_base_ligera(archivo)
    
    # Filtros en el sidebar para ahorrar espacio central
    with st.sidebar:
        st.header("Filtros")
        ciclos = st.multiselect("Ciclos", df[col_ciclo].unique(), default=df[col_ciclo].unique())
        edades = st.multiselect("Edades", df[col_edad].unique(), default=df[col_edad].unique())
        nombres_ph = list(mapeo_ph.values())
        tecs_reparto = sorted([t for t in df["TEC_ORI"].unique() if t not in nombres_ph and t != "nan"])
        tecs_sel = st.multiselect("Técnicos a Intercambiar", tecs_reparto, default=tecs_reparto)

    if st.button("🚀 Iniciar Reparto"):
        # Filtrado
        df_f = df[(df[col_ciclo].isin(ciclos)) & (df[col_edad].isin(edades))].copy()
        
        # 1. Separar PH (Mantienen sus barrios por regla operativa)
        df_ph = df_f[df_f[col_unidad].isin(mapeo_ph.keys())].copy()
        for und, tec in mapeo_ph.items():
            df_ph.loc[df_ph[col_unidad] == und, col_tecnico] = tec
        
        # 2. Reparto General con Intercambio (Adrian y resto)
        df_gen = df_f[~df_f[col_unidad].isin(mapeo_ph.keys())].copy()
        df_gen = df_gen.sort_values([col_edad, col_barrio], ascending=[False, True])
        
        final_rows = []
        asignados = set()
        
        # Bucle optimizado: Evita el mismo barrio original
        for tec in tecs_sel:
            # Filtrar lo que no es de él y no ha sido asignado
            pool = df_gen[(df_gen["TEC_ORI"] != tec) & (~df_gen.index.isin(asignados))].head(50)
            if not pool.empty:
                pool[col_tecnico] = tec
                final_rows.append(pool)
                asignados.update(pool.index)
        
        # Unificar
        if final_rows:
            df_resultado = pd.concat([df_ph] + final_rows)
            st.success(f"Asignación lista: {len(df_resultado)} filas.")
            st.dataframe(df_resultado.head(100)) # Solo mostrar preview para no saturar
            
            # Descarga
            towrite = io.BytesIO()
            df_resultado.to_excel(towrite, index=False, engine="openpyxl")
            st.download_button("📥 Descargar Excel", towrite.getvalue(), "Asignacion_Final.xlsx")
        else:
            st.warning("No se pudieron realizar intercambios con los filtros seleccionados.")
