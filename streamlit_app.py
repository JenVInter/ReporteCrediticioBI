import streamlit as st
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from time import sleep
import pandas as pd
from datetime import datetime
from PIL import Image
import pytesseract
import tabula
import re
import numpy as np

def LimpiarText(df):
    df = df.map(lambda x: re.sub('S.A.', 'SA', x))  
    df = df.map(lambda x: re.sub("'", '', x))
    df = df.map(lambda x: re.sub('[^\w\s]', ' ', x))
    df = df.map(lambda x: re.sub("\s+", ' ', x))
    df = df.apply(lambda x: x.strip())
    return(df)

def main():
    st.title('Reporte Crediticio')

    # Mostrar imagen como logo al lado del título
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

    # Obtener el ID de 10 dígitos del usuario
    Id = st.text_input("Por favor, ingresa el valor de 10 dígitos:")
    if len(Id) == 10 and Id.isdigit():
        if st.button('Consultar Información'):
            # Configuración del WebDriver
            driver = webdriver.Chrome(ChromeDriverManager().install())
            
            # Inicialización de DataFrames
            df_final = pd.DataFrame()
            df_iess = pd.DataFrame()
            df_final_sri = pd.DataFrame()

            try:
                st.subheader('Información Judicial', divider="gray")# Consultar información de procesos judiciales
                try:
                    url_procesos = 'https://procesosjudiciales.funcionjudicial.gob.ec/busqueda-filtros'
                    driver.get(url_procesos)
                    sleep(2)

                    # Ingresar el ID en el campo de búsqueda
                    ProcJudicial = driver.find_element(By.ID, 'mat-input-3')
                    ProcJudicial.send_keys(Id)
                    sleep(5)

                    # Hacer clic en el botón de búsqueda
                    SignInButton = driver.find_element(By.XPATH, "/html/body/app-root/app-expel-filtros-busqueda/expel-sidenav/mat-sidenav-container/mat-sidenav-content/section/form/div[6]/button[1]")
                    SignInButton.click()
                    sleep(5)

                    # Extraer información de la tabla de resultados
                    InfoCausas = driver.find_element(By.CLASS_NAME, 'cuerpo')
                    lineas = InfoCausas.text.split('\n')
                    datos = [linea.split('\t') for linea in lineas]
                    df = pd.DataFrame(datos)

                    df_final = pd.DataFrame()
                    grupos_filas = [df.iloc[i:i + 5, :] for i in range(0, len(df), 5)]
                    grupos_transpuestos = [grupo.T for grupo in grupos_filas]

                    for i, grupo_transpuesto in enumerate(grupos_transpuestos):
                        nuevo_nombre_columnas = ['NRegistros', 'FechaIngreso', 'NumeroProceso', 'AccionInfraccion', 'Detalle']
                        grupo_transpuesto.columns = nuevo_nombre_columnas
                        df_final = df_final.append(grupo_transpuesto, ignore_index=True)

                    df_final = df_final.drop(columns=['Detalle'])
                    df_final.insert(loc=0, column='Identificacion', value=Id)
                    #df_final['FechaProceso'] = datetime.today().date()
                    #df_final['IdCJ'] = 'SI'

                    # Mostrar el DataFrame sin índices visibles
                    st.table(df_final)
                except Exception as e:
                    st.write('Sin Información encontrada')
                    print('Error en consulta judicial:', e)

                st.subheader('Información IESS', divider="gray")
                try:
                    url_iess = 'https://www.iess.gob.ec/iess-kiosko-web/pages/public/afiliacion/certificadoAfiliacion.jsf'
                    driver.get(url_iess)
                    sleep(2)

                    ProcIESS = driver.find_element(By.XPATH, "//input[@id='frmCertificadoAfiliacion:cedulaIn']")
                    ProcIESS.click()
                    sleep(3)

                    for numero in Id:
                        boton_numero = driver.find_element(By.CSS_SELECTOR, f"button[title='{numero}']")
                        boton_numero.click()

                    sleep(3)
                    boton_cierre = driver.find_element(By.XPATH, "//button[normalize-space()='.']")
                    boton_cierre.click()
                    boton_consulta = driver.find_element(By.XPATH, "//input[@name='frmCertificadoAfiliacion:j_id30']")
                    boton_consulta.click()
                    sleep(12)

                    driver.switch_to.window(driver.window_handles[1])
                    driver.save_screenshot('IESS_Reporte.png')
                    sleep(3)

                    imagen = Image.open('IESS_Reporte.png')
                    coordenadas = (150, 200, 750, 345)
                    imagen.crop(coordenadas).save('IESS_Reporte.png')

                    imagen = Image.open('IESS_Reporte.png')
                    texto_extraido = pytesseract.image_to_string(imagen)

                    # Expresiones regulares para extraer datos
                    patron_patronal = r'(?:Ni|N)imero Patronal:\s*(\d+)'
                    patron_lugar = r'\d+(.*?)con RUC'
                    patron_lugar2 = r'afiliacion a\s*(.*?)\s*con RUC'
                    patron_afiliado = r'afiliado es:\s*([\w]+)'
                    patron_fecha = r'\d{4}-\d{1,2}'

                    numero_patronal = re.findall(patron_patronal, texto_extraido, re.DOTALL)
                    lugar = re.findall(patron_lugar, texto_extraido, re.DOTALL)
                    lugar2 = re.findall(patron_lugar2, texto_extraido, re.DOTALL)
                    estado_afiliado = texto_extraido.split("afiliado es:")[1].split("\n")[0].strip()
                    fecha_proceso = re.findall(patron_fecha, texto_extraido)

                    if len(numero_patronal) > 1:
                        numero_patronalf = pd.DataFrame(numero_patronal, columns=['NumeroPatronal'])
                        lugarf = pd.DataFrame(lugar, columns=['Lugar'])
                        estado_afiliadof = pd.DataFrame({'Estado': [estado_afiliado] * len(numero_patronal)})
                        fecha_procesof = pd.DataFrame({'UltimaFechaAfiliacion': [fecha_proceso[0]] * len(numero_patronal)})
                        df_iess = pd.concat([numero_patronalf, lugarf, estado_afiliadof, fecha_procesof], axis=1)
                    else:
                        numero_patronalf = pd.DataFrame(numero_patronal, columns=['NumeroPatronal'])
                        lugarf = pd.DataFrame(lugar, columns=['Lugar'])
                        estado_afiliadof = pd.DataFrame({'Estado': [estado_afiliado]})
                        fecha_procesof = pd.DataFrame({'UltimaFechaAfiliacion': [fecha_proceso[0]]})
                        df_iess = pd.concat([numero_patronalf, lugarf, estado_afiliadof, fecha_procesof], axis=1)

                    df_iess['Lugar'] = df_iess['Lugar'].str.replace(".", "")
                    df_iess.at[0, 'Lugar'] = df_iess.loc[0, 'Lugar'].split("empresa(s):\n\n")[-1].strip()
                    df_iess.at[0, 'Lugar'] = df_iess.loc[0, 'Lugar'].split("empresas):\n\n")[-1].strip()
                    df_iess.at[0, 'Lugar'] = df_iess.loc[0, 'Lugar'].split("empresas")[-1].strip()

                    df_iess.insert(loc=0, column='Identificacion', value=Id)

                    cols = ['NumeroPatronal', 'Estado', 'Lugar']
                    df_iess[cols] = df_iess[cols].apply(lambda x: LimpiarText(x))

                    df_iess['UltimaFechaAfiliacion'] = df_iess.UltimaFechaAfiliacion.apply(lambda x: x.strip())
                    df_iess['NumeroPatronal'] = df_iess.NumeroPatronal.astype('Int64').astype('str')
                    df_iess = df_iess.assign(Estado=np.where(
                        (df_iess.Estado.str.contains("ACTIV", regex=True, flags=re.IGNORECASE)), "ACTIVO",
                        np.where((df_iess.Estado.str.contains("JUBIL", regex=True, flags=re.IGNORECASE)), "JUBILADO",
                                 np.where((df_iess.Estado.str.contains("FALLECID", regex=True, flags=re.IGNORECASE)), "FALLECIDO", df_iess.Estado)
                                 )
                    ))
                    st.table(df_iess)
                except Exception as e:
                    st.write('Información IESS: Sin Información encontrada')

                st.subheader('Información SRI', divider="gray")
                try:
                    url_sri = 'https://srienlinea.sri.gob.ec/sri-en-linea/SriDeclaracionesWeb/ConsultaImpuestoRenta/Consultas/consultaImpuestoRenta'
                    driver.get(url_sri)
                    sleep(2)

                    Idsri = '1722431101001'
                    contr = 'Victor2022*'

                    # Ingresar credenciales
                    ProcSri = driver.find_element(By.XPATH, "//input[@id='usuario']")
                    ProcSri.click()
                    sleep(3)
                    ProcSri.send_keys(Idsri)
                    sleep(5)

                    ProcSRIctr = driver.find_element(By.XPATH, "//input[@id='password']")
                    ProcSRIctr.click()
                    sleep(3)
                    ProcSRIctr.send_keys(contr)
                    sleep(5)

                    # Iniciar sesión
                    ProcSRIclick = driver.find_element(By.XPATH, "//input[@id='kc-login']")
                    ProcSRIclick.click()
                    sleep(5)

                    # Ingresar el ID para la búsqueda
                    elemento_busqueda = driver.find_element(By.XPATH, "//input[@id='busquedaRucId']")
                    elemento_busqueda.click()
                    elemento_busqueda.send_keys(Id)
                    sleep(5)

                    # Clic en botón de búsqueda
                    ProcSRIclick = driver.find_element(By.XPATH, "/html/body/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/div[6]/div[2]/div/div[2]/div/button")
                    ProcSRIclick.click()
                    sleep(5)

                    # Extraer información
                    InfoCausas = driver.find_element(By.XPATH, '//*[@id="sribody"]/sri-root/div/div[2]/div/div/sri-impuesto-renta-web-app/div/sri-impuesto-renta/div[1]/sri-mostrar-impuesto-renta/div[5]/div[1]/div')
                    lineas = InfoCausas.text.split('\n')
                    datos = [linea.split('\t') for linea in lineas]
                    df = pd.DataFrame(datos)

                    # Procesamiento de la tabla SRI
                    n_registros_sri = df.iloc[0].apply(lambda x: x.split('-')[-1].strip())
                    print('Se encontraron:', n_registros_sri[0])
                    df = df[~df.isin(['ui-btn','Detalle de valores - 8 registros','Impuesto a la Renta Causado Régimen General','Otros Regímenes','Formulario']).any(axis=1)]
                    df.iloc[[1, 2]] = df.iloc[[2, 1]].values
                    df = df.iloc[:-2]

                    df_final_sri = pd.DataFrame()
                    nuevo_nombre_columnas = df.iloc[:3].astype(str).T.values.flatten()
                    nuevo_nombre_columnas = nuevo_nombre_columnas.tolist()
                    df = df[3:].reset_index(drop=True)
                    df = df.replace('USD', '', regex=True)
                    df = df.replace(',', '.', regex=True)
                    grupos_filas = [df.iloc[i:i+3, :] for i in range(0, len(df), 3)]
                    grupos_transpuestos = [grupo.T for grupo in grupos_filas]

                    for i, grupo_transpuesto in enumerate(grupos_transpuestos):
                        grupo_transpuesto.columns = nuevo_nombre_columnas
                        df_final_sri = df_final_sri.append(grupo_transpuesto, ignore_index=True)

                    df_final_sri[['Año fiscal', 'Formulario']] = df_final_sri['Año fiscal'].str.split(' ', expand=True, n=1)
                    df_final_sri = df_final_sri[['Año fiscal', 'Formulario', 'Valor', 'Impuesto a la Salida de Divisas']]
                    df_final_sri.fillna('Sin Informacion', inplace=True)
                    df_final_sri = df_final_sri.replace('Período Fiscal en curso', np.nan , regex=True)
                    df_final_sri = df_final_sri.applymap(lambda x: np.nan if isinstance(x, str) and x.startswith("* La") else x)

                    # Mostrar la tabla con la información del SRI
                    st.table(df_final_sri)
                except Exception as e:
                    st.write('Información SRI: Sin Información encontrada')
                    print('Error en consulta SRI:', e)

            except Exception as e:
                st.write('Ocurrió un error:', e)
                
            finally:
                driver.quit()

    else:
        st.write("El valor ingresado no tiene exactamente 10 dígitos. Inténtalo de nuevo.")

if __name__ == "__main__":
    main()
