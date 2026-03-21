import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización Logística")

# --- SIDEBAR: CONFIGURACIÓN Y FILTROS ---
st.sidebar.header("⚙️ Configuración y Filtros")

# Soporte para archivos .xls antiguos y .xlsx modernos
archivo = st.sidebar.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

# Nombres de columnas ajustados
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"
col_subcat = "SUBCATEGORIA"

if archivo:
    try:
        # 1. LECTURA CON MOTORES ESPECÍFICOS
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()

        # Validar columnas necesarias
        cols_req = [col_tecnico, col_deuda, col_barrio, col_ciclo, col_direccion, col_edad, col_subcat]
        for c in cols_req:
            if c not in df.columns:
                st.error(f"❌ Falta la columna: {c}")
                st.stop()

        # 2. LIMPIEZA DE DATOS
        for col in [col_tecnico, col_barrio, col_ciclo, col_direccion, col_edad, col_subcat]:
            df[col] = df[col].astype(str).str.strip()

        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # 3. FILTROS DINÁMICOS EN SIDEBAR
        st.sidebar.subheader("🎯 Criterios de Selección")
        
        ciclos_disp = sorted(df[col_ciclo].unique())
        ciclos_sel = st.sidebar.multiselect("Ciclo Facturación", ciclos_disp, default=ciclos_disp)
        
        rangos_sel = st.sidebar.multiselect("Rango Edad", sorted(df[col_edad].unique()), default=df[col_edad].unique())
        sub_sel = st.sidebar.multiselect("Subcategoría", sorted(df[col_subcat].unique()), default=df[col_subcat].unique())
        
        deuda_min = st.sidebar.number_input("Deuda mayor a:", min_value=0, value=0, step=50000)

        # Filtro de Técnicos con Modo Exclusión
        st.sidebar.subheader("👥 Técnicos")
        todos_tecnicos = sorted(df[col_tecnico].unique())
        modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")

        if modo_exclusion:
            excluir = st.sidebar.multiselect("Excluir técnicos:", todos_tecnicos)
            tecnicos_final = [t for t in todos_tecnicos if t not in excluir]
        else:
            tecnicos_final = st.sidebar.multiselect("Incluir técnicos:", todos_tecnicos, default=todos_tecnicos)

        # APLICAR FILTROS
        df_base = df[
            (df[col_ciclo].isin(ciclos_sel)) &
            (df[col_edad].isin(rangos_sel)) &
            (df[col_subcat].isin(sub_sel)) &
            (df["_deuda_num"] >= deuda_min) &
            (df[col_tecnico].isin(tecnicos_final))
        ].copy()

        # 4. LÓGICA DE PROCESAMIENTO (PH vs RUTA)
        unidades_ph = ["ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH", 
                       "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", "ITA SUSPENSION BQ 37 PH"]

        df_ph = df_base[df_base[col_tecnico].isin(unidades_ph)].copy()
        df_ph_final = df_ph.sort_values(by="_deuda_num", ascending=False).groupby(col_tecnico).head(50)

        df_otros = df_base[~df_base[col_tecnico].isin(unidades_ph)].copy()
        lista_rutas = []
        for tec, grupo in df_otros.groupby(col_tecnico):
            ordenado = grupo.sort_values(by=[col_ciclo, col_barrio, col_direccion])
            lista_rutas.append(ordenado.head(50))
        
        df_resultado = pd.concat([df_ph_final] + lista_rutas, ignore_index=True) if (not df_ph_final.empty or lista_rutas) else pd.DataFrame()

        # 5. TABS Y VISUALIZACIÓN
        tab1, tab2 = st.tabs(["📋 Tabla de Asignación", "📊 Dashboard Ejecutivo"])

        with tab1:
            st.success(f"✅ Se han asignado {len(df_resultado)} pólizas optimizadas.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)

            if not df_resultado.empty:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Ruta_Optimizada")
                
                st.sidebar.markdown("---")
                st.sidebar.download_button("📥 Descargar Reporte Final", data=output.getvalue(), file_name="Ruta_UT_Optimizada.xlsx")

        with tab2:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Pólizas", len(df_resultado))
            c2.metric("Deuda Total", f"$ {df_resultado['_deuda_num'].sum():,.0f}")
            c3.metric("Barrios", df_resultado[col_barrio].nunique())

            st.divider()

            col_l, col_r = st.columns(2)
            with col_l:
                # REQUERIMIENTO: TOP 10 EN TABLA
                st.subheader("🏆 Top 10 Técnicos (Mayor Deuda)")
                top_deuda = (
                    df_resultado.groupby(col_tecnico)["_deuda_num"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                    .reset_index()
                )
                top_deuda.columns = ["Técnico", "Deuda Total"]
                # Formatear la deuda para lectura fácil
                top_deuda["Deuda Total"] = top_deuda["Deuda Total"].apply(lambda x: f"$ {x:,.0f}")
                st.table(top_deuda) 

            with col_r:
                st.subheader("🥧 Distribución por Subcategoría")
                fig2 = px.pie(df_resultado, names=col_subcat, hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)

            st.subheader("📊 Pólizas por Rango de Edad")
            fig3 = px.histogram(df_resultado, x=col_edad, color=col_edad)
            st.plotly_chart(fig3, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error al procesar: {e}")
else:
    st.info("👆 Por favor, sube el archivo Excel para comenzar.")
