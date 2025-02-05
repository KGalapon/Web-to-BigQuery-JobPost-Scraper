

from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import json
import math
import random
from datetime import date
date_today = date.today()


def extract_transform_single_page(url, headers, page_counter):

    """
    url = link (string)
    headers = headers (dictionary)
    page_counter = number of pages to scrape (integer)
    
    """

    #INITIALIZE THE LISTS STORING THE DETAILS
    job_ids = []
    job_titles = []
    companies = []
    locations = []
    disciplines = []
    work_types = []
    salaries = []
    post_dates = []
    job_details = []
    links = []

    r = requests.get(url, headers)
    soup = BeautifulSoup(r.content, 'html.parser')
    cards = soup.find_all('div', class_ = '_1fggenz0 _1feq2e74v _1feq2e751')
    for c, job_counter in zip(cards,range(len(cards))) :
        a = c.find('a')
        
        #JOB ID EXTRACTION
        job_id = a['href'][5:13]
        job_ids.append(job_id)
        
        #JOB PAGE LINK
        job_url = 'https://ph.jobstreet.com' + a['href']

        
        #EXTRACT AND PROCESS FROM EVERY JOB URL
        r_job_page = requests.get(job_url, headers)
        soup_job_page = BeautifulSoup(r_job_page.content, 'html.parser')
        
        #JOB_TITLE EXTACTION
        
        #First h1 element of the page
        title = soup_job_page.find('h1').text
        job_titles.append(title)
        
        #COMPANY_NAME
        
        company = soup_job_page.find('span', attrs = {'data-automation': 'advertiser-name'}).text
        companies.append(company)
        
        #LOCATION
        location = soup_job_page.find('span', attrs = {'data-automation': 'job-detail-location'}).text
        locations.append(location)
        
        #DISCIPLINE
        discipline = soup_job_page.find('span', attrs = {'data-automation': 'job-detail-classifications'}).text
        disciplines.append(discipline)
        
        #WORK TYPE
        work_type = soup_job_page.find('span', attrs = {'data-automation': 'job-detail-work-type'}).text
        work_types.append(work_type)
        
        #SALARY
        
        salary = soup_job_page.find('span', attrs = {'data-automation': 'job-detail-salary'})
        if salary == None:
            salaries.append(None)
        else: 
            salaries.append(salary.text)
            
        #POST_DATE
        try:
            date_json = soup_job_page.find_all('script', type="application/ld+json")[1].text
            post_date = json.loads(date_json)['datePosted']
            post_dates.append(post_date)
        except:
            post_dates.append(None)
            
        #JOB_DETAILS
        job_detail = soup_job_page.find('div', attrs = {'data-automation': 'jobAdDetails'}).text
        job_details.append(job_detail)
        
        #LINK
        links.append(job_url)

        print(f'Page {page_counter + 1}, Job No. {job_counter +1}, {job_id} scraped!')

        time.sleep(random.uniform(3,7))
     
    return job_ids, job_titles, companies, locations, disciplines, work_types, salaries, post_dates, job_details, links


# For scraping all the pages!!!
def scrape_to_csv_all(url, headers, main_dict,pages_to_scrape):
    
    # READ URL
    r_page = requests.get(url, headers)
    soup = BeautifulSoup(r_page.content, 'html.parser')

    if r_page.status_code == 200:

        # SCRAPE THE NUMBER OF JOBS
        no_jobs = int(soup.find('span', attrs = {'data-automation' : 'totalJobsCount'}).text.replace(',',''))

        #ESTIMATE THE NUMBER OF PAGES TO SCRAPE
        est_no_page = math.ceil(no_jobs/32) #there are 32 jobs per page

        page_total = est_no_page if pages_to_scrape == None  else pages_to_scrape

        print(f'There are a total of {page_total} pages to scrape but we will scrape {pages_to_scrape}')

        #LOOP THROUGH THE PAGES
        for i in range(page_total):
            try:
                page_url = url + '&page=' + str(i+1) + '&sortmode=KeywordRelevance'
                results = extract_transform_single_page(page_url, headers, i)

        
                #Add the results to the dictionary
                for index, key in zip(range(10), main_dict.keys()):
                    main_dict[key] = main_dict[key] + results[index]
            except:
                return main_dict
            
            print(f'Page {i+1} scraped!')
            
            time.sleep(random.uniform(30,60))
        return main_dict

    else:
        print(f'Something went wrong. Status code {r_page.status_code}')
