# -*- coding: utf-8 -*-
"""
Created on Sat Sep 16 13:51:56 2017

@author: dhartig
"""
import csv, re, shapefile

# Based on BP_2015_00CZ1.tzt from American Factfinder; used for Employment_by_zip_15
translate = {'a': 10, 'b': 60, 'c': 175, 'e': 375, 'f': 750, 'g': 1750, 'h': 3750, 'i': 7500, 'j': 17500, 'k': 37500, 'l': 75000}


# Helper function to parse zip code out of US Census bureau GEO.id
def zip_from_geoid(geoid):
    mtch = re.match("\d+US(\d{5})", geoid)
    if mtch:
        return mtch.group(1)
    return None

# All parse functions must start with 'read_'. All functions must return a dict with key = zipcode
# and val = another dict with key, vals of whatever data. There is no checking to ensure keys on the inner 
# dict do not collide. 
def read_population():
    data = {}
    with open('./Population_by_zip_15.csv', 'r') as f: 
        rdr = csv.reader(f, delimiter = ',', quotechar = '"')
        next(rdr) # not using a dictreader, skip the column headers
    
        for line in rdr:
            zcode = zip_from_geoid(line[0])
            data[zcode] = {'population': int(line[1]), 'pop_child': int(line[1]) - int(line[2]), 'pop_old': int(line[3])}
    
    return data
    
def read_employment():
    data = {}
    with open('./Employment_by_zip_15.csv', 'r') as f:
        rdr = csv.reader(f, delimiter = ',', quotechar = '"')
        next(rdr) # not using a dictreader, skip the column headers
        next(rdr) # Two lines of headers
        
        for line in rdr:
            zcode = zip_from_geoid(line[0])
            name = re.match("ZIP \d{5} \((.*)\)", line[1]).group(1)
                       
            if line[4] == 'D' or line[3] == 'S':
                emp = translate[line[3]]
                emp_pay = emp * 40
            else:
                emp = int(line[3])
                emp_pay = int(line[5])
           
            data[zcode] = {'name': name, 'employment': emp, 'emp_pay': emp_pay}
           
    return data
   
def read_geography():
    data = {}
    sf = shapefile.Reader("/opt/ziplfs/tl_2014_us_zcta510.shp")
    for r in sf.records():
        zcode, area, lat, lon = (r[i] for i in [0, 5, 7, 8])
        data[zcode] = {'area': float(area)/1000000, 'location': "ST_GEOMFROMTEXT('POINT({0} {1})')".format(float(lat), float(lon))} 
    return data

    
def read_housing():
    data = {}
    with open('./Housing_by_zip_15.csv', 'r') as f:
        rdr = csv.reader(f, delimiter = ',', quotechar = '"')
        next(rdr) # not using a dictreader, skip the column headers
        
        for line in rdr:
            zcode = zip_from_geoid(line[0])
            data[zcode] = {'hunits': int(line[1]), 
                            'hvacany': int(line[2]), 
                            'sing_det': int(line[3]),
                            'sing_att': int(line[4]),
                            'duplex': int(line[5]),
                            'three_four': int(line[6]),
                            'five_nine': int(line[7]), 
                            'ten_nineteen': int(line[8]),
                            'twenty_plus': int(line[9]),
                            '2014_later': int(line[10]),
                            '2010_2013': int(line[11]),
                            '2000_2009': int(line[12]),
                            '1990_1999': int(line[13]),
                            '1980_1989': int(line[14]),
                            '1970_1979': int(line[15]),
                            '1960_1969': int(line[16]),
                            '1950_1959': int(line[17]),
                            '1940_1949': int(line[18]),
                            '1939_older': int(line[19]),
                            'howner': int(line[20]),
                            'hrenter': int(line[21])}

    return data
        

        
        
        
    
    
    
    
    
    
    
            