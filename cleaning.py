
import pandas as pd
from wordsegment import load, segment
import re
import numpy as np
import requests
from bs4 import BeautifulSoup
import json
import google.generativeai as genai
import ast
import time
import warnings
warnings.filterwarnings("ignore")


def remove_duplicates(df):
    df = df.drop_duplicates(subset = ['job_details'])
    print('remove dupes done!')
    return df


def to_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None
    
def to_time(x):
    try:
        return pd.to_datetime(x).time()
    except:
        return None


def convert_datetime(df):
    # df['post_dates'] = df['post_dates'].astype('str')
    df['day_posted'] = df['post_dates'].apply(to_date)
    df['time_posted'] = df['post_dates'].apply(to_time)
    print('convert date-time done!')
    return df


def clean_job_details(df):
    df['job_details'] = df['job_details'].str.replace('\xa0', '')
    df['job_details'] = df['job_details'].str.replace('\u202f', '')
    df['job_details'] = df['job_details'].str.lower()
    df['job_details'] = df['job_details'].apply(lambda x: re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', x))
    df['job_details'] = df['job_details'].apply(lambda x: re.sub(r'\n', '', x))
    print('cleaned job details done!')

    return df

def clean_disciplines(df):
    df['subdisciplines'] = df['disciplines'].apply(lambda x : str(re.findall(r'\((.*?)\)', x)[0]))
    df['disciplines'] = df['disciplines'].apply(lambda x : re.sub(r'\([^\)]*\)\s*', ' ', x))
    df['disciplines'] = df['disciplines'].apply(lambda x :  re.sub(r'\s+', ' ', x).strip())
    print('cleaned disciplines done!')
    return df

#Used to convert salaries in foreign currency to PHP live
API_KEY = '' #exchangerate-api API key
base = 'PHP'
r = requests.get(f'https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{base}')
content = BeautifulSoup(r.content)
exchange_rates = json.loads(str(content))['conversion_rates']


def salary_extract(entry):
    entry = str(entry)
    # if there is no digit in the data then we replace it with None
    if bool(re.search(r'\d', entry)) == False:
        return None, None, None

    # is it a per hour rate?
    elif 'per hour' in entry:
        #it is in another currency
        if bool(re.search(r'\(.*?\)', entry)):
            currency = re.findall(r'\((.*?)\)',entry)[0]
            exchange_rate = exchange_rates[currency]


            if '–' in entry or ' to ' in entry:
                #Find the maximum and the minimum hourly rate
                values =  re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)
                min = float(values[0].replace(",",''))
                max = float(values[1].replace(",",''))

                #173 is the average number of work hours per week

                return round(min*173/exchange_rate,3) , round(max*173/exchange_rate,3), currency
            else:
                values = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)[0]
                val = float(values.replace(",",''))

                return round(val*173/exchange_rate,3) ,round(val*173/exchange_rate), currency 

        #Hourly Rate in PHP 
        else:
            #if it is in a range
            if '–' in entry or ' to ' in entry:
                values =  re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)
                #Find the maximum and minimum hourly rate
                min = float(values[0].replace(",",''))
                max = float(values[1].replace(",",''))
                return min*173, max*173, 'PHP'
            
            #Not in a range
            else:
                values = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)[0]
                val = float(values.replace(",",''))
                return val*173,val*173, 'PHP'

    # per month
    elif 'per month' in entry:

        #Another currency (DONE)
        if bool(re.search(r'\(.*?\)', entry)):
            currency = re.findall(r'\((.*?)\)',entry)[0]
            exchange_rate = exchange_rates[currency]


            if '–' in entry or ' to ' in entry:
                values =  re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)
                min = float(values[0].replace(",",''))
                max = float(values[1].replace(",",''))
                return round(min/exchange_rate,3) , round(max/exchange_rate,3), currency
            
            else:
                values = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)[0]
                val = float(values.replace(",",''))
                return round(val/exchange_rate,3) ,round(val/exchange_rate), currency
        
      
        #In PHP (DONE)
        else:
            if '–' in entry or ' to ' in entry:
                values =  re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)
                min = float(values[0].replace(",",''))
                max = float(values[1].replace(",",''))
                return min if min>1000 else None ,max if max>1000 else None, 'PHP'
            else:
                values = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", entry)[0]
                val = float(values.replace(",",''))
                return val if val>1000 else None ,val if val>1000 else None, 'PHP'
    else:
        return None,None,None


def min_salary(entry):
    return salary_extract(entry)[0]
def max_salary(entry):
    return salary_extract(entry)[1]
def salary_currency(entry):
    return salary_extract(entry)[2]


def clean_salary(df):
    df['min_salary'] = df['salaries'].apply(min_salary)
    df['max_salary'] = df['salaries'].apply(max_salary)
    df['salary_currency'] = df['salaries'].apply(salary_currency)
    print('clean salary done!')
    return df


genai.configure(api_key='' #Gemini API key)
model = genai.GenerativeModel("gemini-1.5-flash")


#Converts a dictionary into a list
def output_to_dict(output):
    try:
        start = output.find("{")  # Find the starting bracket
        end = output.rfind("}")
        python_dict = ast.literal_eval(output[start:end+1])
        return python_dict
    except:
        return {'concepts': [], 'tools': [], 'education': [], 'yoe': []}


#Extraces information from the job descriptions
def prompt(job_desc):
    prompt_clean_desc = f"""

    You will output strictly a python dictionary with four values and four keys: "concepts", "tools", "education", "yoe" based on a job description.

    The values of the dictionary of are lists and their contents are governed by the following:

    For the "concepts" key:

    For the job decription below, place ALL the Data Analytics, Programming and Data Science concepts/roles/responsibilities desired by the employer in a python list and nothing else. 
    The output should strictly be a python list. Examples of such concepts are: Machine Learning, 
    Data Analysis,Exploratory Data Analysis, Natural Language Processing, Data Cleaning etc. The list must not include specific tools like Python, R, SAS etc. 
    If there are none, return an empty python list.


    For the "tools" key:

    For the job decription below, place ALL the Data Analytics and Data Science tools/technologies/frameworks desired by the employer in a python list and nothing else. 
    The output should strictly be a python list.
    Examples are Python, Excel, R, SAS, AWS, SQL, PowerBI, Tableau, Google Cloud, and others. It has to be a specific tool.
    If it is by Microsoft do not place Microsoft or MS before the actual name.
    Do not include concepts such as Machine Learning, Data Analysis,Exploratory Data Analysis, Natural Language Processing, Data Cleaning etc. 
    If there are none, return an empty python list.

    For the "education" key:

    For the job decription below, place ALL the explicitly degrees/courses desired by the employer in a python list and nothing else.
    The degrees must be specific such as IT, Computer Science, Statistics, Mathematics and more. If the employer explicitly says 'any degree', place  ONLY 'Any'and into the list. 
    DO NOT PUT BS/MS/PhD, Bachelor's Degree, and Graduate Degree. Put only the name of the degree/course.
    It has to be a specific course. Do NOT put "Any ___ related course", "Bachelor's/Master's degree in a ______ field", or "Bachelor's Degree"
    If there are no courses/degrees specified, return an empty python list.

    For the "yoe" key:

    For the job decription below, place the minimum years of experience as an integer in a python list and nothing else. 
    Choose the highest years of experience mentioned in the job description so the resulting list will have only one entry.
    Place 0 if it is open to fresh graduates. If the document does not mention years of experience, then the list must be empty. 
    

    The job_description is: {job_desc}

    """
    response_total = model.generate_content(prompt_clean_desc)
    output_total = response_total.text
    return output_to_dict(output_total)


#Places them in a new column
def clean_descriptions(df):
    df.loc[:,'responsibilities'] = pd.Series([[] for i in range(len(df))])
    df.loc[:,'tools'] =  pd.Series([[] for i in range(len(df))])
    df.loc[:,'education'] = pd.Series([[] for i in range(len(df))])
    df.loc[:,'yoe'] =  pd.Series([[] for i in range(len(df))])
    for i in list(df.index):
        result_dict = prompt(df.loc[i,'job_details'])
        df.at[i,'responsibilities'] = result_dict['concepts']
        df.at[i,'tools'] = result_dict['tools']
        df.at[i,'education'] = result_dict['education']
        df.at[i,'yoe'] = result_dict['yoe']
        print(f'job description {i+1} out of {len(df)} cleaned!')
        time.sleep(6)
    print('extract data from job details done!')
    return df


#Cleans the addresses
def clean_address(df):
    df['locations'] = (
        df['locations']
        .str.lower()                # Convert to lowercase
        .str.strip()                # Remove leading/trailing spaces
        .str.replace(r'\s+', ' ', regex=True)  # Normalize spaces
    )
    return df


#Converts string into a list
def output_to_list(output):
    start = output.find("[")  # Find the starting bracket
    end = output.rfind("]")
    python_list = ast.literal_eval(output[start:end+1])
    return python_list


#Clean list data if needed
def clean_list(df):
    df['tools'] = df['tools'].apply(lambda x : output_to_list(x))
    df['education'] = df['education'].apply(lambda x : output_to_list(x))
    df['responsibilities']  = df['responsibilities'].apply(lambda x : output_to_list(x))
    df['yoe'] = df['yoe'].apply(lambda x : output_to_list(x))
    return df





