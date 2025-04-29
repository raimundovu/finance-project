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

    def clean_lines(lines): 
        lines = [line.strip() for line in text.splitlines() if line.strip() and line.lower() != 'coy']
        return lines

    def separate_sections(original):
        section_keys = ['Fecha', 'Detalle', 'Monto cargo', 'Monto abono'] 

        separated = {}
        current_key = None

        for line in original:
            if line in section_keys:
                current_key = line
                separated[current_key] = []
            else:
                if current_key: 
                    separated[current_key].append(line)
        return separated

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

        existing_data = worksheet.get_all_values()
        next_row = len(existing_data) + 1

        # Escribir datos sin sobrescribir
        set_with_dataframe(worksheet, df, row=next_row, include_column_header=False)

        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        print(f"¡Datos subidos exitosamente! Puedes verlo aquí: {spreadsheet_url}")
       

    def parse_text_to_dataframe(text: str) -> pd.DataFrame:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
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
                monto = amount_match.group()
                detalle = line.replace(current_date, '').replace(monto, '').replace('coy', '').strip()
                rows.append({
                    "Fecha": current_date,
                    "Detalle": detalle,
                    "Monto cargo": monto
                })

        return pd.DataFrame(rows)



    ir = ImageReader(OS.Mac)
    text = ir.extract_text('images/image.png', lang='eng')
    print(text)
    
    df = parse_text_to_dataframe(text)

    publish(df)

