import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación por Bloque de Barrios")

# Mapeo de Unidades PH (Blindado con tu tabla)
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALAMRALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Definición del Orden Estricto para la Gráfica de Edad
ORDEN_EDAD_GRAFICA = [
    "0-30",
    "31-60",
    "61-90",
    "91-120",
    "121-360",
    "361-1080",
    "> 1080"
]

# Columnas
col_barrio, col_ciclo, col_direccion = "BARRIO", "CICLO_FACTURACION", "DIRECCION"
col_tecnico, col_unidad, col_deuda = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO", "DEUDA_TOTAL"
col_edad, col_subcat = "RANGO_EDAD", "SUBCATEGORIA"

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    try:
        # 1. LECTURA
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")
            
        df.columns = df.columns.str.strip()
        
        # Limpieza deuda para cálculos
        df["_deuda_num"] = pd.to_numeric(df[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)

        # Forzar la columna de edad como categoría para el ordenamiento global
        # (Esto asegura que el filtro de multiselect en Configuración respete el orden lógico)
        df[col_edad] = df[col_edad].astype(str).str.strip()
        
        tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

        with tab_filtros:
            st.subheader("⚙️ Configuración de Reparto")
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
            
            st.divider()
            
            c1, c2, c3 = st.columns(3)
            with c1:
                ciclos_sel = st.multiselect("Filtrar Ciclos", sorted(df[col_ciclo].dropna().unique().astype(str)), default=df[col_ciclo].dropna().unique().astype(str))
                subcat_sel = st.multiselect("Filtrar Subcategoría", sorted(df[col_subcat].dropna().unique().astype(str)), default=df[col_subcat].dropna().unique().astype(str))
            
            with c2:
                # Usamos el orden estricto definido arriba para el filtro de edades
                edades_disp = [e for e in ORDEN_EDAD_GRAFICA if e in df[col_edad].unique()]
                prioridad_edades = st.multiselect(
                    "3. Prioridad de Edad (Mueve para ordenar importancia):", 
                    edades_disp, 
                    default=edades_disp,
                    help="Las pólizas se asignarán primero a los rangos que pongas arriba."
                )
            
            with c3:
                nombres_ph = list(mapeo_ph.values())
                tecnicos_reparto = sorted([t for t in df[col_tecnico].dropna().unique() if t not in nombres_ph])
                tecnicos_sel = st.multiselect("Técnicos Integrales para Reparto General", tecnicos_reparto, default=tecnicos_reparto)

        # =========================
        # PROCESAMIENTO
        # =========================
        # 1. Filtrado pool por Ciclo y Edad seleccionados
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) & 
            (df[col_edad].astype(str).isin(prioridad_edades)) &
            (df[col_subcat].astype(str).isin(subcat_sel))
        ].copy()

        # 2. Aplicar ORDEN DE PRIORIDAD por Edad y Deuda
        # Esto hace que las pólizas "más importantes" queden arriba de todo el archivo
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)
        #df_pool = df_pool.sort_values(by=[col_edad, "_deuda_num"], ascending=[True, False])

        # --- SECCIÓN PH (Lógica Estricta) ---
        df_ph_final = pd.DataFrame()
        if not excluir_ph:
            df_ph_final_list = []
            for unidad, funcionario in mapeo_ph.items():
                # Buscamos en el pool ya ordenado por edad/deuda
                pool_ph = df_pool[df_pool[col_unidad] == unidad].copy()
                if not pool_ph.empty:
                    # Toma las 50 mejores respetando la prioridad de edad que pusiste arriba
                    asignacion_ph = pool_ph.sort_values(by=[col_edad, "_deuda_num"], ascending=[True, False]).head(50) 
                    asignacion_ph[col_tecnico] = funcionario
                    df_ph_final_list.append(asignacion_ph)
            
            if df_ph_final_list:
                df_ph_final = pd.concat(df_ph_final_list)

        # --- SECCIÓN REPARTO GENERAL (LOGICA BLOQUE DE BARRIOS) ---
        # Excluimos las unidades PH para que no se mezclen con el reparto general
        df_otros = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys())].copy()
        
        # ORDEN CRÍTICO PARA BLOQUE DE BARRIOS: Prioridad Edad -> Ciclo -> Barrio -> Dirección
        df_otros = df_otros.sort_values(
            by=[col_edad, col_ciclo, col_barrio, col_direccion], 
            ascending=[True, True, True, True]
        )

        lista_final_otros = []
        indices_asignados = set(df_ph_final.index) if not df_ph_final.empty else set()

        for tec in tecnicos_sel:
            cupo = 50
            
            # Filtrar las pólizas disponibles que NO hayan sido asignadas
            pols_libres = df_otros[~df_otros.index.isin(indices_asignados)]
            
            # Lógica de Bloque de Barrios (mientras haya cupo y pólizas disponibles)
            while cupo > 0 and not pols_libres.empty:
                # Tomamos el barrio del primer registro libre (respetando el orden geográfico/prioridad)
                barrio_actual = pols_libres.iloc[0][col_barrio]
                
                # Tomamos el bloque del mismo barrio hasta completar el cupo del técnico
                bloque_barrio = pols_libres[pols_libres[col_barrio] == barrio_actual].head(cupo).copy()
                
                if not bloque_barrio.empty:
                    bloque_barrio[col_tecnico] = tec
                    lista_final_otros.append(bloque_barrio)
                    indices_asignados.update(bloque_barrio.index)
                    
                    # Actualizamos el cupo del técnico y las pólizas disponibles
                    cupo -= len(bloque_barrio)
                    pols_libres = df_otros[~df_otros.index.isin(indices_asignados)]
                else:
                    # Si no hay bloque (error inesperado), rompemos el bucle
                    break

        # UNIÓN FINAL
        final_list = []
        if not df_ph_final.empty: final_list.append(df_ph_final)
        if lista_final_otros: final_list.extend(lista_final_otros)
        
        if final_list:
            df_resultado = pd.concat(final_list, ignore_index=True)
        else:
            df_resultado = pd.DataFrame()

        # =========================
        # VISTAS
        # =========================
        with tab1:
            if not df_resultado.empty:
                st.success(f"Asignación generada con éxito respetando prioridades de edad y bloque geográfico de barrios.")
                st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel de Asignación", data=output.getvalue(), file_name="Asignacion_UT_Priorizada_Barrios.xlsx")
            else:
                st.warning("No hay pólizas que coincidan con los filtros seleccionados.")

        with tab2:
            if not df_resultado.empty:
                st.subheader("Pólizas Asignadas por Rango de Edad")
                
                # --- GRÁFICA DE EDAD CON ORDEN ESTRICTO ---
                # 1. Crear conteo
                conteo_edad = df_resultado[col_edad].value_counts().reset_index()
                conteo_edad.columns = [col_edad, "cantidad"]
                
                # 2. Reindexar basándonos en el orden estricto (eliminando los que no existen)
                edades_existentes = [e for e in ORDEN_EDAD_GRAFICA if e in df_resultado[col_edad].unique()]
                conteo_edad = conteo_edad.set_index(col_edad).reindex(edades_existentes).reset_index()
                
                # 3. Mostrar Gráfica
                fig_edad = px.bar(
                    conteo_edad, 
                    x=col_edad, 
                    y="cantidad", 
                    color=col_edad, 
                    text_auto=True,
                    category_orders={col_edad: ORDEN_EDAD_GRAFICA} # Forzamos el orden en el eje X
                )
                st.plotly_chart(fig_edad, use_container_width=True)
                
                st.divider()
                
                col_d1, col_d2 = st.columns(2)
                
                with col_d1:
                    st.subheader("🏆 Top 10 Técnicos (Deuda Asignada)")
                    ranking = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                    ranking.columns = ["Técnico", "Deuda Total"]
                    st.table(ranking.style.format({"Deuda Total": "$ {:,.0f}"}))

                with col_d2:
                    st.subheader("🥧 Distribución por Subcategoría")
                    fig_pie = px.pie(df_resultado, names=col_subcat, hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)

    except Exception as e:
        st.error(f"Se produjo un error durante el procesamiento del archivo: {e}")
else:
    st.info("👋 Por favor, sube un archivo Excel (Seguimiento) para comenzar.")
