import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import pandas as pd
import re
import aiohttp
import asyncio
import numpy as np
from PIL import Image
import pytesseract
from time import sleep
import os
import glob
import tabula
import shutil
import tempfile

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
    # directorio temporal
    temp_dir = tempfile.mkdtemp()
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    prefs = {
        "download.default_directory": temp_dir,  # Directorio temporal
        "download.prompt_for_download": False,   # No mostrar cuadro de diálogo
        "plugins.always_open_pdf_externally": True  # Descargar automáticamente los PDFs
    }   
    
    options.add_experimental_option("prefs", prefs)
# usar este service para modo desarrollo
    #service = Service(ChromeDriverManager().install())
    
    # usar este service para modo produccion
    service = Service(ChromeDriverManager(driver_version='120.0.6099.224').install())
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

        elemento_busqueda = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@id='busquedaRucId']")))
        elemento_busqueda = driver.find_element(By.XPATH, "//input[@id='busquedaRucId']")
        elemento_busqueda.click()
        elemento_busqueda.send_keys(Id)

        ProcSRIclick = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "/html/body/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/div[6]/div[2]/div/div[2]/div/button")))
        ProcSRIclick = driver.find_element(By.XPATH, "/html/body/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/div[6]/div[2]/div/div[2]/div/button")
        ProcSRIclick.click()

        InfoCausas = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@id='sribody']/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/sri-mostrar-impuesto-renta/div[5]/div[1]/div")))
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
        #df = df.replace(',', '.', regex=True)
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

# Función para descargar y leer el PDF desde MSP
def descargar_y_leer_pdf(Id):
    driver = get_driver()
    # Ruta de la carpeta de descargas
    downloads_folder = tempfile.gettempdir()
    try:
        url = 'https://coberturasalud.msp.gob.ec/'
        driver.get(url)
        sleep(2)

        ProcMsp = driver.find_element(By.XPATH, "/html/body/div/div[1]/div[2]/div[1]/div[2]/div/div")
        ProcMsp.click()
        ProcMsp = driver.find_element(By.XPATH, "//*[@id='cedula']")
        ProcMsp.send_keys(Id)
        ProcMsp = driver.find_element(By.XPATH, "/html/body/div/div[1]/div[2]/div[1]/div[5]/div/button[1]")
        ProcMsp.click()
        sleep(3)

        pdf_element = driver.find_element(By.TAG_NAME, 'embed')  # Puede ser 'iframe' o 'embed'
        pdf_url = pdf_element.get_attribute('src')
        print(f"URL del PDF: {pdf_url}")
        # Descargar el PDF
        print("Archivos en la carpeta de descargas antes de descargar:", glob.glob(os.path.join(downloads_folder, "*.pdf")))
        driver.get(pdf_url)
        sleep(3)  
        print("Archivos en la carpeta de descargas después de descargar:", glob.glob(os.path.join(downloads_folder, "*.pdf")))


        # Buscar los archivos PDF en la carpeta de descargas
        pdf_files = glob.glob(os.path.join(downloads_folder, "*.pdf"))

        # Ordenar por fecha de modificación y seleccionar el más reciente
        if pdf_files:
            latest_pdf = max(pdf_files, key=os.path.getmtime)

            # Leer las tablas del archivo PDF
            try:
                # Extraer tablas
                tables = tabula.read_pdf(latest_pdf, multiple_tables=True)
                
                # Crear DataFrames separados para cada tabla
                dataframes = []
                for i, table in enumerate(tables):
                    df = pd.DataFrame(table)
                    # Cambiar nombres de columnas
                    df.rename(columns={
                        'Tipo de Seguro': 'TipoSeguro',
                        'Registro de Cobertura de Atención de Salud': 'CoberturaSalud'
                    }, inplace=True)
                    # Eliminar columna Mensaje
                    if 'Mensaje' in df.columns:
                        df.drop(columns=['Mensaje'], inplace=True)
                    # Eliminar los NA de la columna 'Seguro'
                    if 'Seguro' in df.columns:
                        df = df.dropna(subset=['Seguro'])
                    dataframes.append(df)
                
                return dataframes
            except Exception as e:
                print(f"Error al leer el PDF: {e}")
                return []
        else:
            print("No se encontraron archivos PDF en la carpeta de descargas.")
            return []
    finally:
        print('J¿Hi')
        # driver.quit()

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
                    st.write(e)
                    
                st.subheader('Cobertura de Salud', divider="gray")
                try:
                    dataframes = descargar_y_leer_pdf(Id)
                    for i, df in enumerate(dataframes):
                        st.write(f"Tabla {i+1}")
                        st.table(df)
                except Exception as e:
                    st.write('Error al leer la información de cobertura de salud')
                    st.write(e)

            except Exception as e:
                st.write('Ocurrió un error:', e)
                
    else:
        st.write("El valor ingresado no tiene exactamente 10 dígitos. Inténtalo de nuevo.")

if __name__ == "__main__":
    asyncio.run(main())
