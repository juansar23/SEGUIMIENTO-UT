import streamlit as st
import pandas as pd
import io
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Gestión de Inventario UT", layout="wide")

# --- ESTADO DE LA SESIÓN (Para guardar las salidas temporalmente) ---
if 'historico_salidas' not in st.session_state:
    st.session_state.historico_salidas = pd.DataFrame(
        columns=["Fecha", "Material", "Cantidad", "Entregado A", "Técnico Responsable"]
    )

st.title("📦 Sistema de Control: Entradas y Salidas UT")

archivo = st.file_uploader("1️⃣ Cargar Inventario Inicial (Excel)", type=["xlsx"])

if archivo:
    # Cargar datos
    df_original = pd.read_excel(archivo)
    df_original.columns = df_original.columns.str.strip()
    
    # Identificar columna de material/subcategoría
    col_sub = next((c for c in df_original.columns if c.lower() in ["subcategoría", "subcategoria"]), None)
    
    if not col_sub:
        st.error("No se encontró la columna 'Subcategoría' en el Excel.")
        st.stop()

    # --- TABS PRINCIPALES ---
    tab_inv, tab_salida, tab_historial = st.tabs(["📋 Inventario Actual", "📤 Registrar Salida", "📜 Historial de Entregas"])

    # ==================================================
    # TAB 1: INVENTARIO ACTUAL (ENTRADAS)
    # ==================================================
    with tab_inv:
        st.subheader("Estado actual de materiales")
        
        # Calcular Stock (Entradas - Salidas)
        resumen_entradas = df_original.groupby(col_sub).size().reset_index(name='Entradas')
        resumen_salidas = st.session_state.historico_salidas.groupby("Material")["Cantidad"].sum().reset_index()
        resumen_salidas.columns = [col_sub, "Salidas"]
        
        stock_df = pd.merge(resumen_entradas, resumen_salidas, on=col_sub, how="left").fillna(0)
        stock_df["Stock Disponible"] = stock_df["Entradas"] - stock_df["Salidas"]
        
        # Métricas rápidas
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Entradas", int(stock_df["Entradas"].sum()))
        c2.metric("Total Salidas", int(stock_df["Salidas"].sum()), delta_color="inverse")
        c3.metric("Disponible", int(stock_df["Stock Disponible"].sum()))
        
        st.dataframe(stock_df, use_container_width=True)

    # ==================================================
    # TAB 2: REGISTRAR SALIDA (EL FORMULARIO)
    # ==================================================
    with tab_salida:
        st.subheader("📝 Formulario de Entrega de Material")
        
        with st.form("form_salida"):
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                # El usuario elige de lo que existe en el Excel cargado
                lista_materiales = sorted(df_original[col_sub].unique())
                material_sel = st.selectbox("Seleccionar Material", lista_materiales)
                
                cantidad = st.number_input("Cantidad a entregar", min_value=1, step=1)
            
            with col_f2:
                # Quién recibe (pueden ser los Técnicos Integrales del Excel)
                lista_tecnicos = sorted(df_original["TECNICOS INTEGRALES"].unique()) if "TECNICOS INTEGRALES" in df_original.columns else []
                entregado_a = st.text_input("Nombre de quien recibe")
                responsable = st.selectbox("Técnico que autoriza/entrega", lista_tecnicos)

            fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
            
            btn_registrar = st.form_submit_button("Confirmar Salida")

            if btn_registrar:
                # Validar stock disponible antes de registrar
                disp = stock_df[stock_df[col_sub] == material_sel]["Stock Disponible"].values[0]
                
                if cantidad > disp:
                    st.error(f"❌ Error: Solo quedan {int(disp)} unidades de {material_sel}.")
                else:
                    # Guardar en el historial (session_state)
                    nueva_salida = {
                        "Fecha": fecha_entrega,
                        "Material": material_sel,
                        "Cantidad": cantidad,
                        "Entregado A": entregado_a,
                        "Técnico Responsable": responsable
                    }
                    st.session_state.historico_salidas = pd.concat([
                        st.session_state.historico_salidas, 
                        pd.DataFrame([nueva_salida])
                    ], ignore_index=True)
                    
                    st.success(f"✅ Registrada salida de {cantidad} {material_sel} a {entregado_a}")
                    st.rerun()

    # ==================================================
    # TAB 3: HISTORIAL Y EXPORTACIÓN
    # ==================================================
    with tab_historial:
        st.subheader("Registros de Salidas Realizadas")
        
        if st.session_state.historico_salidas.empty:
            st.info("No hay salidas registradas todavía.")
        else:
            st.dataframe(st.session_state.historico_salidas, use_container_width=True)
            
            # Botón para descargar el reporte de salidas
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.historico_salidas.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Reporte de Salidas",
                data=output.getvalue(),
                file_name=f"salidas_material_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("👋 Por favor, sube el archivo Excel de inventario para habilitar el registro de salidas.")
