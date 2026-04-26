import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Sistema ITA - Reparto Geográfico", layout="wide")
st.title("📊 Asignación Geográfica por Bloques")

# Mapeo PH (Blindados)
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN",
    "ITA SUSPENSION BQ 26":"STIVEN ENRRIQUE DIAZ VELASQUEZ", 


}

# Columnas (con normalización robusta)
COL_BARRIO, COL_CICLO = "BARRIO", "CICLO_FACTURACION"
COL_TECNICO, COL_UNIDAD = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO"
COL_DIRECCION, COL_EDAD = "DIRECCION", "RANGO_EDAD"

@st.cache_data(ttl=3600)
def cargar_datos(file):
    df = pd.read_excel(file)
    df.columns = [str(c).strip().upper() for c in df.columns]
    # Guardamos técnico original para el filtro de "no repetir"
    df["TEC_ORI"] = df[COL_TECNICO].astype(str).str.strip()
    return df

archivo = st.file_uploader("Subir Archivo", type=["xlsx"])

if archivo:
    df = cargar_datos(archivo)
    
    tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Resultado"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            excluir_ph = st.checkbox("🚫 EXCLUIR PH (No reasignar)", value=True)
            contingencia = st.radio("Si faltan pólizas para todos:", ["Detener asignación", "Ignorar restricción de no repetir barrio"], help="Si se acaban las pólizas de otros barrios, ¿quieres que los técnicos tomen las suyas?")
        with c2:
            tecs_disponibles = sorted([str(t) for t in df["TEC_ORI"].unique() if str(t).lower() != "nan" and t not in mapeo_ph.values()])
            tecnicos_sel = st.multiselect("Técnicos de Reparto", tecs_disponibles, default=tecs_disponibles)
        
        procesar = st.button("🚀 Iniciar Reparto Geográfico")

    if procesar:
        # 1. ORDENAMIENTO JERÁRQUICO (Ciclo -> Barrio -> Dirección)
        df_work = df.sort_values([COL_CICLO, COL_BARRIO, COL_DIRECCION]).copy()
        
        # 2. Separar PH
        df_ph = pd.DataFrame()
        indices_ph = set()
        if not excluir_ph:
            df_ph = df_work[df_work[COL_UNIDAD].isin(mapeo_ph.keys())].copy()
            for und, tec in mapeo_ph.items():
                df_ph.loc[df_ph[COL_UNIDAD] == und, COL_TECNICO] = tec
            indices_ph = set(df_ph.index)

        # 3. Preparar Reparto General
        df_gen = df_work[~df_work.index.isin(indices_ph)].copy()
        asignados = set()
        lista_resultados = []

        # Lógica de Consumo por Bloques
        for tec in tecnicos_sel:
            cupo = 50
            while cupo > 0:
                # Filtrar disponibles
                candidatos = df_gen[~df_gen.index.isin(asignados)]
                
                if candidatos.empty: break # No hay más trabajo
                
                # Política: ¿Ignorar restricción?
                if contingencia == "Detener asignación":
                    candidatos = candidatos[candidatos["TEC_ORI"] != tec]
                
                if candidatos.empty: break # Nadie más puede tomar esto
                
                # Identificar el barrio actual del primer candidato
                barrio_actual = candidatos.iloc[0][COL_BARRIO]
                bloque_barrio = candidatos[candidatos[COL_BARRIO] == barrio_actual]
                
                # ¿Cuánto tomamos?
                cantidad_a_tomar = min(len(bloque_barrio), cupo)
                seleccion = bloque_barrio.head(cantidad_a_tomar).copy()
                
                # Asignar
                seleccion[COL_TECNICO] = tec
                lista_resultados.append(seleccion)
                asignados.update(seleccion.index)
                cupo -= len(seleccion)

        with tab2:
            df_final = pd.concat([df_ph] + lista_resultados, ignore_index=True)
            st.success(f"Asignación completa: {len(df_final)} registros.")
            st.dataframe(df_final.drop(columns=["TEC_ORI"]))
            
            # Descarga
            towrite = io.BytesIO()
            df_final.drop(columns=["TEC_ORI"]).to_excel(towrite, index=False)
            st.download_button("📥 Descargar", towrite.getvalue(), "Asignacion_Geografica.xlsx")
