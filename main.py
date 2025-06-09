import asyncio
from playwright.async_api import async_playwright, TimeoutError
from datetime import datetime, date, timedelta
from urllib.parse import urlencode
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
import calendar

# Definir headers y user_agent una sola vez para consistencia
COMMON_HEADERS = {
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://mibanco.santander.cl',
    'Referer': 'https://mibanco.santander.cl/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'app': '007',
    'canal': '003',
    'nro_ser': '1',
    'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'tokentbk': 'TOKEN@4152811016027300',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Connection': 'keep-alive',
    'Priority': 'u=1, i',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36' 
}

# Datos del formulario para la petición POST
LOGIN_PAYLOAD_DATA = {
    'scope': 'Completa',
    'username': '00username', # ACTUALIZAR CON EL VALOR REAL DEL USUARIO DE LA PETICIÓN CURL
    'password': 'password', # ACTUALIZAR CON EL VALOR REAL DE LA CLAVE DE LA PETICIÓN CURL
    'client_id': '4e9af62c-6563-42cd-aab6-0dd7d50a9131'
}

# URL del endpoint de autenticación
AUTH_TOKEN_URL = 'https://apideveloper.santander.cl/sancl/privado/party_authentication_restricted/party_auth_dss/v1/oauth2/token'


async def handle_route(route, page_instance):
    """
    Función asíncrona para interceptar y manejar peticiones de red.
    Recibe el objeto `route` de Playwright y una instancia de `page`.
    """
    request = route.request

    if request.method == "POST" and AUTH_TOKEN_URL in request.url:
        print("Petición de token interceptada!")
        print(f"URL original interceptada: {request.url}")
        print(f"Headers originales interceptados: {request.headers}")
        if request.post_data:
            print(f"Post Data original interceptado: {request.post_data}")

        # Realizar tu propia petición POST con los headers actualizados
        custom_response = await page_instance.request.post(
            AUTH_TOKEN_URL,
            data=urlencode(LOGIN_PAYLOAD_DATA), # Usar los datos definidos globalmente y codificarlos
            headers=COMMON_HEADERS # Usar los headers definidos globalmente
        )

        body = await custom_response.body()
        headers = dict(custom_response.headers)
        status = custom_response.status

        print(f"Respuesta de tu petición POST: Estado {status}, Texto: {body.decode('utf-8')}")

        await route.fulfill(status=status, body=body, headers=headers)
    else:
        await route.continue_()


def publish(df):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
    client = gspread.authorize(creds)

    spreadsheet_name = 'Gastos 2025'
    try:
        spreadsheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        print('No existe esa hoja de calculo')
        return # Salir si no encuentra la hoja de cálculo

    # Obtener el nombre del mes de la fecha del primer gasto
    fecha = pd.to_datetime(df['Fecha'][0], format='%d/%m/%Y')
    nombre_mes = calendar.month_name[fecha.month] # Obtener el nombre del mes completo
    print(f"Nombre del mes detectado: {nombre_mes}")

    worksheet_list = spreadsheet.worksheets()
    worksheet_names = [ws.title for ws in worksheet_list]
    if nombre_mes in worksheet_names:
        worksheet = spreadsheet.worksheet(nombre_mes)
        print(f"La hoja '{nombre_mes}' ya existe.")
    else:
        worksheet = spreadsheet.add_worksheet(title=nombre_mes, rows="100", cols="20")
        print(f"Hoja '{nombre_mes}' creada.")
        set_with_dataframe(worksheet, df.head(0)) # Escribir solo los headers

    existing_data = worksheet.col_values(1)
    next_row = len(existing_data) + 1

    include_headers = len(existing_data) == 0

    set_with_dataframe(
        worksheet,
        df.iloc[:, :3],
        row=next_row,
        col=1,
        include_column_header=include_headers
    )
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
    print(f"¡Datos subidos exitosamente! Puedes verlo aquí: {spreadsheet_url}")


def get_dates_from_last_processed(date_format ="%d/%m/%Y"):
    last_fecha = None
    fecha_objetivo = datetime.today().strftime('%d/%m/%Y')

    try:
        with open("last_processed_date.txt", "r") as archivo:
            last_fecha = archivo.readline().strip() # Usar readline y strip para evitar saltos de línea
    except FileNotFoundError:
        print("El archivo 'last_processed_date.txt' no se encontró. Procesando desde una fecha predeterminada o la fecha de hoy.")
        # Podrías establecer last_fecha a una fecha muy antigua o la fecha de hoy
        # Para este ejemplo, estableceremos el inicio como el día anterior a hoy si el archivo no existe
        last_fecha_obj = datetime.today() - timedelta(days=1)
        last_fecha = last_fecha_obj.strftime(date_format)
    except Exception as e:
        print(f"Ocurrió un error al leer el archivo 'last_processed_date.txt': {e}")
        # En caso de otros errores de lectura, puedes optar por salir o establecer una fecha por defecto
        last_fecha_obj = datetime.today() - timedelta(days=1)
        last_fecha = last_fecha_obj.strftime(date_format)


    print(f"Última fecha procesada (desde archivo o defecto): {last_fecha}")
    print(f"Fecha objetivo (hoy): {fecha_objetivo}")

    try:
        start_date = datetime.strptime(last_fecha, date_format).date()
        end_date = datetime.strptime(fecha_objetivo, date_format).date()
    except ValueError as e:
        raise ValueError(f"Error al parsear fechas. Asegúrate de que 'last_processed_date.txt' contenga una fecha válida con formato {date_format}. Error: {e}")

    dates = []
    current_date = start_date + timedelta(days=1) # Empezar desde el día siguiente a last_fecha

    while current_date <= end_date:
        dates.append(current_date.strftime(date_format))
        current_date += timedelta(days=1)
    return dates


def dictionary_to_dataframe(gastos):
    df = pd.DataFrame(gastos)
    print("DataFrame inicial:\n", df)

    if "Monto Cargo" in df.columns:
        # Eliminar caracteres no numéricos excepto el punto decimal si es el caso, luego convertir a int
        # Si los montos son enteros sin decimales, la regex es correcta.
        # Si tienen decimales y necesitas manejarlos, ajusta la regex y la conversión.
        df["Monto Cargo"] = (
            df["Monto Cargo"]
            .str.replace(r"[^0-9]", "", regex=True) # Elimina todo lo que no sea dígito
            .astype(int)
        )
    print("DataFrame final:\n", df)
    return df

async def scrap(dates):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=COMMON_HEADERS['User-Agent'], # Usar el User-Agent consistente
            extra_http_headers={k: v for k, v in COMMON_HEADERS.items() if k != 'User-Agent' and k != 'Content-Type'} # Excluir User-Agent y Content-Type ya que Playwright los maneja por separado
        )
        page = await context.new_page()

        # Registrar la función de manejo de rutas ANTES de cualquier navegación que pueda disparar la petición
        await page.route("**", lambda route: handle_route(route, page)) # Pasar la instancia de page a handle_route

        await page.goto("https://banco.santander.cl/personas")
        await page.click('#btnIngresar')

        print("URL actual:", page.url)

        await page.wait_for_selector("#login-frame")
        frame = page.frame_locator("#login-frame")

        # CORREGIDO: Pasar timeout a .wait_for()
        await frame.locator("#rut").wait_for(timeout=10000)
        print("Se encontró el campo #rut dentro del iframe")

        rut_value = LOGIN_PAYLOAD_DATA['username'] # Usar el RUT del payload
        for i in range(1, len(rut_value) + 1):
            valor_parcial = rut_value[:i]
            await frame.locator("#rut").fill(valor_parcial)
            await asyncio.sleep(0.1) # Pequeño delay para simular escritura humana

        # CORREGIDO: Pasar timeout a .wait_for()
        await frame.locator('#pass').wait_for(timeout=10000)
        print("Se encontró el campo #pass dentro del iframe")

        pwd_value = LOGIN_PAYLOAD_DATA['password'] # Usar la contraseña del payload
        for i in range(1, len(pwd_value) + 1):
            valor_parcial = pwd_value[:i] # CORREGIDO: usar pwd_value
            await frame.locator("#pass").fill(valor_parcial)
            await asyncio.sleep(0.1) # Pequeño delay

        await asyncio.sleep(2) # Dar un momento antes del clic

        # Hacer clic en el botón "submit" dentro del iframe
        await frame.locator('button[type="submit"]').click()

        print("Clic en submit realizado. Esperando navegación o intercepción.")
        # Espera que la URL final de la página sea la de home o dashboard después del login
        # Puedes ajustar esta URL según a dónde te redirija el login exitoso
        try:
            await page.wait_for_url("https://mibanco.santander.cl/UI.Web.HB/Private_new/frame/#/private/home/main", timeout=30000)
            print("Navegación post-login exitosa a la URL de home.")
        except TimeoutError:
            print("Tiempo de espera agotado para la URL de home post-login. Comprobando URL actual.")
            print(f"URL actual después del intento de login: {page.url}")
            # Si el login falla, page.url podría seguir siendo la página de login o mostrar un error.
            # Puedes añadir más lógica aquí para manejar fallos de login.
            await page.screenshot(path="login_failed_screenshot.png")
            await browser.close()
            return [] # Retornar lista vacía de gastos si el login falla

        # Ir directamente a la URL de movimientos
        print("Navegando a la página de movimientos...")
        await page.goto("https://mibanco.santander.cl/UI.Web.HB/Private_new/frame/#/private/Saldos_TC/main/bill")
        await asyncio.sleep(5) # Esperar a que la página de movimientos cargue completamente

        # Intentar cerrar el modal "Recuérdamelo más tarde" si aparece
        try:
            await page.locator("button.solicitanocamp", has_text="Recuérdamelo más tarde", timeout=5000).click()
            print("Se hizo clic en 'Recuérdamelo más tarde'")
        except TimeoutError:
            print("No se encontró el modal 'Recuérdamelo más tarde'.")

        # Esperar a que la tabla de movimientos esté presente
        await page.wait_for_selector("table.mat-table", timeout=15000)
        print("Tabla de movimientos encontrada.")

        rows = await page.query_selector_all("table.mat-table tbody tr")
        gastos = []

        # Actualizar la last_processed_date después de obtener las fechas a procesar y antes del scraping
        fecha_objetivo_str = datetime.today().strftime('%d/%m/%Y')
        try:
            with open("last_processed_date.txt", "w") as archivo:
                archivo.write(fecha_objetivo_str)
            print(f"Fecha objetivo '{fecha_objetivo_str}' almacenada como última fecha procesada.")
        except Exception as e:
            print(f"Ocurrió un error al escribir la fecha objetivo en 'last_processed_date.txt': {e}")


        fecha_actual = None
        for row in rows:
            columnas = await row.query_selector_all("td")
            total_col = len(columnas)

            if total_col < 6: # Asegurarse de que la fila tiene suficientes columnas
                continue

            fecha_text = await columnas[0].inner_text()
            detalle = await columnas[2].inner_text()
            monto = await columnas[3].inner_text()

            if fecha_text.strip():
                fecha_actual = fecha_text.strip()

            if fecha_actual in dates: # Filtrar por las fechas que queremos procesar
                gastos.append({
                    "Fecha": fecha_actual,
                    "Detalle": detalle.strip(),
                    "Monto Cargo": monto.strip()
                })
        print(f"Scraped {len(gastos)} movimientos para las fechas objetivo.")

        await browser.close()
        return gastos


if __name__ == '__main__':
    # 1. Obtener las fechas a procesar
    dates_to_process = get_dates_from_last_processed()
    print(f"Fechas a procesar: {dates_to_process}")

    # 2. Realizar el scraping
    scraped_data = asyncio.run(scrap(dates_to_process))

    if not scraped_data:
        print("No se obtuvieron gastos o hubo un problema en el scraping. No se publicará nada.")
    else:
        # 3. Convertir a DataFrame
        df_gastos = dictionary_to_dataframe(scraped_data)

        # 4. Publicar en Google Sheets
        publish(df_gastos)