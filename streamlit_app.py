import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from streamlit_pdf_viewer import pdf_viewer
from streamlit_extras.add_vertical_space import add_vertical_space
#from PyPDF2 import PdfReader
import time
import os
import re
import zipfile
import io
import base64

st.set_page_config(
    page_title="Bloody app devours my soul", 
    layout="wide")

def extract(lst):
    return [item[0] for item in lst]
def find_account(input_string):
    res = re.search(r'\d{20}', input_string)
    return res[0]
def data_prep_load():
    conn = st.connection("gsheets", type=GSheetsConnection)
    url = "https://docs.google.com/spreadsheets/d/1ftUQL2RRga6sXe7gqjv19FmUDinwtkR-o_UNmFBFMXs/edit"
    data = conn.read(spreadsheet=url, usecols=[0, 1, 2])
    data.columns = ['account', 'file_name', 'class']
    return data
def env_initiation():
    if 'raw_files' not in st.session_state:
        st.session_state.raw_files = None

    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'recognized_files' not in st.session_state:
        st.session_state.recognized_files = []
    if 'nonrecognized_files' not in st.session_state:
        st.session_state.nonrecognized_files = []
def file_segregation(data):
    # Function separates uploaded data into 3 structures:

    # initial - raw_files
    #_________________________________
    # generated - recognized_files
    # generated - nonrecognized_files
    # generated - uploaded_files (all)

    file_not_detected = '❌ Файл не определен ❌'
    account_not_detected = '❌ Номер счета не найден ❌'

    if upload:
        st.session_state.raw_files = upload
        for file in st.session_state.raw_files:

            # First check: account pattern
            if_found = re.search(r'\d{20}', file.name)
            file_name = file.name

            if if_found:
                account_detected = if_found[0]
            # Second check: if in Spreadsheet DB
                if account_detected in data.account.tolist():
                    file.name = account_detected
                    if file_name not in extract(st.session_state.recognized_files):
                        st.session_state.recognized_files.append([file_name, account_detected, True])
                        st.session_state.uploaded_files.append(([file_name, account_detected, True]))
                
                else:
                    if file_name not in extract(st.session_state.nonrecognized_files):
                        st.session_state.nonrecognized_files.append([file_name, account_not_detected, False])
                        st.session_state.uploaded_files.append(([file_name, account_not_detected, False]))
            else:
                if file_name not in extract(st.session_state.nonrecognized_files):
                    st.session_state.nonrecognized_files.append([file_name, file_not_detected, False])
                    st.session_state.uploaded_files.append(([file_name, file_not_detected, False]))
def db_creation(data, db):
    upload_db = pd.DataFrame(data, columns=['upl_filename', 'account', 'recognition_status'])
    rename_db = upload_db.merge(db ,how='left', on='account')[
        ['account', 'upl_filename', 'file_name', 'class']]
    
    return upload_db, rename_db
def recongnition_status(upload, data):
    col1, col2, col3 = st.columns(3)
    #
    upl_m = len(upload)
    recogn_m = len(data)
    nonrecogn_m = upl_m - recogn_m
    #
    col1.metric(label="Файлов загружено", value=upl_m, delta=upl_m, delta_color='off')
    col2.metric("Распознано", recogn_m, recogn_m)
    col3.metric("Нераспознано", nonrecogn_m, nonrecogn_m, delta_color='inverse')
def preview():
    
    if_show_rename = st.toggle('Show upload&rename table')
    if if_show_rename and not len(upload) == 0:
        options = {
            'All': st.session_state.uploaded_files, 
            'Recognized': st.session_state.recognized_files, 
            'Non-recognized': st.session_state.nonrecognized_files}
        
        control = st.segmented_control('Show uploaded files', options)
        
        if control:
            #st.write(options[control])
            st.dataframe(options[control], 
                        use_container_width=True)
        
    elif if_show_rename and len(upload) == 0:
        st.warning('No files uploaded')
def create_zip(upload, db):
        zip_buffer = io.BytesIO()
        
        # Create a Zip file in memory
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

            for pdf in upload:

                try:    
                    st.write(pdf.name)
                    pdf_name = db[db['upl_filename'] == pdf.name]['file_name'].values[0] + '.pdf'

                    zip_file.writestr(pdf_name, pdf.getvalue())
                except:
                    st.markdown('''❌''' + pdf.name + ''' :red[was not added]''')
        
        zip_buffer.seek(0)  # Rewind the buffer to the beginning
        return zip_buffer
def look_at_fund_accounts (db):
    option = st.radio("Choose AMC of interest", options=["None", "S+", "WIM"], index=0)

    if option == "S+":
        st.dataframe(db[db['class'] in ['S', 'S, AFI']])
    elif option == "WIM":
        st.dataframe(db[db['class'] == 'W'])
    else:
        pass
    ###
def download_zip(upload, db):
    if st.button('Download ZIP of PDFs'):
        if upload:
            zip_buffer = create_zip(upload, db)
            st.download_button(
                label="Download ZIP",
                data=zip_buffer,
                file_name="pdf_files.zip",
                mime="application/zip",
                icon=":material/barcode:"
            )
        else:
            st.warning("Please upload some PDF files first.")
        
def txt_prep():
    with open("исходный_файл.txt", "r") as original_file:
        content = original_file.readlines()

    # Разделение содержимого файла


    containers = []
    container = []

    for line in content:
        if "Получатель=" in line:
            container.append(line)
            containers.append(container)
            container = []
        elif "СекцияРасчСчет" in line:
            containers.append(container)
            container = []
            container.append(line)
        else:
            container.append(line)
    containers.append(container)

    header = containers[0]
    date = containers[1][:2]
    accounts = [[x] for x in containers[1][2:]]
    statements = containers[2:]
    ending = ['КонецФайла']

    txt_files = []

    for iter_account, iter_statement in zip(accounts, statements):
        iter_file = ''

    iter_file = header + date  + iter_account + iter_statement + ending
    txt_files.append(iter_file)

    for file, iter_account in zip(txt_files, accounts):
        file_name = find_account(iter_account[0])+".txt"
        with open(file_name, "w") as section_file:
            section_file.writelines(file)



#####################################



data = data_prep_load()
env_initiation()

upload = st.file_uploader(
    "Загружаем файлики", accept_multiple_files=True, type='pdf')

#statements = []
file_segregation(data=data)

upload_db, rename_db = db_creation(data=st.session_state.recognized_files, db=data)
#
add_vertical_space(6)
#
recongnition_status(upload, data=st.session_state.recognized_files)
preview()
#
add_vertical_space(6)
#
look_at_fund_accounts(data)
download_zip(upload, rename_db)