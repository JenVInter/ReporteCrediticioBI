import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import pandas as pd
import re
import aiohttp
import asyncio
import numpy as np

# Función para limpiar el texto en un DataFrame
def LimpiarText(df):
    df = df.map(lambda x: re.sub('S.A.', 'SA', x))  
    df = df.map(lambda x: re.sub("'", '', x))
    df = df.map(lambda x: re.sub('[^\w\s]', ' ', x))
    df = df.map(lambda x: re.sub("\s+", ' ', x))
    df = df.apply(lambda x: x.strip())
    return df

# Función para obtener un driver de Selenium con configuraciones específicas

def get_driver():
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    options.binary_location = '/usr/bin/chromium'  # Asegúrate de apuntar al binario correcto de Chromium
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Función asincrónica para realizar una solicitud POST a una API judicial
async def post_request_funcion_judicial(cedula_demandado):
    url = "https://api.funcionjudicial.gob.ec/EXPEL-CONSULTA-CAUSAS-SERVICE/api/consulta-causas/informacion/buscarCausas"
    
    payload = {
        "numeroCausa": "",
        "actor": {
            "cedulaActor": "",
            "nombreActor": ""
        },
        "demandado": {
            "cedulaDemandado": cedula_demandado,
            "nombreDemandado": ""
        },
        "provincia": "",
        "numeroFiscalia": "",
        "recaptcha": "verdad",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response.raise_for_status()

# Función para crear un DataFrame con la información judicial obtenida
def create_dataframe_funcion_judicial(data):
    df = pd.DataFrame(data)
    df_filtered = df[['idJuicio', 'estadoActual', 'fechaIngreso', 'nombreDelito']]
    df_filtered.columns = ['ID Juicio', 'Estado Actual', 'Fecha Ingreso', 'Nombre Delito']
    df_filtered.loc[:, 'Fecha Ingreso'] = pd.to_datetime(df_filtered['Fecha Ingreso'], errors='coerce').dt.strftime('%d/%m/%Y')
    return df_filtered

# Función asincrónica para realizar la consulta SRI
async def consulta_sri(Id):
    driver = get_driver()
    try:
        url_sri = 'https://srienlinea.sri.gob.ec/sri-en-linea/SriDeclaracionesWeb/ConsultaImpuestoRenta/Consultas/consultaImpuestoRenta'
        driver.get(url_sri)
        await asyncio.sleep(2)

        Idsri = '1722431101001'
        contr = 'Victor2022*'

        # Rellenar campos de usuario y contraseña
        proc_sri = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='usuario']")))
        proc_sri.send_keys(Idsri)

        proc_sri_ctr = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='password']")))
        proc_sri_ctr.send_keys(contr)

        # Hacer clic en el botón de login
        login_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='kc-login']")))
        driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
        driver.execute_script("arguments[0].click();", login_button)
        await asyncio.sleep(3)

        elemento_busqueda = driver.find_element(By.XPATH, "//input[@id='busquedaRucId']")
        elemento_busqueda.click()
        elemento_busqueda.send_keys(Id)
        await asyncio.sleep(5)

        ProcSRIclick = driver.find_element(By.XPATH, "/html/body/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/div[6]/div[2]/div/div[2]/div/button")
        ProcSRIclick.click()
        await asyncio.sleep(3)

        InfoCausas = driver.find_element(By.XPATH, '//*[@id="sribody"]/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/sri-mostrar-impuesto-renta/div[5]/div[1]/div')
        lineas = InfoCausas.text.split('\n')
        datos = [linea.split('\t') for linea in lineas]
        df = pd.DataFrame(datos)

        n_registros_sri = df.iloc[0].apply(lambda x: x.split('-')[-1].strip())
        df = df[~df.isin(['ui-btn','Detalle de valores - 8 registros','Impuesto a la Renta Causado Régimen General','Otros Regímenes','Formulario']).any(axis=1)]
        df.iloc[[1, 2]] = df.iloc[[2, 1]].values
        df = df.iloc[:-2]

        df_final_sri = pd.DataFrame()
        nuevo_nombre_columnas = df.iloc[:3].astype(str).T.values.flatten().tolist()
        df = df[3:].reset_index(drop=True)
        df = df.replace('USD', '', regex=True)
        df = df.replace(',', '.', regex=True)
        grupos_filas = [df.iloc[i:i+3, :] for i in range(0, len(df), 3)]
        grupos_transpuestos = [grupo.T for grupo in grupos_filas]

        for grupo_transpuesto in grupos_transpuestos:
            grupo_transpuesto.columns = nuevo_nombre_columnas
            df_final_sri = pd.concat([df_final_sri,grupo_transpuesto], ignore_index=True)

        df_final_sri[['Año fiscal', 'Formulario']] = df_final_sri['Año fiscal'].str.split(' ', expand=True, n=1)
        df_final_sri = df_final_sri[['Año fiscal', 'Formulario', 'Valor', 'Impuesto a la Salida de Divisas']]
        df_final_sri.fillna('Sin Información', inplace=True)
        return df_final_sri

    finally:
        driver.quit()

# Función principal de la aplicación Streamlit
async def main():
    st.title('Reporte Crediticio')

    st.markdown(
        """
        <style>
        .logo-container {
            display: inline-block;
            vertical-align: middle;
            margin-left: 400px;
            margin-top: -130px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        '<div style="text-align: center;"><img src="https://www.camaraofespanola.org/files/Afiliados/Logos/BancoInternacional.png" width="250" class="logo-container"></div>',
        unsafe_allow_html=True
    )

    st.write('Ingresa la Identificación')

    Id = st.text_input("Por favor, ingresa el valor de 10 dígitos:")

    if len(Id) == 10 and Id.isdigit():
        if st.button('Consultar Información'):
            try:
                st.subheader('Información Judicial', divider="gray")
                try:
                    result = await post_request_funcion_judicial(Id)
                    df_fj = create_dataframe_funcion_judicial(result)
                    st.table(df_fj)
                except Exception as e:
                    st.write('Sin información encontrada')
                    print('Error en consulta judicial:', e)

                st.subheader('Información SRI', divider="gray")
                try:
                    df_sri = await consulta_sri(Id)
                    st.table(df_sri)
                except Exception as e:
                    st.write('Sin información encontrada')
                    st.write( e)

            except Exception as e:
                st.write('Ocurrió un error:', e)
                
    else:
        st.write("El valor ingresado no tiene exactamente 10 dígitos. Inténtalo de nuevo.")

if __name__ == "__main__":
    asyncio.run(main())
