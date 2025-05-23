from PIL import Image
from pytesseract import pytesseract

import enum
import pandas as pd
import gspread
import calendar
import re
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from urllib.request import urlopen

class OS(enum.Enum):
    Mac = 0
    Windows = 1

class Languages(enum.Enum):
    ENG = 'eng'
    SPA = 'spa'


class ImageReader:

    def __init__(self, os: OS):
        if os == OS.Mac:
            print('Running on mac.')
        if os == OS.Windows:
            print('Running on windows.')
    

    def extract_text(self, image_path: str, lang: str) -> str:
        img = Image.open(image_path)
        extracted_text = pytesseract.image_to_string(img, lang = lang)

        return extracted_text

if __name__ == '__main__':

    def publish(df):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
        client = gspread.authorize(creds)

        spreadsheet_name = 'Gastos 2025'
        try:
            spreadsheet = client.open(spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            print('No existe esa hoja de calculo')

        fecha = pd.to_datetime(df['Fecha'][0], format='%d/%m/%Y')
        nombre_mes = calendar.month_name[fecha.month]  # Ejemplo: 'April'
        print(f"Nombre del mes detectado: {nombre_mes}")

        worksheet_list = spreadsheet.worksheets()
        worksheet_names = [ws.title for ws in worksheet_list]
        if nombre_mes in worksheet_names:
            worksheet = spreadsheet.worksheet(nombre_mes)
            print(f"La hoja '{nombre_mes}' ya existe.")
        else:
            worksheet = spreadsheet.add_worksheet(title=nombre_mes, rows="100", cols="20")
            print(f"Hoja '{nombre_mes}' creada.")
            set_with_dataframe(worksheet, df.head(0))

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
       

    def parse_text_to_dataframe(text: str) -> pd.DataFrame:
        print(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        print(lines)
        
        date_pattern = r'\d{2}/\d{2}/\d{4}'
        first_line = lines[0]
        date_match = re.search(date_pattern, first_line)
        if not date_match:
            raise ValueError("No se encontró una fecha válida en el texto.")
        
        current_date = date_match.group()
        
        rows = []
        for line in lines:
            amount_match = re.search(r'-\$[\d\.\,]+', line)
            if amount_match:
                monto_raw = amount_match.group()
                monto = monto_raw.replace('-$', '').replace('.', '')
                detalle = line.replace(current_date, '').replace(monto_raw, '').replace('coy', '').replace('poy', '').strip()
                rows.append({
                    "Fecha": current_date,
                    "Detalle": detalle,
                    "Monto cargo": monto
                })

        return pd.DataFrame(rows)



    ir = ImageReader(OS.Mac)
    text = ir.extract_text('images/image.png', lang='eng')
    
    df = parse_text_to_dataframe(text)

    publish(df)

