import requests
from bs4 import BeautifulSoup
import json
from fuzzywuzzy import fuzz
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt

#Group 2
#Mary Fleck, Matthew Liu, Jiaying Shi, Mary Fleck


#Source zero - data source 3 in the project prototype, downloaded from the web
source0 = pd.read_csv('https://data.wprdc.org/datastore/dump/5a05b9ec-2fbf-43f2-bfff-1de2555ff7d4')

keywords = ["Food Pantry", "Meal", "Lunch", "Dinner"]
searched_keywords = '|'.join(keywords)
# filter the data: keep only the rows that contain one of the keywords 
df1 = source0[source0["service_name"].str.contains(searched_keywords) & source0["category"].str.contains("pantries")] 
df2 = source0[source0["category"].str.contains("meal")]
source0_df = pd.concat([df1,df2])


#---------------------


# Scraping https://www.foodpantries.org/ci/pa-pittsburgh
response = requests.get("https://www.foodpantries.org/ci/pa-pittsburgh")
html_soup = BeautifulSoup(response.text, 'html.parser')
data = html_soup.find_all('script', type='application/ld+json')
scraped_data = []
for i,x in enumerate(data):
    temp = json.loads(x.text, strict=False)
    restaurant = {}
    if temp.get("name") != None:
        restaurant['organization'] = temp.get("name")
    if temp.get("image") != None:
        restaurant['image'] = temp.get("image")
    if temp.get("description") != None:
        restaurant['narrative'] = temp.get("description")
    if temp.get("address") != None:
        address = temp.get("address")['streetAddress'] + ', ' + temp.get("address")['addressLocality'] + ', ' + temp.get("address")['addressRegion'] + ', ' + temp.get("address")['postalCode']
        restaurant['address'] = address
    if len(restaurant) > 1:
        scraped_data.append(restaurant)

scraped_data[0]

source1 = scraped_data.copy()
source1_df = pd.DataFrame(source1)


#---------------------

# Scraping https://www.homelessshelterdirectory.org/cgi-bin/id/cityfoodbanks.cgi?city=pittsburgh&state=PA
scraped_data2 = []

response = requests.get("https://www.homelessshelterdirectory.org/cgi-bin/id/cityfoodbanks.cgi?city=pittsburgh&state=PA")
html_soup = BeautifulSoup(response.text, 'html.parser')
data = html_soup.find_all("div", {"class": "item_content"})
for i,x in enumerate(data):
    restaurant = {}
    if x.find('h4') != None:
        restaurant['organization'] = x.find('h4').text
    if x.find('p') != None:  
        restaurant['narrative'] = x.find('p').text
    if len(restaurant) > 1:
        scraped_data.append(restaurant)
        scraped_data2.append(restaurant)

source2 = scraped_data2.copy()
source2_df = pd.DataFrame(source2)


#---------------------

#Combine all data into a data frame
alldata = pd.concat([source0_df, source1_df, source2_df], sort=True, ignore_index = True)

#Drop dups
alldata.drop_duplicates(subset = 'organization', inplace = True)

#Re-index the data frame
alldata = alldata.reset_index(drop=True)

#Fill NAs
cleandata = alldata.fillna(0)

#Print the entire data frame
# with pd.option_context('display.max_rows', None, 'display.max_columns', None): 
#     print(cleandata)


#---------------------


#Extract phone numbers from the narrative
pat = r'\d{3}.\d{3}.\d{4}' 
to_search = cleandata['narrative'].tolist()

phone_ = {} 
i=-1 
for entry in to_search:
    i += 1
    if re.findall(pat, str(entry)):
        phone_[i] = list(re.findall(pat, str(entry)))[0:1] #gets the first phone number from the narrative

phone_

cleandata['narrative'][44] #dict indexes correspond with df indexes

#Add phone numbers to dataframe
for i in phone_:
    cleandata.loc[i,'phone'] = phone_[i]

#Extract addresses
pat2 = r'.*, [A-Z][A-Z] \d{5}?'


address = {} 
i=-1 
for entry in to_search:
    i += 1
    if re.findall(pat2, str(entry)):
        address[i] = re.findall(pat2, str(entry))
address
    
cleandata['narrative'][46] #dict indexes correspond with df indexes

#add addresses to df
for i in address:
    cleandata.loc[i,'address'] = address[i]


#---------------------


# Converting data frame to dictionary
from collections import OrderedDict, defaultdict
dd = defaultdict(list)
dd = cleandata.to_dict('records', into=dd)


#---------------------


# Traversing through each restaurant to extract google rating and address.
for i, restaurant in enumerate(dd):
    name = restaurant.get("organization")
    name = name.strip().replace(" ", "%20")
    api_key = "AIzaSyADX1QAGro4gr0VeKThf5fUA78nVF0HiRQ"
    location = "Pittsburgh"
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?"
    url = url+"&key=" + api_key
    url = url+"&input=" + name
    url = url+"&inputtype=textquery&fields=geometry,name,place_id,formatted_address,name,rating,opening_hours"
    response = requests.get(url)
    html_soup = BeautifulSoup(response.text, 'html.parser')
    google_places = json.loads(html_soup.text)
    sort_ratio = []
    # Matching for the closest restaurant match if more than one received
    if len(google_places.get("candidates"))>0:
        for place in google_places.get("candidates"):
            sort_ratio.append(fuzz.token_sort_ratio(place.get("formatted_address"),restaurant.get("address"))) 
        selected_google_place = google_places.get("candidates")[sort_ratio.index(max(sort_ratio))]
        rating = selected_google_place.get("rating")
        if selected_google_place.get("opening_hours")!=None:
            open_now = selected_google_place.get("opening_hours").get("open_now")
            restaurant["google_open_now"] = open_now
        formatted_address = selected_google_place.get("formatted_address")
        if selected_google_place.get("geometry")!=None:
          lat = selected_google_place.get("geometry").get("location").get("lat")
          long_ = selected_google_place.get("geometry").get("location").get("lng")
          restaurant["google_lat"] = lat
          restaurant["google_long"] = long_
        name = selected_google_place.get("name")
        place_id = selected_google_place.get("place_id")
        restaurant["google_rating"] = rating
        restaurant["google_formatted_address"] = formatted_address
        restaurant["google_name"] = name

        new_url = "https://maps.googleapis.com/maps/api/place/details/json?place_id=" +place_id + "&fields=formatted_phone_number,opening_hours/weekday_text,website,review&key=" + api_key
        new_response = requests.get(new_url)
        new_html_soup = BeautifulSoup(new_response.text, 'html.parser')
        selected_google_place_detailed = json.loads(new_html_soup.text).get("result")

        if selected_google_place_detailed.get("formatted_phone_number")!=None:
          restaurant["google_formatted_phone_number"] = selected_google_place_detailed.get("formatted_phone_number")

        if selected_google_place_detailed.get("reviews")!=None:
          reviews = selected_google_place_detailed.get("reviews")
          if len(reviews) > 1:
            restaurant["google_reviews_1"] = reviews[0].get("text")
            restaurant["google_reviews_2"] = reviews[1].get("text")
          elif len(reviews) == 1:
            restaurant["google_reviews_1"] = reviews[0].get("text")
            restaurant["google_reviews_2"] = ""
          else:
            restaurant["google_reviews_1"] = ""
            restaurant["google_reviews_2"] = ""

        if selected_google_place_detailed.get("website")!=None:
          restaurant["google_website"] = selected_google_place_detailed.get("website")

#-----------------------------------------------------------------------------




#---------------------
#option 1 - display all data

#copy data and clean
dfClean = pd.DataFrame.from_dict(dd)

#dfClean.dropna(inplace = True)
dfClean = dfClean[dfClean['google_formatted_phone_number'].notna()]
dfClean.reset_index(inplace = True)

dfClean = dfClean.replace({'Allegheny Valley Association of Churches/AVAC Interfaith Hospitality Network' : 'Allegheny Valley Association of Churches'})

#select columns and rename
dfShow = dfClean[['organization',
 'google_formatted_address',
 'google_formatted_phone_number',
 'google_rating',
 'google_website']]
colNames = ['organization', 'address', 'phone', 'rating', 'website']
dfShow.columns = colNames

#remove whitespace from headers and cells
dfShow = dfShow.rename(columns=lambda x: x.strip())
dfShow = dfShow.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

#sort by rating
dfShow = dfShow.sort_values(by=['rating'], ascending = False)



#---------------------
#option 2 - reviews

#select columns and rename
reviewDF = dfClean[['organization',
 'google_reviews_1',
 'google_reviews_2',
 'google_rating']]
colNames1 = ['organization', 'review1', 'review2', 'rating']
reviewDF.columns = colNames1

#remove whitespace from headers and cells
reviewDF = reviewDF.rename(columns=lambda x: x.strip())
reviewDF = reviewDF.apply(lambda x: x.str.strip() if (x.dtype != 'bool' and x.dtype == "object" ) else x)


#---------------------
#option 3 - display open now

#filter based on open food pantries
openNowDF = dfClean[dfClean['google_open_now'] == True]

#select columns and rename
openNowDF = openNowDF[['organization',
 'google_formatted_address',
 'google_formatted_phone_number',
 'google_rating',
 'google_website',
 'google_open_now']]
colNames2 = ['organization', 'address', 'phone', 'rating', 'website', 'open_now']
openNowDF.columns = colNames2


#---------------------
#option 4 - plot on map

#get lat lon, drop outlier or NA values
dfLonLat = dfClean[['google_lat', 'google_long']]
# dfLonLat = dfLonLat.drop([37, 64])

#load map image and bounding lat lon values
pgh_map = plt.imread('pgh_map.png')
BBox2 = (-80.0909, -79.7823, 40.5734, 40.329)


#---------------------
#option 5 - neighborhood bar plot

#filter by neighborhood, clean data and count by neighborhood
neighborDF = dfClean['neighborhood']
neighborDF = neighborDF.replace({'North SIde' : 'North Side', 'WIlkinsburg' : 'Wilkinsburg'})
neighborDF = neighborDF[neighborDF != 0].value_counts()



#---------------------
#Edit display preference for table output
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', 80)
pd.set_option('expand_frame_repr', False)


#---------------------
#User interaction

answer = ''
while answer != 'Q' and answer != 'q':
    print('''
    Please select from this menu:

    1)  Display table of food pantries sorted by rating
    2)  Display food pantries that are open now
    3)  Display food pantry reviews
    4)  Plot food pantries on map
    5)  Bar plot of food pantry distribution by neighborhood
    A)  More detail about specific pantry
    B)  Export table from 1) as a csv
    Q)  Quit from this program
    ''')
    answer = input('    Your choice: ').strip()
    if answer == '1':
        print(dfShow)

    elif answer == '2':
        print(openNowDF)

    elif answer == '3':
        print(reviewDF)

    elif answer == '4':
        #plot over map and set lat lon limits
        fig, ax = plt.subplots(figsize = (8,7))
        #opacity = 1, color = blue, size = 15
        ax.scatter(dfLonLat['google_long'], dfLonLat['google_lat'], zorder=1, alpha=1, c='b', s=15)
        ax.set_title('Location of Food Pantries in Pittsburgh')
        #set lon lat limitations
        ax.set_xlim(BBox2[0],BBox2[1])
        ax.set_ylim(BBox2[2],BBox2[3])
        ax.imshow(pgh_map, zorder=0, extent = BBox2, aspect= 'equal')
        plt.xlabel(xlabel = "Latitude")
        plt.ylabel(ylabel = "Longitude")
        plt.show()

    elif answer == '5':
        #bar plot of neighborhoods
        neighborDF.plot(kind = 'bar')
        #add labels/title and clean up label size
        plt.xticks(fontsize=6)
        plt.xlabel(xlabel = "Neighborhood")
        plt.ylabel(ylabel = "Count")
        plt.title(label = "Distribution of Shelters across Pittsburgh Neighborhoods")
        plt.show()

    elif answer == 'a' or answer == 'A':
        #user enters row number for more detailed information
        answerDetail = ''
        answerDetail = input('   Which Row would you like to look at? ').strip()

        #test if user entered valid integer and not a string etc
        try:
            print(dfClean.iloc[int(answerDetail)])
        except:
            print('\n    Your choice is invalid:', answerDetail, '\n')

    elif answer == 'b' or answer == 'B':
        #export first graph as csv
        dfShow.to_csv('food_pantries.csv', encoding='utf-8', index = False)

    elif answer == 'q' or answer == 'Q':
        pass   # the loop will terminate

    else:
        print('\n    Your choice is not valid:', answer, '\n')
